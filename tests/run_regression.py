#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""判决引擎回归基准（对标 LLMmap test_model.py 的量化标尺模式）。

历史已定案件（tests/cases/*.json，脱敏）→ 期望判决档位。
判决权重 / 覆盖率阈值 / 收缩规则每次调整都必须跑通本基准，
防止评分调优静默改变既有案件的定性。

用法:
    python tests/run_regression.py            # 全部用例
    python tests/run_regression.py case_edge  # 名称模糊匹配
退出码: 0 全过 / 1 有失败
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api_detective.verdict import build_verdict  # noqa: E402


def check_case(spec: dict) -> list:
    """跑单案并返回违规列表（空 = 通过）。"""
    v = build_verdict(spec["data"])
    exp = spec["expect"]
    errs = []

    if "score_min" in exp and v["score"] < exp["score_min"]:
        errs.append(f"score {v['score']} < 下限 {exp['score_min']}")
    if "score_max" in exp and v["score"] > exp["score_max"]:
        errs.append(f"score {v['score']} > 上限 {exp['score_max']}")
    if "tier_prefix" in exp and not v["tier"].startswith(exp["tier_prefix"]):
        errs.append(f"tier「{v['tier']}」不以「{exp['tier_prefix']}」开头")
    if exp.get("inconclusive") is not None and v["inconclusive"] != exp["inconclusive"]:
        errs.append(f"inconclusive={v['inconclusive']}，期望 {exp['inconclusive']}")
    if exp.get("edge_note") and not v["edge_case_note"]:
        errs.append("期望 edge_case_note 非空，实际为空")
    if "n_clues_max" in exp and v["n_clues"] > exp["n_clues_max"]:
        errs.append(f"n_clues {v['n_clues']} > 上限 {exp['n_clues_max']}")
    if "must_clues" in exp:
        ids = {c["id"] for c in v["clues"]}
        missing = [m for m in exp["must_clues"] if m not in ids]
        if missing:
            errs.append(f"缺少必备线索: {missing}")

    print(f"  score={v['score']:<3} p={v['p_genuine']:<7} coverage={v['coverage']:<6} "
          f"tier={v['tier']}")
    return errs


def main() -> int:
    cases_dir = Path(__file__).parent / "cases"
    patterns = sys.argv[1:]
    files = sorted(cases_dir.glob("*.json"))
    if patterns:
        files = [f for f in files if any(p in f.name for p in patterns)]
    if not files:
        print("no matching regression cases")
        return 1

    failed = []
    for cf in files:
        spec = json.loads(cf.read_text(encoding="utf-8"))
        print(f"[CASE] {spec['name']}  ({cf.name})")
        errs = check_case(spec)
        if errs:
            failed.append(spec["name"])
            for e in errs:
                print(f"  ✗ {e}")
        else:
            print("  ✓ PASS")

    print(f"\n{'='*52}")
    print(f"回归基准: {len(files) - len(failed)}/{len(files)} 通过")
    if failed:
        print("失败用例:", ", ".join(failed))
        return 1
    print("全部通过 ✓")
    return 0


if __name__ == "__main__":
    sys.exit(main())
