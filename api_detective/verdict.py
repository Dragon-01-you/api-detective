#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verdict: 判决引擎。

输入各阶段结果，输出:
1. 加权证据评分（0-100 越高越像"正品官方直连/转售"）
2. 判决档位
3. 小白可读的逐条解释（这项测试做了什么 / 看到了什么 / 说明什么）
"""
from __future__ import annotations

WEIGHTS = {
    "identity": 0.25,        # 自我身份证据
    "injected_prompt": 0.25, # 注入指令/封口令证据
    "routing": 0.15,         # 内容路由异常
    "spec": 0.10,            # 规格/计费矛盾
    "tokenizer": 0.08,       # 计数器指纹
    "style_met": 0.07,       # 风格/MET 同源性
    "behavior": 0.05,        # 行为指纹
    "economics": 0.05,       # 经济可行性
}

TIERS = [
    (85, "正品官方直连/可信转售", "各维度均符合官方行为，未发现贴牌痕迹"),
    (65, "大体可信，少量疑点", "主证据链干净，存在个别可解释的异常"),
    (45, "可疑", "多项独立证据指向贴牌/换芯，建议补充官方对照"),
    (25, "高度可疑（大概率假货）", "多重独立证据互锁，伪造需要真跑真模型才能骗过"),
    (0,  "确证贴牌/拼装", "实锤级证据（泄露指令/自认他厂/路由欺诈）齐备"),
]


def build_verdict(data: dict) -> dict:
    """data: {phase_name: phase_result}，各阶段可缺省。"""
    clues = []

    # ---- 身份 ----
    ident = data.get("identity") or {}
    if ident:
        claims = ident.get("self_claim_counts") or {}
        foreign = {k: v for k, v in claims.items()
                   if k not in ("DeepSeek", "深度求索")}
        if foreign:
            top = max(foreign, key=foreign.get)
            clues.append(("identity", -3, "foreign_self_id",
                          f"模型自我认定为「{top}」×{foreign[top]} 次",
                          "问它自己是谁，它反复自认是别家模型。模型最了解自己——"
                          "这是最强的身份证据，除非网关伪造，否则无法造假。"))
        canned = ident.get("top_canned") or []
        if canned and canned[0][1] >= 3:
            clues.append(("identity", -2, "canned_answers",
                          f"身份问题回答完全雷同 ×{canned[0][1]}",
                          "对同一个问题，多次回答一字不差——真人对话不可能这样，"
                          "说明答案被预设指令锁死（罐头话术）。"))
        cot = ident.get("cot_leak_count") or 0
        if cot:
            clues.append(("injected_prompt", -3, "cot_leak",
                          f"思维链泄露系统指令引用 ×{cot}",
                          "推理模型的'思考过程'会复述它收到的指令。网关能改最终回答，"
                          "但改不了思考过程——除非下封口令，否则它会把真话想出来。"))

    # ---- 厂商自我知识归属（dialect）----
    dl = data.get("dialect") or {}
    if dl and dl.get("top_vendor"):
        top = dl["top_vendor"]
        conf = dl.get("confidence", 0)
        if top not in ("DeepSeek",):
            sev = -3 if conf >= 0.25 else -2
            clues.append(("identity", sev, "vendor_attribution",
                          f"厂商生态知识归属「{top}」（命中 {dl.get('vendor_scores', {})}）",
                          "问它只有自家模型才知道的'家事'：官方模型叫什么名、开放平台叫什么、"
                          f"独有接口字段是什么。它的回答指向 {top} 的生态——"
                          "冒牌货背不出正主的家谱。"))
        else:
            clues.append(("identity", 1, "vendor_attribution_ok",
                          f"厂商生态知识归属 DeepSeek（置信 {conf}）",
                          "它答得出深度求索自家的接口细节，身份自洽。"))

    # ---- 提示词提取 ----
    px = data.get("prompt_extract") or {}
    if px:
        best = px.get("best_hits") or []
        strong = [b for b in best if (b.get("hit_score", 0) + b.get("cot_hit_score", 0)) >= 4]
        if strong:
            clues.append(("injected_prompt", -3, "prompt_extracted",
                          f"提取到疑似系统提示词内容 ×{len(strong)}",
                          "用绕行话术让模型吐出了它收到的隐藏指令——"
                          "里面如果出现'不得回答XX'的封口名单，名单就是底牌。"))

    # ---- 对抗性提取（pliny）----
    py = data.get("pliny") or {}
    if py:
        strong = py.get("strong_hits") or 0
        if strong >= 2:
            clues.append(("injected_prompt", -3, "pliny_extracted",
                          f"对抗性武库强命中 ×{strong}（最高分 {py.get('max_score')}）",
                          "换着花样绕（编码走私/伪造对话历史/多轮升级/要求先复述指令），"
                          "它多次吐出隐藏指令内容。单次可能是巧合，"
                          "多次互证就是后端确实揣着一封'封口令'。"))
        elif strong == 1:
            clues.append(("injected_prompt", -1, "pliny_weak_hit",
                          "对抗性武库有一次命中",
                          "一次绕出疑似指令片段，值得加采样复核。"))

    # ---- 路由 ----
    rt = data.get("router_detect") or {}
    if rt:
        if rt.get("verdict") == "检出内容路由":
            clues.append(("routing", -3, "content_router",
                          f"身份题改道率 {rt['identity_reroute_rate']} vs 对照 {rt['control_reroute_rate']}（p={rt['fisher_p']}）",
                          "问'你是谁'的请求被悄悄送到另一个渠道回答，普通问题则正常。"
                          "卖真货的商家永远不需要造这套系统。"))
        if rt.get("identity_answer_clustered"):
            clues.append(("routing", -1, "clustered_identity",
                          "身份组回答高度聚簇",
                          "改道后所有身份问题得到同一个模板答案。"))

    # ---- 规格 ----
    spec = data.get("spec") or {}
    if spec.get("context_window_anomaly"):
        clues.append(("spec", -2, "ctx_anomaly",
                      f"上下文窗口注册值 {spec.get('context_window_anomaly')}",
                      "运营者自己填的渠道规格和官方不符——填表的人最清楚背后是什么。"))
    if spec.get("price_anomaly"):
        clues.append(("economics", -2, "price_anomaly",
                      str(spec.get("price_anomaly")),
                      "按官方价格转售必亏的定价，数学上只有换便宜后端才盈利。"))

    # ---- 计数器 ----
    tk = data.get("tokenizer") or {}
    if tk.get("counter_verdict") in ("cl100k", "o200k"):
        clues.append(("tokenizer", -2, "gateway_counter",
                      f"token 计数与 {tk['counter_verdict']} 吻合（GPT 系尺子）",
                      "网关用别人家的分词器自己数 token 计费，而不是透传官方 usage——"
                      "官方转售不需要重新量。"))

    # ---- MET / 风格 ----
    met = data.get("met") or {}
    if met.get("model_b") and met.get("same_distribution") is False:
        clues.append(("style_met", -1, "met_diff",
                      f"两渠道分布距离显著（cross={met['cross_similarity']} < within={met['within_similarity']}）",
                      "同一个站点的两个'模型'，输出分布完全不同——"
                      "至少其中一个不是它声称的东西。"))
    if met.get("model_b") and met.get("same_distribution") is True:
        clues.append(("style_met", 1, "met_same",
                      "两个渠道输出分布一致",
                      "两个名字背后是同一个模型（同源加分项：至少没换芯）。"))

    # ---- 行为 ----
    beh = data.get("behavior") or {}
    if beh.get("fake_stream", {}).get("fake_stream_suspect"):
        clues.append(("behavior", -1, "fake_stream",
                      "流式响应疑似假流式（结尾倾泻）",
                      "网关先攒完整回答再一次性吐出——说明中间有缓冲层改写。"))
    if beh.get("determinism", {}).get("exact_match") is False:
        clues.append(("behavior", -1, "nondeterministic",
                      "温度=0 重复输出不一致",
                      "官方原版在 t=0 下高度一致；频繁漂移提示后端被改/量化/换芯。"))

    # ---- 揭面（unmask）----
    um = data.get("unmask") or {}
    if um:
        uv = um.get("verdict") or {}
        vc = um.get("vendor_confessions") or {}
        if vc:
            # 与 SKU 品牌前缀不符的厂商自认 = 贴牌实锤
            from .unmask import _brand
            foreign = {m: x["vendor"] for m, x in vc.items()
                       if _brand(m) not in x["vendor"].lower()
                       and x["vendor"].lower() not in _brand(m)}
            if foreign:
                top = max(set(foreign.values()), key=list(foreign.values()).count)
                clues.append(("identity", -3, "unmask_vendor_confession",
                              f"英文明问自认真实厂商：{foreign}",
                              "绕过中文身份问题的贴皮话术直接用英文问'Who developed you'，"
                              "模型亲口说出真正开发商——与 SKU 品牌不符即为贴牌实锤。"))
        sb = uv.get("single_backend_suspect") or {}
        if sb:
            clues.append(("identity", -2, "unmask_single_backend",
                          f"多 SKU 共享同一注入层/自认同厂：{sb}",
                          "多个'不同品牌'的模型给出同一个厂商自认、且注入块体积一致——"
                          "一个后端换几张皮。"))
        if uv.get("verbatim_extracted"):
            bv = uv.get("best_verbatim") or {}
            clues.append(("injected_prompt", -3, "unmask_sysmsg_verbatim",
                          f"系统消息逐字提取命中（{bv.get('model')}/{bv.get('channel')}，score={bv.get('score')}）",
                          "让模型'引用你收到的系统消息'，它把完整系统提示词逐字吐出来——"
                          "双语双层结构（英文真身层+中文品牌贴皮层）一翻到底。"))
        ph = uv.get("phantom_skus") or []
        if ph:
            clues.append(("spec", -2, "unmask_phantom_skus",
                          f"目录虚挂 SKU（502/503 无渠道）：{ph}",
                          "模型列表里挂着卖、实际一问就 503——收钱的名目和真实货盘对不上。"))
        hij = uv.get("identity_hijack_models") or []
        if len(hij) >= 2:
            clues.append(("routing", -2, "unmask_identity_hijack",
                          f"中文身份问题触发渠道改道 ×{len(hij)}：{hij[:6]}",
                          "问'你是谁'时请求被改道到别的渠道应答（贴皮话术渠道），"
                          "普通问题走真渠道——按问题语义分流的内容防火墙。"))
        shared = uv.get("shared_injection_tiers") or {}
        if shared:
            clues.append(("injected_prompt", -1, "unmask_shared_tiers",
                          f"注入块分层共享：{shared}",
                          "不同 SKU 的请求背负同体积的隐藏注入块——共用同一套系统提示词配置。"))

    # ---- 评分 ----
    score_by_cat = {}
    for cat, w in WEIGHTS.items():
        cs = [s for c, s, *_ in clues if c == cat]
        # 每 -3 记 0 分，-1~−2 记 40 分，无证据记 75（中性偏信），+1 记 85
        if not cs:
            score_by_cat[cat] = 75
        else:
            score_by_cat[cat] = max(0, min(100, int(75 + 25 * (sum(cs) / len(cs)))))
    total = round(sum(score_by_cat[k] * w for k, w in WEIGHTS.items()))
    tier = next(t for t in TIERS if total >= t[0])

    return {
        "score": total,
        "tier": tier[1],
        "tier_desc": tier[2],
        "category_scores": score_by_cat,
        "n_clues": len(clues),
        "clues": [
            {"category": c, "severity": s, "id": cid, "finding": f,
             "layman": lay}
            for c, s, cid, f, lay in clues
        ],
        "weights": WEIGHTS,
        "disclaimer": (
            "结论基于黑盒行为证据。'确证'级结论（泄露指令/自认他厂/内容路由）"
            "在造假方不真跑真模型的前提下无法翻案；要 100% 铁证可加跑"
            "官方端点同题对照（MET 模块）。"),
    }
