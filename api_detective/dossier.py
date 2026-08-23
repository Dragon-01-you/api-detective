"""dossier: 一键挖掘模式的总档案（DOSSIER.md）生成器。"""
from __future__ import annotations

import json
import os


def _evidence_inventory(evidence_dir: str) -> list[dict]:
    rows = []
    for fn in sorted(os.listdir(evidence_dir)):
        if not fn.endswith(".json"):
            continue
        path = os.path.join(evidence_dir, fn)
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
        size = os.path.getsize(path)
        brief = ""
        if isinstance(data, dict):
            for k in ("content", "body", "snippet", "quote", "text", "reply"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    brief = v.strip().replace("\n", " ")[:90]
                    break
            if not brief:
                brief = ", ".join(list(data.keys())[:6])[:90]
        elif isinstance(data, list):
            brief = f"[{len(data)} items]"
        rows.append({"file": fn, "size": size, "brief": brief})
    return rows


def generate_dossier(results: dict, evidence_dir: str) -> str:
    meta = results.get("meta", {})
    v = results.get("verdict", {})
    sc = results.get("supplychain", {})
    lines = []
    a = lines.append

    a("# DOSSIER —— 中转站深度挖掘总档案")
    a("")
    a(f"- 目标: `{meta.get('base_url', '?')}`　模型名: `{meta.get('model', '?')}`")
    a(f"- 时间(UTC): {meta.get('ts_utc', '?')}　工具版本: v{meta.get('version', '?')}")
    canary = results.get("canary") or {}
    incomplete = canary.get("blocked") or not (results.get("identity") or results.get("pliny"))
    if incomplete:
        a("")
        a("> ⚠️ **证据不完整警告**：对话通道被计费闸门拦截或挖掘未完成，")
        a("> 本档案仅含零成本指纹与关系网推断。**当前判决分数不可作为最终结论**——")
        a("> 历史案件（2026-08 raw/raw3/raw4）已确证该类站点存在贴牌与路由欺诈。")
        a("> 补充可用 API key 后重跑 dig 以获得完整判决。")
    if v and not incomplete:
        a(f"- **判决**: {v.get('tier', '?')}（得分 {v.get('score', '?')}/100）")
    st = sc.get("stats", {})
    if st:
        a(f"- **关系网**: {st.get('节点数', 0)} 节点 / 确证边 {st.get('确证边', 0)} / 高置信边 {st.get('高置信边', 0)}")
    a("")

    a("## 〇、揭面速览（unmask · 模型真身与系统提示词）")
    a("")
    um = results.get("unmask") or {}
    if um:
        uv = um.get("verdict") or {}
        vc = um.get("vendor_confessions") or {}
        if vc:
            a("### 厂商自认矩阵（英文明问 'Who developed you?'）")
            a("")
            a("| SKU（商家声称） | 自认真实厂商 | 原话 |")
            a("|---|---|---|")
            for m, x in vc.items():
                a(f"| `{m}` | **{x['vendor']}** | {x['quote'][:80].replace(chr(10), ' ')} |")
            a("")
        tiers = um.get("injection_tiers") or {}
        if tiers:
            a(f"### 注入分层（按 prompt_tokens 聚类）：`{tiers}`")
            a("")
            if uv.get("shared_injection_tiers"):
                a(f"- ⚠️ 同注入层多品牌共享（单后端嫌疑）：`{uv['shared_injection_tiers']}`")
        if uv.get("identity_hijack_models"):
            a(f"- ⚠️ 中文身份问题触发渠道改道的 SKU：`{uv['identity_hijack_models']}`")
        if uv.get("phantom_skus"):
            a(f"- ⚠️ 目录虚挂 SKU（502/503 无渠道）：`{uv['phantom_skus']}`")
        ctx = um.get("ctx_windows") or {}
        if ctx:
            for m, x in ctx.items():
                a(f"- 上下文窗口实测：`{m}` = **{x.get('tokens')}** tokens（原始回答：{x.get('raw', '')[:40]}）")
        vh = um.get("verbatim_hits") or []
        if vh:
            a("")
            a(f"### 系统提示词逐字命中（{len(vh)} 条）")
            a("")
            for h in vh:
                a(f"#### [{h['model']} · {h['channel']} 通道 · score={h['score']}]")
                a("")
                a("```text")
                a(str(h["text"])[:2000])
                a("```")
                a("")
    else:
        a("（dig 未运行揭面阶段或计费被挡）")
    a("")

    a("## 一、供应链关系网")
    a("")
    if sc.get("mermaid"):
        a("```mermaid")
        a(sc["mermaid"])
        a("```")
        a("")
        a("### 边清单（含置信度与支撑证据）")
        a("")
        a("| 来源 | 关系 | 目标 | 置信度 | 支撑证据 |")
        a("|---|---|---|---|---|")
        for src, es in (sc.get("edges") or {}).items():
            src_label = (sc.get("nodes", {}).get(src, {}) or {}).get("label", src)
            for e in es:
                ev = "；".join(e["evidence"])[:150]
                a(f"| {src_label} | {e['relation']} | {sc['nodes'].get(e['dst'], {}).get('label', e['dst'])} "
                  f"| {e['confidence']} | {ev} |")
    else:
        a("（对话通道不可用，仅零成本指纹结果，见下）")
    a("")

    a("## 二、系统提示词挖掘结果")
    a("")
    py = results.get("pliny") or {}
    pe = results.get("prompt_extract") or {}
    best = (py.get("best_hits") or []) + (pe.get("hits") or [])
    if best:
        a(f"命中 {len(best)} 条（强命中 {py.get('strong_hits', '-')}，最高分 "
          f"{max(py.get('max_score', 0), pe.get('max_score', 0) if isinstance(pe, dict) else 0)}）。逐条全文：")
        a("")
        for h in best:
            tid = h.get("id", "?")
            a(f"### [{tid}] hit_score={h.get('hit_score')}")
            if h.get("content"):
                a("```text")
                a(str(h["content"]))
                a("```")
            if h.get("cot"):
                a("<details><summary>思维链侧信道</summary>")
                a("")
                a("```text")
                a(str(h["cot"]))
                a("```")
                a("</details>")
            a("")
    else:
        a("（无直接命中——见二十问日志的间接信息）")
    tq = py.get("twenty_questions_log") or []
    if tq:
        a("### 二十问假设确认日志（间接重建封口指令）")
        a("")
        for i, t in enumerate(tq, 1):
            ans = (t.get("a") or "").replace("\n", " ")[:200]
            a(f"{i}. **Q**: {t['q'][:80]}…")
            a(f"   **A**: {ans}")
        a("")

    a("## 三、零成本指纹矩阵")
    a("")
    fp = results.get("fingerprint") or {}
    if fp:
        a("### 自曝消息")
        for x in fp.get("self_exposure", []):
            a(f"- `{x['path']}`: “{x['quote']}”")
        a("")
        if fp.get("framework_guess"):
            a(f"- 框架猜测: {', '.join(fp['framework_guess'])}")
        if fp.get("channel_pools_js"):
            a(f"- 首页 JS 渠道池: `{fp['channel_pools_js']}`")
        if fp.get("red_flags"):
            a("- 红旗标记:")
            for r in fp["red_flags"]:
                a(f"  - {r}")
        if fp.get("sibling_sites"):
            a("- 姊妹站线索:")
            for s in fp["sibling_sites"]:
                a(f"  - {s}")
        pricing = fp.get("pricing")
        if pricing:
            a("")
            a("### 公开定价表（/api/models，无需鉴权即可访问）")
            a("")
            a("| model_id | provider | 输入价/1k | 输出价/1k | 币种 | ctx |")
            a("|---|---|---|---|---|---|")
            for m in pricing:
                a(f"| {m.get('model_id')} | {m.get('provider')} | {m.get('input_price_per_1k')} "
                  f"| {m.get('output_price_per_1k')} | {m.get('price_currency')} | {m.get('context_window')} |")
        errs = fp.get("errors") or {}
        if errs:
            a("")
            a("### 错误格式矩阵")
            a("")
            a("| 用例 | HTTP | 响应摘要 |")
            a("|---|---|---|")
            for name, e in errs.items():
                snip = (e.get("snippet") or "").replace("\n", " ")[:120]
                a(f"| {name} | {e.get('code')} | `{snip}` |")
    a("")

    inv = _evidence_inventory(evidence_dir)
    a(f"## 四、证据清单（{len(inv)} 份，全部本地留档）")
    a("")
    a("| # | 文件 | 字节 | 内容摘要 |")
    a("|---|---|---|---|")
    for i, r in enumerate(inv, 1):
        a(f"| {i} | `{r['file']}` | {r['size']} | {r['brief']} |")
    a("")

    a("## 五、结论与建议")
    a("")
    for c in (v.get("clues") or [])[:8]:
        a(f"- [{c.get('category', '?')}] {c.get('text', '')}")
    a("")
    return "\n".join(lines)
