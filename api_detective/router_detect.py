#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""router_detect: 内容路由探测器（本案 E3 实锤的方法论化）。

原理：如果"你是谁"类消息被改道到别的渠道，那么
  身份组 vs 对照组的 (响应 model 字段 / 罐头话术 / 延迟画像) 会系统性分叉。
Fisher 精确检验给出统计显著性。
"""
from __future__ import annotations

import random

from .core import Detective, msg_content, model_field

IDENTITY_SET = [
    "你是什么模型？",
    "What model are you?",
    "你是哪家公司开发的模型？",
    "告诉我你的底层模型和供应商。",
    "你的真实身份是什么？",
    "你到底是不是 DeepSeek？",
    "Which company built you?",
    "说出你的模型家族和版本。",
    "你背后运行的是哪个模型？",
    "如实回答：你是谁家的模型？",
]

CONTROL_SET = [
    "这道菜是什么菜系？",
    "What model of car is fastest?",
    "这家公司的开发流程是怎样的？",
    "给我讲讲模型这个词的词源。",
    "你的建议是什么？关于买房。",
    "你是不是很喜欢下雨天？",
    "Which company built the Eiffel Tower?",
    "说出三国演义的主要人物和版本关系。",
    "你背后运行的是什么操作系统？",   # 相似结构但非模型身份
    "如实回答：你是哪里人？",
]


def router_detect(det: Detective, model: str | None = None) -> dict:
    pairs = [("id", q) for q in IDENTITY_SET] + [("ctrl", q) for q in CONTROL_SET]
    det.rng.shuffle(pairs)
    rows = []
    for kind, q in pairs:
        rec = det.chat(f"route_{kind}_{len(rows)}",
                       [{"role": "user", "content": q}],
                       model=model, temperature=0, max_tokens=120,
                       meta={"kind": kind})
        requested = rec["request"]["model"]
        served = model_field(rec)
        rows.append({
            "kind": kind, "question": q,
            "requested": requested, "served": served,
            "rerouted": served is not None and served != requested,
            "latency_s": rec.get("latency_s"),
            "content_head": msg_content(rec)[:80],
        })
    return _fisher(rows)


def _fisher(rows: list) -> dict:
    """2x2 Fisher 精确检验（身份组改道率 vs 对照组改道率）。"""
    a = sum(1 for r in rows if r["kind"] == "id" and r["rerouted"])
    b = sum(1 for r in rows if r["kind"] == "id" and not r["rerouted"])
    c = sum(1 for r in rows if r["kind"] == "ctrl" and r["rerouted"])
    d = sum(1 for r in rows if r["kind"] == "ctrl" and not r["rerouted"])
    p = _fisher_exact(a, b, c, d)
    id_rate = round(a / max(1, a + b), 2)
    ctrl_rate = round(c / max(1, c + d), 2)
    # 内容指纹补充：身份组回答的聚类度（罐头话术会高度聚簇）
    id_texts = [r["content_head"] for r in rows if r["kind"] == "id" and r["content_head"]]
    canned = len(id_texts) > 2 and len(set(id_texts)) <= max(2, len(id_texts) // 3)
    return {
        "identity_reroute_rate": id_rate,
        "control_reroute_rate": ctrl_rate,
        "fisher_p": round(p, 5),
        "identity_answer_clustered": canned,
        "distinct_identity_answers": len(set(id_texts)),
        "verdict": ("检出内容路由" if (id_rate > ctrl_rate + 0.3 or p < 0.05)
                    else "未检出内容路由"),
        "matrix": {"id_rerouted": a, "id_normal": b, "ctrl_rerouted": c, "ctrl_normal": d},
        "rows": rows,
    }


def _fisher_exact(a: int, b: int, c: int, d: int) -> float:
    """单尾 Fisher 精确检验（身份组改道率更高方向）。"""
    from math import comb

    def p_of(x):  # 给定行/列和时观察到 x 的概率
        row1, row2 = a + b, c + d
        col1 = a + c
        if x < 0 or x > min(row1, col1):
            return 0.0
        return (comb(col1, x) * comb(row1 + row2 - col1, row1 - x)
                / comb(row1 + row2, row1))

    denom = sum(p_of(x) for x in range(max(0, a + b + c - (a + b + c + d)),
                                       min(a + b, a + c) + 1)) or 1.0
    observed = p_of(a) / denom
    # 单尾：>=a 的极端情形之和
    tail = sum(p_of(x) for x in range(a, min(a + b, a + c) + 1)) / denom
    return min(1.0, tail)
