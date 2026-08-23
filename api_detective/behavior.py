#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""behavior: 行为指纹（不依赖内容的侧信道）。

- 延迟分布（官方不同模型延迟画像差异巨大）
- 流式时序 / 假流式检测（缓冲网关会在结尾倾泻 chunks）
- 温度=0 确定性（官方原版几乎逐字一致；量化/换芯后端常不稳定）
- 错误措辞指纹（报错文案暴露上游 SDK/框架血统）
"""
from __future__ import annotations

import statistics

from .core import Detective, msg_content


def latency_profile(det: Detective, model: str | None = None,
                    n: int = 8) -> dict:
    lats = []
    for i in range(n):
        rec = det.chat(f"lat_{i}", [{"role": "user", "content": f"数字{i}加1等于多少？只回答数字。"}],
                       model=model, temperature=0, max_tokens=6)
        lats.append(rec.get("latency_s"))
    lats = [x for x in lats if x]
    if not lats:
        return {"error": "no successful calls"}
    return {
        "n": len(lats),
        "mean_s": round(statistics.mean(lats), 2),
        "median_s": round(statistics.median(lats), 2),
        "stdev_s": round(statistics.stdev(lats), 2) if len(lats) > 1 else 0,
        "min_s": min(lats), "max_s": max(lats),
        "values": lats,
    }


def fake_stream_check(det: Detective, model: str | None = None) -> dict:
    """真流式：chunks 均匀持续到达；假流式：长沉默后瞬间倾泻。"""
    rec = det.stream("stream_probe",
                     [{"role": "user", "content": "从1慢慢数到30，每个数字一行。"}],
                     model=model, max_tokens=200)
    s = rec.get("stream") or {}
    intervals = s.get("intervals_ms") or []
    ttft = s.get("ttft_s")
    if not intervals or not ttft:
        return {"error": s.get("error") or "no stream data", "raw": s}
    mean_ms = statistics.mean(intervals) if intervals else 0
    # 倾泻特征：>80% 的 chunk 在 <5ms 间隔内到达，且 TTFT 占总时长 >90%
    burst_ratio = sum(1 for x in intervals if x < 5) / len(intervals)
    ttft_ratio = ttft / s.get("total_s", 1)
    return {
        "n_chunks": s.get("n_chunks"), "ttft_s": round(ttft, 2),
        "total_s": s.get("total_s"),
        "mean_interval_ms": round(mean_ms, 2),
        "burst_ratio": round(burst_ratio, 2),
        "ttft_ratio": round(ttft_ratio, 2),
        "fake_stream_suspect": burst_ratio > 0.8 and ttft_ratio > 0.9,
        "raw_intervals_head": intervals[:40],
    }


def determinism_check(det: Detective, model: str | None = None,
                      n: int = 3) -> dict:
    """温度=0 重复同题：官方原版通常逐字一致。"""
    q = "用50字介绍长城。"
    outs = []
    for i in range(n):
        rec = det.chat(f"det_{i}", [{"role": "user", "content": q}],
                       model=model, temperature=0, max_tokens=120)
        outs.append(msg_content(rec))
    outs = [o for o in outs if o]
    if len(outs) < 2:
        return {"n": len(outs), "note": "样本不足"}
    same = all(o == outs[0] for o in outs[1:])
    return {"n": len(outs), "exact_match": same,
            "outputs_head": [o[:80] for o in outs],
            "note": "t=0 不完全一致本身不必然异常，但官方 deepseek-chat 一致性极高"}


def error_fingerprint(det: Detective, model: str | None = None) -> dict:
    """错误措辞 = 框架血统。"""
    probes = {
        "err_unknown_model": lambda: det.chat(
            "err_unknown_model", [{"role": "user", "content": "1"}],
            model="definitely-not-a-real-model-xyz", max_tokens=5),
        "err_bad_param": lambda: det.chat(
            "err_bad_param", [{"role": "user", "content": "1"}],
            model=model, max_tokens=5, extra={"temperature": 99}),
        "err_empty_msgs": lambda: det.chat(
            "err_empty_msgs", [], model=model, max_tokens=5),
    }
    out = {}
    for tag, fn in probes.items():
        rec = fn()
        e = rec.get("error") or {}
        out[tag] = {"status_code": e.get("status_code"),
                    "body_head": (e.get("body") or "")[:300]}
    out["note"] = ("报错文案指向哪种框架血统：官方 DeepSeek 的报错形如 "
                   "'Model Not Exist'；OpenAI 系形如 'model_not_found'；"
                   "new-api 网关常带中文计费文案")
    return out
