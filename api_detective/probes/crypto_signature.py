#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""crypto_signature: 密码学签名验证（最高权重证据类别）。

与行为侧信道（分词器/措辞/延迟）不同，这里检测的是**密码学证据**：

1. Anthropic thinking signature（吸收自 Veridrop 方法学）
   - extended thinking 模式下，官方服务端会在 thinking block 附加加密签名
     （约 500–2000+ 字符 Base64）
   - 签名由 Anthropic 服务端生成，中转站理论上无法伪造
   - 检测：存在性 + 长度 + Base64 字符集 + 多次调用差异性（真签名每次不同）
   - 注：Anthropic 未公开验签公钥，故做结构化验证（存在/长度/字符集/可变性）；
     官方若开放验签 API，可在 _verify_signature() 接入

2. OpenAI reasoning token 合理性（o1/o3/o4 系列）
   - 真实推理模型的 reasoning token 数与问题难度强相关
   - 检测：同一模型对「难/易」两档问题的 reasoning_tokens 是否有显著区分
   - 伪造模型常表现为：reasoning_tokens 恒定、为 0、或与难度无关

输出 evidence 列表（verdict 类别: crypto_signature，权重最高 0.18）。
"""
from __future__ import annotations

import base64
import json
import re
import time

import requests

from ..core import Detective

ANTHROPIC_VERSION = "2023-06-01"
SIG_LEN_MIN = 400     # 真实签名下限（放宽到 400 防官方变更后漏报）
SIG_LEN_MAX = 4000    # 上限（防伪造超长填充）
_B64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")

# 难/易两档问题（数学题：难度差应体现为 reasoning_tokens 差）
EASY_TASK = "What is 2+2? Reply with the number only."
HARD_TASK = ("A train leaves A at 60km/h, another leaves B (300km away) at 90km/h "
             "towards it. After how many minutes do they meet? Show reasoning.")


def _anthropic_request(det: Detective, body: dict) -> tuple[int, dict | None, str]:
    """裸 HTTP 调 Anthropic Messages 协议（/v1/messages）。"""
    base = det.base_url.rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    url = f"{base}/v1/messages"
    headers = {"x-api-key": det.api_key,
               "authorization": f"Bearer {det.api_key}",
               "anthropic-version": ANTHROPIC_VERSION,
               "content-type": "application/json"}
    try:
        r = requests.post(url, headers=headers, json=body, timeout=180)
        try:
            return r.status_code, r.json(), r.text[:2000]
        except ValueError:
            return r.status_code, None, r.text[:2000]
    except Exception as e:  # noqa: BLE001
        return 0, None, str(e)[:500]


def _check_signature_block(block: dict) -> dict:
    """结构化验证单个 thinking block 的 signature。"""
    sig = block.get("signature") or ""
    info = {"len": len(sig), "nonempty": bool(sig)}
    info["len_ok"] = SIG_LEN_MIN <= len(sig) <= SIG_LEN_MAX
    info["b64_charset_ok"] = bool(sig) and bool(_B64_RE.match(sig))
    # Base64 可解码性
    try:
        base64.b64decode(re.sub(r"\s", "", sig), validate=True)
        info["b64_decodable"] = True
    except Exception:  # noqa: BLE001
        info["b64_decodable"] = False
    info["valid"] = all((info["nonempty"], info["len_ok"],
                         info["b64_charset_ok"], info["b64_decodable"]))
    return info


def _verify_signature(sig: str) -> dict:
    """预留：Anthropic 公开验签方法接入点。

    官方目前未公开 thinking signature 的验签公钥/API。
    若未来开放，在此实现（JWT/Ed25519 验签等），结构化验证降级为辅助。
    """
    return {"public_key_verification": "unavailable",
            "note": "Anthropic 未公开验签公钥，采用结构化验证"
                    "(存在性/长度/Base64/多调用差异性)"}


def anthropic_thinking_probe(det: Detective, n_calls: int = 2) -> dict:
    """Anthropic extended thinking 签名探针。"""
    out: dict = {"protocol": "anthropic", "n_calls": n_calls, "sigs": []}
    prompt = ("What is the capital of Australia? Think briefly then answer "
              "with the city name only.")
    for i in range(n_calls):
        body = {"model": det.model, "max_tokens": 2048,
                "thinking": {"type": "enabled", "budget_tokens": 1024},
                "messages": [{"role": "user", "content": prompt}]}
        t0 = time.monotonic()
        code, js, raw = _anthropic_request(det, body)
        rec = {"call": i, "status": code, "latency_s": round(time.monotonic() - t0, 2)}
        sigs_in_call = []
        if js:
            for blk in js.get("content", []):
                if isinstance(blk, dict) and blk.get("type") == "thinking":
                    chk = _check_signature_block(blk)
                    chk["sig_head"] = (blk.get("signature") or "")[:64]
                    sigs_in_call.append(chk)
            rec["model_field"] = js.get("model")
            rec["stop_reason"] = js.get("stop_reason")
            if js.get("error"):
                rec["api_error"] = js.get("error")
        else:
            rec["raw_head"] = raw[:300]
        rec["signatures"] = sigs_in_call
        out["sigs"].append(rec)
        det.ev.save(f"crypto_anth_think_{i}", rec)
        det.polite_sleep()

    # ---- 汇总判定 ----
    all_checks = [s for call in out["sigs"] for s in call.get("signatures", [])]
    out["n_signature_blocks"] = len(all_checks)
    out["any_valid"] = any(c["valid"] for c in all_checks)
    sig_values = []
    for call in out["sigs"]:
        for s in call.get("signatures", []):
            if s.get("nonempty"):
                sig_values.append(s.get("sig_head"))
    # 真签名每次调用都不同（同前缀=重复使用同一签名=伪造嫌疑）
    out["all_distinct"] = (len(sig_values) >= 2
                           and len(set(sig_values)) == len(sig_values))
    return out


def openai_reasoning_probe(det: Detective) -> dict:
    """OpenAI o1/o3/o4 reasoning token 合理性探针（难度区分度）。"""
    out: dict = {"protocol": "openai", "runs": []}
    for label, task in (("easy", EASY_TASK), ("hard", HARD_TASK)):
        rec = det.chat(f"crypto_r_{label}",
                       messages=[{"role": "user", "content": task}],
                       max_tokens=1500,
                       extra={"reasoning_effort": "medium"},
                       meta={"difficulty": label})
        usage = (rec.get("response") or {}).get("usage") or {}
        details = usage.get("completion_tokens_details") or {}
        rt = details.get("reasoning_tokens")
        out["runs"].append({"difficulty": label, "reasoning_tokens": rt,
                            "completion_tokens": usage.get("completion_tokens"),
                            "error": (rec.get("error") or {}).get("status_code")})
    # ---- 判定：难/易 reasoning tokens 应有区分度 ----
    rts = {r["difficulty"]: r["reasoning_tokens"] for r in out["runs"]}
    easy_rt, hard_rt = rts.get("easy"), rts.get("hard")
    if easy_rt is None and hard_rt is None:
        out["reasoning_supported"] = False
    else:
        out["reasoning_supported"] = True
        if isinstance(easy_rt, (int, float)) and isinstance(hard_rt, (int, float)):
            out["hard_gt_easy"] = hard_rt > easy_rt
            out["ratio"] = round(hard_rt / easy_rt, 2) if easy_rt else None
            # 难题 reasoning 应明显多于易题（≥1.3 倍且绝对差 ≥30）
            out["plausible"] = bool(hard_rt >= easy_rt * 1.3
                                    and hard_rt - easy_rt >= 30)
        else:
            out["plausible"] = None
    det.ev.save("crypto_oai_reasoning", out)
    return out


def crypto_signature_probe(det: Detective) -> dict:
    """主入口：组合 Anthropic 签名 + OpenAI reasoning 两路证据。"""
    evidence: list[dict] = []
    claimed = (det.model or "").lower()

    # ---- 路 1：Anthropic thinking signature ----
    # 声称 Claude 系 或 端点支持 /v1/messages 时启用
    is_claude = "claude" in claimed
    anth = anthropic_thinking_probe(det) if is_claude else None
    if anth is not None:
        if anth["n_signature_blocks"] == 0:
            # 有错误时（如 4xx）记录但不判死刑——可能是协议不支持
            err = any(c.get("api_error") or c.get("status") != 200
                      for c in anth["sigs"])
            evidence.append({
                "id": "thinking_signature_missing",
                "pass": False if not err else None,
                "inconclusive": err,
                "finding": (f"声称 Claude（{det.model}）但 extended thinking 响应中"
                            f"无 signature 块（{anth['n_calls']} 次调用）"),
                "detail": anth,
            })
        else:
            valid = anth["any_valid"]
            distinct = anth["all_distinct"]
            evidence.append({
                "id": "thinking_signature_valid" if (valid and distinct)
                else "thinking_signature_suspicious",
                "pass": bool(valid and distinct),
                "finding": (f"thinking signature 存在×{anth['n_signature_blocks']}，"
                            f"结构合法={valid}，多次调用互异={distinct}"),
                "detail": anth,
                "verification": _verify_signature(""),
            })

    # ---- 路 2：OpenAI reasoning token 合理性 ----
    is_reasoning_model = any(k in claimed for k in
                             ("o1", "o3", "o4", "reasoning", "r1"))
    oai = openai_reasoning_probe(det) if is_reasoning_model else None
    if oai is not None:
        if not oai.get("reasoning_supported"):
            evidence.append({
                "id": "reasoning_token_absent",
                "pass": None,  # 不定罪：可能网关剥离了 usage 细节
                "inconclusive": True,
                "finding": f"声称推理模型（{det.model}）但 usage 无 reasoning_tokens 字段",
                "detail": oai,
            })
        elif oai.get("plausible") is False:
            evidence.append({
                "id": "reasoning_token_anomaly",
                "pass": False,
                "finding": (f"reasoning_tokens 与难度无关: "
                            f"easy={oai['runs'][0]['reasoning_tokens']} / "
                            f"hard={oai['runs'][1]['reasoning_tokens']}"),
                "detail": oai,
            })
        elif oai.get("plausible") is True:
            evidence.append({
                "id": "reasoning_token_plausible",
                "pass": True,
                "finding": (f"reasoning_tokens 随难度递增: "
                            f"easy={oai['runs'][0]['reasoning_tokens']} → "
                            f"hard={oai['runs'][1]['reasoning_tokens']}"),
                "detail": oai,
            })

    result = {
        "probe": "crypto_signature",
        "claimed_model": det.model,
        "protocols_tested": [e for e in (("anthropic", is_claude),
                                         ("openai-reasoning", is_reasoning_model))
                             if e[1]],
        "evidence": evidence,
        "n_evidence": len(evidence),
        "verdict_hint": ("密码学证据已采集" if evidence
                         else "未命中密码学探针适用协议（非 Claude / 非推理模型）"),
    }
    det.ev.save("crypto_signature_summary", result)
    return result


def _dump(x) -> str:
    return json.dumps(x, ensure_ascii=False, default=str)[:500]
