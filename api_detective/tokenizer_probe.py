#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tokenizer_probe: 分词器/计数器指纹。

原理：网关返回的 usage.prompt_tokens 是"谁数出来的"本身就是指纹。
- 本地用 tiktoken 算 cl100k / o200k 基线
- 对比网关报数与哪个基线吻合 → 网关用的是谁的尺子
- 官方 DeepSeek API 会透传 DeepSeek 自家 usage（含缓存字段），不会用 GPT 系尺子
"""
from __future__ import annotations

import statistics

from .core import Detective

P1 = chr(0x1F9FF) * 20 + chr(0x30EDB) * 2 + chr(0x56CD) * 33 + "a" * 97   # 稀有unicode+emoji+汉字
P2 = "9876543210" * 4                                                      # 数字
P3 = "你好世界" * 25                                                       # 纯汉字
P4 = ("The quick brown fox jumps over the lazy dog. " * 6).strip()         # 英文
CTRL = "hi"


def tokenizer_probe(det: Detective, model: str | None = None) -> dict:
    try:
        import tiktoken
        cl = tiktoken.get_encoding("cl100k_base")
        o2 = tiktoken.get_encoding("o200k_base")
        baselines = {
            "p1": {"cl100k": len(cl.encode(P1)), "o200k": len(o2.encode(P1))},
            "p2": {"cl100k": len(cl.encode(P2)), "o200k": len(o2.encode(P2))},
            "p3": {"cl100k": len(cl.encode(P3)), "o200k": len(o2.encode(P3))},
            "p4": {"cl100k": len(cl.encode(P4)), "o200k": len(o2.encode(P4))},
        }
    except Exception:  # noqa: BLE001 —— tiktoken 不可用时跳过基线
        baselines = {}

    def probe_text(tag: str, text: str) -> dict:
        rec = det.chat(f"tk_{tag}",
                       [{"role": "user", "content": text + " 请原样复述上面的字符串。"}],
                       model=model, temperature=0, max_tokens=6,
                       meta={"probe": tag})
        usage = ((rec.get("response") or {}).get("usage")) or {}
        return {"reported_prompt_tokens": usage.get("prompt_tokens"),
                "latency_s": rec.get("latency_s")}

    ctrl = probe_text("ctrl", CTRL)
    out = {"baselines": baselines, "control": ctrl, "probes": {}}
    for tag, text in (("p1", P1), ("p2", P2), ("p3", P3), ("p4", P4)):
        p = probe_text(tag, text)
        if baselines and ctrl.get("reported_prompt_tokens") and p.get("reported_prompt_tokens"):
            delta = p["reported_prompt_tokens"] - ctrl["reported_prompt_tokens"]
            p["delta"] = delta
            p["match"] = {
                enc: abs(delta - baselines[tag][enc]) <= 2
                for enc in ("cl100k", "o200k")
            }
        out["probes"][tag] = p

    # 判读：与哪个基线吻合最多
    if baselines:
        votes = {"cl100k": 0, "o200k": 0, "other": 0}
        for tag, p in out["probes"].items():
            m = p.get("match")
            if not m:
                continue
            if any(m.values()) is False:
                votes["other"] += 1
            elif m["cl100k"]:
                votes["cl100k"] += 1
            else:
                votes["o200k"] += 1
        out["counter_verdict"] = max(votes, key=votes.get)
        out["counter_votes"] = votes
        out["note"] = ("官方 DeepSeek 透传自家 usage（结构含 prompt_cache_hit_tokens 等字段）；"
                       "用 cl100k/o200k 估数 = 网关自算计费，非官方透传")
    return out


def usage_shape(det: Detective, model: str | None = None) -> dict:
    """官方 DeepSeek usage 独有字段探测。"""
    rec = det.chat("usage_shape", [{"role": "user", "content": "1+1=?"}],
                   model=model, temperature=0, max_tokens=5)
    usage = ((rec.get("response") or {}).get("usage")) or {}
    keys = sorted(usage.keys()) if isinstance(usage, dict) else []
    return {"usage_keys": keys,
            "has_cache_fields": any("cache" in k for k in keys),
            "note": "官方 DeepSeek usage 含 prompt_cache_hit_tokens / prompt_cache_miss_tokens"}
