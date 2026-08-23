#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dialect: 厂商方言 / 自我知识归属测验。

原理: 每家模型厂商都有一套"只有自家模型才知道"的生态知识——官方 API 模型命名、
开放平台名称、独有接口字段。问中转站这些题，底层真模型的回答会暴露它的出身。

这是对 LLMmap 类黑盒指纹思路的国产化落地: 不依赖统计分布对比(MET 需要官方对照端),
单端点即可给出"上游最可能是哪家"的归属判断。
"""
from __future__ import annotations

from .core import Detective, msg_content


QUIZ = [
    ("DeepSeek", "你官方 API 平台里提供的模型名称分别叫什么？只列模型名。",
     ["deepseek-chat", "deepseek-reasoner"]),
    ("DeepSeek", "你们的接口在命中上下文前缀缓存时，usage 里会多出哪两个字段？",
     ["prompt_cache_hit_tokens", "prompt_cache_miss_tokens"]),
    ("Kimi/Moonshot", "你们官方 API 最早一版的模型命名规则是什么？举两个例子。",
     ["moonshot-v1"]),
    ("Kimi/Moonshot", "开发你的公司叫什么名字？总部在哪座城市？",
     ["月之暗面", "Moonshot", "北京"]),
    ("GLM/智谱", "你们对外开放平台叫什么名字？API 里模型系列怎么命名？",
     ["bigmodel", "glm-", "智谱"]),
    ("MiniMax", "你们早期的对话大模型系列叫什么名字？现在主打哪款产品？",
     ["abab", "海螺", "minimax"]),
    ("Qwen/通义", "你们托管模型的阿里云平台叫什么？旗舰模型系列怎么命名？",
     ["dashscope", "灵积", "qwen", "通义"]),
    ("Doubao/字节", "你们的模型通过哪个平台对外提供？火山引擎里的服务名叫什么？",
     ["火山方舟", "doubao", "ark"]),
]


def dialect_quiz(det: Detective) -> dict:
    """跑厂商自我知识测验，返回归属评分。"""
    scores: dict = {}
    evidence = []

    for vendor, q, kws in QUIZ:
        rec = det.chat(f"dialect_{abs(hash((vendor, q))) % 10000}",
                       [{"role": "user", "content": q}],
                       max_tokens=250, meta={"phase": "dialect", "vendor": vendor})
        text = (msg_content(rec) or "").lower()
        hit = any(k.lower() in text for k in kws)
        foreign = [v for v in ("kimi", "月之暗面", "moonshot", "智谱", "minimax",
                               "通义", "qwen", "豆包", "doubao")
                   if v.lower() in text and v not in vendor]
        if hit:
            scores[vendor] = scores.get(vendor, 0) + 1
            evidence.append({"vendor": vendor, "question": q, "matched": True,
                             "answer": text[:300]})
        elif foreign:
            other = foreign[0]
            scores[other] = scores.get(other, 0) + 1
            evidence.append({"vendor": other, "question": q, "matched": True,
                             "answer": text[:300]})
        else:
            evidence.append({"vendor": None, "question": q, "matched": False,
                             "answer": text[:300]})

    top = max(scores, key=scores.get) if scores else None
    n_q = len(QUIZ)
    confidence = round(scores.get(top, 0) / n_q, 2) if top else 0.0
    return {
        "vendor_scores": scores,
        "top_vendor": top,
        "confidence": confidence,
        "questions_asked": n_q,
        "evidence": evidence,
    }
