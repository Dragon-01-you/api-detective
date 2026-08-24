#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""baseline_compare: 官方基线自动化比对（吸收 llm-verify 基线比对逻辑）。

流程:
  1. generate_baseline(model, base_url, api_key) —— 用官方 Key 跑标准化探针组，
     生成 baselines/<model>.json（身份自认/分词器家族/错误措辞/延迟分布/知识截止）
  2. compare_with_baseline(results, model) —— 目标端点 dig 结果 vs 官方基线，
     输出每维偏离度（余弦相似度 / 欧氏距离 / KL 散度）与三级判定:
       FRAUD_DETECTED / SUSPICIOUS / INCONCLUSIVE / MATCH

基线来源: 用户用官方 Key 生成，或社区 PR 贡献。
GitHub Actions 每周定时刷新（.github/workflows/baseline-sync.yml，需配置官方
Key Secrets，未配置时自动跳过——不消耗额度）。
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime, timezone

# ----------------------------------------------------------------------
# 基础度量（纯 Python 实现，避免 numpy 依赖）
# ----------------------------------------------------------------------
def _cosine(a: dict[str, float], b: dict[str, float]) -> float:
    """字符 3-gram 向量的余弦相似度 ∈ [0,1]。"""
    keys = set(a) | set(b)
    dot = sum(a.get(k, 0.0) * b.get(k, 0.0) for k in keys)
    na = math.sqrt(sum(v * v for v in a.values()))
    nb = math.sqrt(sum(v * v for v in b.values()))
    return dot / (na * nb) if na and nb else 0.0


def _ngram_vec(text: str, n: int = 3) -> dict[str, float]:
    t = re.sub(r"\s+", " ", (text or "").lower())
    return {t[i:i + n]: float(t.count(t[i:i + n]))
            for i in range(max(0, len(t) - n + 1))}


def _kl_divergence(p: list[float], q: list[float], bins: int = 8) -> float:
    """两个样本集的直方图 KL 散度（对称化 Jensen-Shannon 风格，平滑防 ∞）。"""
    def _hist(xs):
        if not xs:
            return [1e-9] * bins
        lo, hi = min(xs), max(xs)
        if hi <= lo:
            h = [1e-9] * bins
            h[0] = 1.0
            return h
        h = [0.0] * bins
        for x in xs:
            idx = min(bins - 1, int((x - lo) / (hi - lo) * bins))
            h[idx] += 1
        s = sum(h)
        return [max(v / s, 1e-9) for v in h]

    hp, hq = _hist(p), _hist(q)
    sp = sum(hp)
    sq = sum(hq)
    hp = [v / sp for v in hp]
    hq = [v / sq for v in hq]
    kl = sum(pi * math.log(pi / qi) for pi, qi in zip(hp, hq))
    return round(kl, 4)


def _euclid(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return float("nan")
    n = min(len(a), len(b))
    return round(math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(n))), 4)


# ----------------------------------------------------------------------
# 基线生成（用官方端点跑标准化探针组）
# ----------------------------------------------------------------------
GEN_PROBES = [
    ("id_who", "Who developed you? One short sentence."),
    ("id_model", "What model are you exactly? One short sentence."),
    ("id_cutoff", "What is your knowledge cutoff date? Answer with the date only."),
    ("tk_a", "Reply with the exact string: 'The quick brown fox jumps over the lazy dog'"),
    ("tk_b", "Reply with the exact string: '人工智能正在改变世界1234567890'"),
]


def generate_baseline(model: str, base_url: str, api_key: str,
                      out_dir: str = "./baselines", n_latency: int = 6) -> str:
    """用官方端点生成基线文件 baselines/<model>.json。"""
    from .core import Detective
    from . import __version__

    det = Detective(base_url, api_key, model,
                    out_dir=os.path.join(out_dir, "_runs"))
    canary = det.canary()
    if canary.get("blocked") or not canary.get("ok"):
        raise RuntimeError(f"官方端点不可用/计费被挡: {canary}")

    features: dict = {}
    # ---- 身份/知识截止 ----
    id_texts = {}
    for name, q in GEN_PROBES:
        rec = det.chat(f"bl_{name}", [{"role": "user", "content": q}],
                       max_tokens=200)
        id_texts[name] = ((rec.get("response") or {}).get("message") or {}).get("content") or ""
    features["identity"] = {
        "who_answer": id_texts["id_who"][:300],
        "model_answer": id_texts["id_model"][:300],
        "cutoff_answer": id_texts["id_cutoff"][:200],
    }
    # ---- 分词器计数指纹 ----
    from .tokenizer_probe import tokenizer_probe
    tk = tokenizer_probe(det)
    features["tokenizer"] = {
        "counter_verdict": tk.get("counter_verdict"),
        "probe_detail": {k: v for k, v in tk.items()
                         if isinstance(v, (int, float, str))},
    }
    # ---- 延迟分布 ----
    lat = []
    for i in range(n_latency):
        rec = det.chat(f"bl_lat_{i}", [{"role": "user", "content": "Say OK."}],
                       max_tokens=5)
        if rec.get("latency_s"):
            lat.append(rec["latency_s"])
    lat_sorted = sorted(lat)
    features["latency"] = {
        "samples_s": lat,
        "p50": lat_sorted[len(lat_sorted) // 2] if lat else None,
        "p90": lat_sorted[int(len(lat_sorted) * 0.9) - 1] if lat else None,
    }
    # ---- 错误措辞指纹 ----
    from .behavior import error_fingerprint
    try:
        errs = error_fingerprint(det)
        phrases = {k: v.get("body_head", "")[:200]
                   for k, v in errs.items()
                   if isinstance(v, dict) and k.startswith("err_")}
        features["errors"] = {"phrases": phrases}
    except Exception as e:  # noqa: BLE001
        features["errors"] = {"phrases": {}, "error": str(e)[:200]}

    doc = {
        "model": model,
        "base_url_origin": re.sub(r"https?://", "", base_url.split("/v1")[0]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_version": __version__,
        "n_billable_calls": det.billable_calls,
        "features": features,
    }
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, f"{model}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    return path


# ----------------------------------------------------------------------
# 基线比对
# ----------------------------------------------------------------------
def _load_baseline(name: str, baseline_dir: str = "./baselines") -> dict:
    path = os.path.join(baseline_dir, f"{name}.json")
    if not os.path.isfile(path):
        # 模糊匹配: deepseek-v4 ≈ deepseek-v4.json / deepseek_v4.json
        if os.path.isdir(baseline_dir):
            for fn in os.listdir(baseline_dir):
                if fn.endswith(".json") and fn[:-5].lower().replace("_", "-") == \
                        name.lower().replace("_", "-"):
                    path = os.path.join(baseline_dir, fn)
                    break
            else:
                raise FileNotFoundError(
                    f"基线不存在: {path}。可用命令生成: "
                    f"python -m api_detective baseline --generate {name} "
                    f"--base-url <官方URL> --api-key <官方KEY>")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def compare_with_baseline(results: dict, baseline_name: str,
                          baseline_dir: str = "./baselines") -> dict:
    """目标 dig 结果 vs 官方基线 → 每维偏离度 + 三级判定。"""
    bl = _load_baseline(baseline_name, baseline_dir)
    bf = bl.get("features") or {}
    dims: list[dict] = []
    hard_mismatches = 0

    # ---- 1. 身份自认（硬指标）----
    bl_id = bf.get("identity") or {}
    ident = results.get("identity") or {}
    claims = ident.get("self_claim_counts") or {}
    if claims and bl_id.get("model_answer"):
        bl_vec = _ngram_vec(bl_id["model_answer"])
        # 目标端点身份答案与官方基线答案的语义相似度
        rows = ident.get("rows") or []
        target_text = " ".join((r.get("content") or "") for r in rows)[:800]
        if target_text.strip():
            tgt_vec = _ngram_vec(target_text)
            sim = _cosine(bl_vec, tgt_vec)
            dev = round(1 - sim, 4)
        else:
            dev = 0.5
        dims.append({"dimension": "identity_self_claim",
                     "metric": "cosine_similarity",
                     "value": f"sim={1 - dev:.3f}", "deviation": dev,
                     "hard": True})
        if dev >= 0.5:
            hard_mismatches += 1
    # unmask 厂商自认兜底
    um = results.get("unmask") or {}
    vc = um.get("vendor_confessions") or {}
    if vc and bl_id.get("who_answer"):
        bl_who = bl_id["who_answer"].lower()
        bl_brand = next((b for b in ("openai", "anthropic", "deepseek",
                                     "google", "qwen", "zhipu", "moonshot")
                         if b in bl_who), "")
        mismatched = {m: v for m, v in vc.items()
                      if bl_brand and bl_brand not in (v or "").lower()}
        if mismatched:
            dims.append({"dimension": "vendor_confession",
                         "metric": "exact_match",
                         "value": f"自认 {list(mismatched.values())[:3]} vs "
                                  f"官方 {bl_brand}",
                         "deviation": 1.0, "hard": True})
            hard_mismatches += 1

    # ---- 2. 分词器家族（硬指标）----
    bl_tk = (bf.get("tokenizer") or {}).get("counter_verdict")
    tgt_tk = (results.get("tokenizer") or {}).get("counter_verdict")
    if bl_tk:
        dev = 0.0 if bl_tk == tgt_tk else (0.0 if not tgt_tk else 1.0)
        dims.append({"dimension": "tokenizer_family",
                     "metric": "exact_match",
                     "value": f"target={tgt_tk} baseline={bl_tk}",
                     "deviation": dev, "hard": bool(tgt_tk)})
        if tgt_tk and dev >= 0.5:
            hard_mismatches += 1

    # ---- 3. 延迟分布（软指标，KL 散度）----
    bl_lat = (bf.get("latency") or {}).get("samples_s") or []
    tgt_lat = []
    beh = results.get("behavior") or {}
    if isinstance(beh.get("latency"), dict):
        tgt_lat = beh["latency"].get("values") or \
                  beh["latency"].get("samples_s") or []
    if bl_lat and tgt_lat:
        kl = _kl_divergence(bl_lat, tgt_lat)
        # KL > 1.0 视为分布显著不同 → 归一化为偏离度
        dev = round(min(1.0, kl / 2.0), 4)
        dims.append({"dimension": "latency_distribution",
                     "metric": "kl_divergence",
                     "value": f"KL={kl}", "deviation": dev, "hard": False})

    # ---- 4. 知识截止日期（软指标，仅当两侧都有答案时比对）----
    bl_cut = (bl_id.get("cutoff_answer") or "")
    cut_m = re.search(r"20\d{2}", bl_cut)
    if cut_m:
        bl_year = cut_m.group(0)
        # 从 dialect/identity 原始行里扫年份答案
        tgt_cut_texts = []
        dl = results.get("dialect") or {}
        for row in (dl.get("rows") or []):
            c = row.get("content") if isinstance(row, dict) else None
            if c and any(k in str(c).lower()
                         for k in ("cutoff", "截止", "知识截至", "训练数据")):
                tgt_cut_texts.append(str(c))
        tgt_cut = " ".join(tgt_cut_texts)
        tgt_m = re.search(r"20\d{2}", tgt_cut)
        if tgt_m:
            dev = 0.0 if tgt_m.group(0) == bl_year else 1.0
            dims.append({"dimension": "knowledge_cutoff",
                         "metric": "exact_match",
                         "value": f"target={tgt_m.group(0)} "
                                  f"baseline={bl_year}",
                         "deviation": dev, "hard": False})

    # ---- 5. LLMmap 最近邻（若两侧都有）----
    lm = results.get("llmmap") or {}
    bl_lm = bf.get("llmmap_top1")
    if lm.get("top1") and bl_lm:
        same = lm["top1"]["model"] == bl_lm
        dims.append({"dimension": "llmmap_top1",
                     "metric": "exact_match",
                     "value": f"target={lm['top1']['model']} baseline={bl_lm}",
                     "deviation": 0.0 if same else 1.0, "hard": False})

    # ---- 汇总 ----
    if not dims:
        return {"verdict": "INCONCLUSIVE", "total_deviation": None,
                "dimensions": [], "baseline": bl.get("model"),
                "reason": "无可比对维度（dig 结果缺少 identity/tokenizer 等探针输出）"}
    total = round(sum(d["deviation"] for d in dims) / len(dims), 4)
    if hard_mismatches >= 2 or (hard_mismatches >= 1 and total >= 0.6):
        verdict = "FRAUD_DETECTED"
    elif total >= 0.5:
        verdict = "SUSPICIOUS"
    elif total >= 0.25:
        verdict = "SUSPICIOUS" if hard_mismatches else "INCONCLUSIVE"
    else:
        verdict = "MATCH"
    return {
        "verdict": verdict,
        "total_deviation": total,
        "hard_mismatches": hard_mismatches,
        "dimensions": dims,
        "baseline": bl.get("model"),
        "baseline_generated_at": bl.get("generated_at"),
        "note": "偏离度=0 完全吻合 / 1 完全偏离；hard 维度（身份/分词器）"
                "两个以上错位即 FRAUD_DETECTED",
    }
