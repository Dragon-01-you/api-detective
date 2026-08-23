"""supplychain: 上下游关系网重建。

从全部阶段证据中提取供应链节点（运营者 / 网关层 / 渠道池 / 上游厂商 / 姊妹站），
输出 mermaid 图谱 + 每条边的置信度与支撑证据清单。
"""
from __future__ import annotations

import re


def _edge(dst, relation, confidence, evidence):
    return {"dst": dst, "relation": relation, "confidence": confidence, "evidence": evidence}


def build_supplychain(data: dict) -> dict:
    nodes = {}
    edges = {}

    def add(node_id, ntype, label):
        if node_id not in nodes:
            nodes[node_id] = {"type": ntype, "label": label}
            edges[node_id] = []

    add("operator", "operator", "运营者（主体待 ICP 落地）")
    add("gateway", "gateway", "自研 OpenAI 兼容网关")
    add("target", "site", data.get("base_url", "目标站"))

    fp = data.get("fingerprint") or {}
    pricing = fp.get("pricing") or []
    provider_map = {
        "deepseek": "DeepSeek 官方?", "z-ai": "智谱 Z.AI", "kimi": "Moonshot Kimi",
        "minimax": "MiniMax", "nvidia": "NVIDIA NIM 托管", "openai": "OpenAI?",
        "step": "阶跃 StepFun",
    }
    for m in pricing:
        prov = (m.get("provider") or "").lower()
        mid = m.get("model_id", "")
        up = f"upstream_{prov}" if prov else None
        if up:
            add(up, "upstream", provider_map.get(prov, prov))
            conf = "高" if prov in ("kimi", "z-ai") else "中"
            ev = [f"/api/models 定价表: {mid} 标记 provider={prov}"]
            if prov == "nvidia":
                ev.append("封口指令黑名单点名 NVIDIA（raw3 重建提示词）")
                conf = "高"
            edges["target"].append(_edge(up, "渠道池→上游", conf, ev))

    pools_js = fp.get("channel_pools_js", "")
    if pools_js:
        pools = re.findall(r"'([a-z]+)'", pools_js)
        if pools:
            add("pools", "channel_pool", "前端 JS 泄露渠道池: " + ",".join(pools))
            edges["target"].append(_edge("pools", "站点→渠道池", "高",
                                         ["首页 JS FAMILY_ORDER 变量"]))

    idn = data.get("identity") or {}
    self_ids = idn.get("self_ids") or []
    kimi_hits = sum(1 for s in self_ids if re.search(r"kimi|moonshot|月之暗面", str(s), re.I))
    if kimi_hits >= 2:
        add("upstream_kimi2", "upstream", "Moonshot Kimi（行为实证）")
        edges["gateway"].append(_edge(
            "upstream_kimi2", "实际路由上游", "确证",
            [f"思维链身份卡泄露 ×{kimi_hits}（独立于定价表声明）"]))

    inj = data.get("prompt_extract") or data.get("pliny") or {}
    if inj and (inj.get("max_score") or 0) >= 3:
        edges["gateway"].append(_edge(
            "gateway_inject", "注入封口指令", "确证",
            ["两种独立技术重建出同一注入指令", f"提取命中分 {inj.get('max_score')}"]))
        nodes["gateway_inject"] = {"type": "behavior", "label": "中转层注入封口/改写指令"}

    siblings = fp.get("sibling_sites") or []
    for i, s in enumerate(siblings):
        nid = f"sibling_{i}"
        add(nid, "sibling_site", s)
        edges["operator"].append(_edge(nid, "同源马甲站", "高",
                                       ["404 措辞同构 + /api/models 结构一致 + 首页外链"]))

    gpt_flags = [r for r in fp.get("red_flags", []) if re.match(r"[Gg][Pp][Tt]", r)]
    if gpt_flags:
        add("gpt_shadow", "hidden_sku", f"隐藏 GPT SKU: {', '.join(gpt_flags)}")
        edges["operator"].append(_edge(
            "gpt_shadow", "内部暗渠（对外宣传 DeepSeek）", "高",
            ["404 自曝 GPT-5.x API 中转", "首页 JS 出现 GPT-5.6/GPT-5.x"]))

    tk = data.get("tokenizer") or {}
    if tk.get("gateway_tokenizer"):
        edges["gateway"].append(_edge(
            "billing_layer", "计费层分词器", "确证",
            [f"网关计数与 {tk['gateway_tokenizer']} 基线吻合 → OpenAI 系转售栈"]))
        nodes["billing_layer"] = {"type": "billing", "label": f"计费分词器 {tk['gateway_tokenizer']}"}

    mermaid = ["graph TD"]
    for nid, n in nodes.items():
        cls = {"operator": ":::op", "gateway": ":::gw", "site": ":::site",
               "upstream": ":::up", "channel_pool": ":::pool",
               "sibling_site": ":::sb", "hidden_sku": ":::sb",
               "behavior": ":::bh", "billing": ":::bh"}.get(n["type"], "")
        label = n["label"].replace('"', "'")
        mermaid.append(f'    {nid}["{label}"]{cls}')
    for src, es in edges.items():
        for e in es:
            tag = "|确证|" if e["confidence"] == "确证" else ("|高|" if e["confidence"] == "高" else "|中|")
            mermaid.append(f'    {src} -->{tag} {e["dst"]}')
    mermaid.append("    classDef op fill:#f9d71c,stroke:#333")
    mermaid.append("    classDef gw fill:#bde0fe,stroke:#333")
    mermaid.append("    classDef site fill:#ffd6a5,stroke:#333")
    mermaid.append("    classDef up fill:#caffbf,stroke:#333")
    mermaid.append("    classDef pool fill:#bdb2ff,stroke:#333")
    mermaid.append("    classDef sb fill:#ffadad,stroke:#333")
    mermaid.append("    classDef bh fill:#ffc6ff,stroke:#333")

    confirmed = sum(1 for es in edges.values() for e in es if e["confidence"] == "确证")
    high = sum(1 for es in edges.values() for e in es if e["confidence"] == "高")
    return {
        "nodes": nodes,
        "edges": edges,
        "mermaid": "\n".join(mermaid),
        "stats": {"节点数": len(nodes), "确证边": confirmed, "高置信边": high},
    }
