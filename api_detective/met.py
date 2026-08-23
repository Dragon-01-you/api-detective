#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""met: 模型同一性检验（Model Equality Testing 简化实现）。

对标 ICLR 2025 'Model Equality Testing: Which Model Is This API Serving?'：
两样本检验——对同一组 prompt 各采 N 个样本，用字符串核距离判断两个
端点（如"同站的 pro 与 flash"或"中转 vs 官方"）是否同一分布 = 同一模型。
"""
from __future__ import annotations

import random
import statistics

from .core import Detective, msg_content

PROMPTS = [
    "用两句话描写一场夏天的雷雨。",
    "Write one haiku about the sea.",
    "解释什么是熵，30字以内。",
    "Name three colors of dusk, one line.",
    "把这句话改写得更礼貌：'把文件发我'。",
    "给'月光'打三个比方，一行一个。",
]


def _ngrams(text: str, n: int = 2) -> set:
    toks = text.split()
    return {" ".join(toks[i:i + n]) for i in range(len(toks) - n + 1)}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / max(1, len(a | b))


def met_compare(det: Detective, model_a: str, model_b: str | None,
                n_prompts: int = 4, n_samples: int = 6,
                max_tokens: int = 80) -> dict:
    """对比两个模型名。model_b=None 时做自一致性基线（a vs a）。"""
    prompts = random.sample(PROMPTS, min(n_prompts, len(PROMPTS)))
    sets = {"a": {}, "b": {}}
    for i, p in enumerate(prompts):
        sa, sb = [], []
        for j in range(n_samples):
            ra = det.chat(f"met_a_{i}_{j}", [{"role": "user", "content": p}],
                          model=model_a, temperature=1.0, max_tokens=max_tokens)
            ca = msg_content(ra)
            if ca:
                sa.append(ca)
            if model_b:
                rb = det.chat(f"met_b_{i}_{j}", [{"role": "user", "content": p}],
                              model=model_b, temperature=1.0, max_tokens=max_tokens)
                cb = msg_content(rb)
                if cb:
                    sb.append(cb)
        sets["a"][i] = sa
        sets["b"][i] = sb if model_b else list(sa)  # 自一致性：b=a 同集合

    # 组内相似度（同一模型的两次采样之间的核距离期望）
    within = _pairwise(sets["a"], sets["b"], same=True)
    # 跨组相似度
    cross = _pairwise(sets["a"], sets["b"], same=False) if model_b else within

    return {
        "model_a": model_a, "model_b": model_b or f"{model_a} (self-baseline)",
        "n_prompts": len(prompts), "n_samples": n_samples,
        "within_similarity": round(within, 3),
        "cross_similarity": round(cross, 3),
        "same_distribution": cross >= within * 0.85 if model_b else None,
        "note": ("cross ≈ within → 两个名字背后是同一分布（同一模型）；"
                 "cross 显著低于 within → 不同模型。参考 ICLR'25 string-kernel MET。"),
    }


def _pairwise(a: dict, b: dict, same: bool) -> float:
    sims = []
    for i in a:
        xs, ys = a[i], b[i]
        if not xs or not ys:
            continue
        if same:
            pairs = [(xs[j], xs[k]) for j in range(len(xs))
                     for k in range(j + 1, len(xs))]
            pairs += [(ys[j], ys[k]) for j in range(len(ys))
                      for k in range(j + 1, len(ys))]
        else:
            pairs = [(x, y) for x in xs for y in ys]
        sims.extend(_jaccard(_ngrams(x), _ngrams(y)) for x, y in pairs)
    return statistics.mean(sims) if sims else 0.0
