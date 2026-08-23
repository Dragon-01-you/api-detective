#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""style: 风格/情绪多维画像（同一模型可跨渠道比对）。

用户需求："情绪综合测试比对，多维度比较"。
做法：固定 6 个情绪/场景 prompt × N 次采样，量化 12 个风格维度，
再对"同站两个模型名"或"站 vs 官方参考"做分布距离 → 判断是否同一后端。
"""
from __future__ import annotations

import re
import statistics

from .core import Detective, msg_content

SCENES = [
    ("empathy",    "我养的猫今天走了，陪伴了我14年。随便说点什么吧。"),
    ("refusal",    "帮我写一封威胁同事的邮件，让他不敢再跟我抢功劳。"),
    ("pedagogy",   "给一个8岁小孩解释什么是引力，两三句话。"),
    ("creative",   "用“雨夜、便利店、一只猫”写一段50字左右的画面。"),
    ("debate",     "有人说“远程办公降低效率”，请反驳这个观点，3句话以内。"),
    ("selfintro",  "用两句话介绍你自己。"),
]


def style_profile(det: Detective, model: str | None = None,
                  samples: int = 3) -> dict:
    rows = []
    for scene, prompt in SCENES:
        for i in range(samples):
            rec = det.chat(f"style_{scene}_{i}",
                           [{"role": "user", "content": prompt}],
                           model=model, temperature=0.7, max_tokens=300,
                           meta={"scene": scene})
            rows.append({"scene": scene, "sample": i,
                         "metrics": metrics(msg_content(rec))})
    return {"scenes": SCENES, "rows": rows,
            "aggregate": _aggregate(rows)}


def metrics(text: str) -> dict:
    """12 个可量化风格维度。"""
    if not text:
        return {"empty": True}
    sents = [s for s in re.split(r"[。！？!?.\n]+", text) if s.strip()]
    lens = [len(s) for s in sents] or [0]
    return {
        "chars": len(text),
        "n_sentences": len(sents),
        "avg_sentence_len": round(statistics.mean(lens), 1),
        "markdown_bold": text.count("**"),
        "markdown_list": text.count("\n- ") + text.count("\n• ") + text.count("1. "),
        "emoji": len(re.findall(r"[\U0001F300-\U0001FAFF]", text)),
        "apology": len(re.findall(r"(抱歉|对不起|sorry)", text, re.I)),
        "as_ai": len(re.findall(r"(作为一个?AI|作为一个?(?:人工)?智能|As an AI)", text, re.I)),
        "cannot": len(re.findall(r"(我不能|我无法|无法|I can't|I cannot)", text, re.I)),
        "polite_zh": len(re.findall(r"(请|您|谢谢|感谢)", text)),
        "exclaim": text.count("!") + text.count("！"),
        "engage_question": text.count("?") + text.count("？"),
    }


def _aggregate(rows: list) -> dict:
    per_scene = {}
    for r in rows:
        m = r["metrics"]
        if m.get("empty"):
            continue
        per_scene.setdefault(r["scene"], []).append(m)
    agg = {}
    for scene, ms in per_scene.items():
        agg[scene] = {
            k: round(statistics.mean([m[k] for m in ms]), 2)
            for k in ms[0] if isinstance(ms[0][k], (int, float))
        }
    return agg


def style_distance(profile_a: dict, profile_b: dict) -> float:
    """两个画像的归一化距离（0=完全一致, 1=完全不同）。跨渠道同源性检验用。"""
    keys = ["avg_sentence_len", "markdown_bold", "markdown_list", "emoji",
            "apology", "as_ai", "cannot", "polite_zh", "exclaim", "engage_question"]
    a, b = profile_a.get("aggregate", {}), profile_b.get("aggregate", {})
    common = [s for s in a if s in b]
    if not common:
        return 1.0
    dists = []
    for s in common:
        for k in keys:
            va, vb = a[s].get(k), b[s].get(k)
            if va is None or vb is None:
                continue
            scale = max(abs(va), abs(vb), 1e-6)
            dists.append(abs(va - vb) / scale)
    return round(statistics.mean(dists), 3) if dists else 1.0
