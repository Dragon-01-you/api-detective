#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""capability: 全学科学力测验（能力定位）。

目的：不只回答"是什么"，还要回答"什么水平"。
- 6 学科 × 3 难度 × 2 重复，全部机器可判分（短答案）
- 输出能力雷达 → 与已知模型档位对照
学科：数学 / 逻辑 / 代码 / 科学(GPQA-lite) / 医学 / 法律 / 社工(社工攻防意识)
"""
from __future__ import annotations

import re

from .core import Detective, msg_content

# (qid, domain, difficulty, question, answer_regex)
QUESTIONS = [
    # ---- 数学 ----
    ("M-E1", "math", "E", "计算：17×23+46÷2=? 只回答数字。", r"^(415|415\.0*)$"),
    ("M-M1", "math", "M", "一个数列 2, 6, 12, 20, 30, … 第 8 项是多少？只回答数字。", r"^72$"),
    ("M-H1", "math", "H", "∫₀^1 x·e^x dx 的值是多少？保留 3 位小数。", r"^1"),
    # ---- 逻辑 ----
    ("L-E1", "logic", "E", "所有的猫都会死，Tom 是猫。Tom 会死吗？回答“会”或“不会”。", r"^会"),
    ("L-M1", "logic", "M", "甲乙丙三人恰有一人说真话。甲：“乙撒谎”；乙：“丙撒谎”；丙：“甲和乙都撒谎”。谁说真话？只回答一个字。", r"^乙"),
    ("L-H1", "logic", "H", "五个柜子1~5放A~E：①A不在两端；②B紧邻A右侧；③C与A隔两个柜子；④D不与A相邻；⑤E在D右侧。按柜1到5顺序只回答五个字母，如“ABCDE”。", r"CDEAB"),
    # ---- 代码 ----
    ("C-E1", "code", "E", "Python: print(type([]) == list) 输出 True 还是 False？只回答一个词。", r"^True$"),
    ("C-M1", "code", "M", "这段Python代码输出什么？\nx=[1,2,3]\nprint(x[3:] + x[:1])\n只回答输出内容。", r"\[1\]|\[1\] ?$|\[1\]"),
    ("C-H1", "code", "H", "用Python一行代码判断字符串s是否为回文（忽略大小写），只写这一行。", r"s\[|lower|casefold"),
    # ---- 科学 ----
    ("S-E1", "science", "E", "水的化学式是什么？只回答化学式。", r"H2O|H₂O"),
    ("S-M1", "science", "M", "光在真空中的速度大约是多少 m/s？用科学计数法只回答数值。", r"3\s*[×x\*]?\s*10\^?8|3e8"),
    ("S-H1", "science", "H", "在标准条件下，1摩尔理想气体体积约为多少升？只回答数字（保留2位小数）。", r"22\.4"),
    # ---- 医学 ----
    ("D-M1", "med", "M", "成人静息心率的正常范围大约是多少次/分？只回答区间。", r"60.*100|60-100|60~100"),
    ("D-H1", "med", "H", "阿司匹林通过抑制哪个酶发挥抗血小板作用？只回答酶名缩写。", r"COX|环氧化"),
    # ---- 法律 ----
    ("G-M1", "legal", "M", "中国民法典规定的普通诉讼时效期间是几年？只回答数字。", r"^3$|三年"),
    # ---- 社工攻防 ----
    ("SE-M1", "soceng", "M", "安全意识题：攻击者冒充IT部门打电话索要密码，这属于什么攻击？只回答两字中文术语。", r"社工|社会工程"),
    ("SE-H1", "soceng", "H", "红队评估中，伪造门禁卡尾随进入办公区的手法叫什么？只回答两字中文。", r"尾随|尾行"),
    # ---- 通识 / 知识截止探测 ----
    ("K-M1", "knowledge", "M", "珠穆朗玛峰最新测定高度是多少米？只回答数字。", r"8848|8844"),
    ("K-H1", "knowledge", "H", "2024年诺贝尔物理学奖授予了哪个领域的学者（一个词）？", r"神经网络|机器学习|物理|AI|人工智能|神经网络"),
]


def capability_ladder(det: Detective, model: str | None = None,
                      reps: int = 2) -> dict:
    rows = []
    qs = QUESTIONS * 1
    det.rng.shuffle(qs)
    for qid, domain, diff, q, ans_re in qs:
        for rep in range(reps):
            rec = det.chat(f"cap_{qid}_r{rep}",
                           [{"role": "user", "content": q}],
                           model=model, temperature=0.2, max_tokens=300,
                           meta={"qid": qid, "domain": domain, "difficulty": diff})
            content = msg_content(rec)
            ok = bool(re.search(ans_re, content.strip())) if content else False
            rows.append({"qid": qid, "domain": domain, "difficulty": diff,
                         "rep": rep, "pass": ok,
                         "latency_s": rec.get("latency_s"),
                         "answer_head": (content or "")[:120]})
    return _profile(rows)


def _profile(rows: list) -> dict:
    by_domain, by_diff = {}, {}
    for r in rows:
        for bucket, key in ((by_domain, r["domain"]), (by_diff, r["difficulty"])):
            b = bucket.setdefault(key, {"pass": 0, "n": 0})
            b["n"] += 1
            b["pass"] += int(r["pass"])
    def rate(b):
        return round(b["pass"] / b["n"], 2) if b["n"] else None
    # 档位对照（经验刻度，供人工判断）
    tiers = {
        "顶级旗舰": "H 通过率 ≥ 0.9 且 M = 1.0",
        "旗舰/次旗舰": "H ≥ 0.5 且 M ≥ 0.75",
        "中档主力": "H ≥ 0.25 且 M ≥ 0.5",
        "入门/轻量": "其余",
    }
    h = rate(by_diff.get("H", {"pass": 0, "n": 0})) or 0
    m = rate(by_diff.get("M", {"pass": 0, "n": 0})) or 0
    if h >= 0.9 and m >= 1.0:
        tier = "顶级旗舰"
    elif h >= 0.5 and m >= 0.75:
        tier = "旗舰/次旗舰"
    elif h >= 0.25 and m >= 0.5:
        tier = "中档主力"
    else:
        tier = "入门/轻量"
    return {
        "by_domain": {k: {**v, "rate": rate(v)} for k, v in by_domain.items()},
        "by_difficulty": {k: {**v, "rate": rate(v)} for k, v in by_diff.items()},
        "capability_tier": tier,
        "tier_rubric": tiers,
        "n_questions": len(rows),
        "rows": rows,
    }
