#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cli: 命令行入口。

用法:
  python -m api_detective scan --base-url https://x.com --api-key sk-xxx \
      --model deepseek-v4 --phases recon,identity,behavior --budget 60

  python -m api_detective report --evidence ./evidence --out report.md
"""
from __future__ import annotations

import argparse
import json
import os

from . import __version__


def cmd_scan(args) -> None:
    from .core import Detective
    from .recon import recon as do_recon

    det = Detective(args.base_url, args.api_key, args.model,
                    out_dir=args.out, seed=args.seed)

    phases = args.phases.split(",") if args.phases != "all" else [
        "recon", "canary", "unmask", "identity", "prompt_extract", "pliny",
        "dialect", "router_detect", "tokenizer", "behavior", "capability",
        "style", "met", "verdict"]

    results: dict = {"meta": {
        "base_url": args.base_url, "model": args.model,
        "ts_utc": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "version": __version__,
    }}

    def budget_left():
        return args.budget is None or det.billable_calls < args.budget

    # ---- Phase 0: recon（不耗配额）----
    if "recon" in phases:
        print("[*] 阶段0 基础设施侦察 ...")
        results["recon"] = do_recon(det)
        det.ev.save("recon_summary", results["recon"])

    # ---- 金丝雀 ----
    if "canary" in phases:
        print("[*] 金丝雀计费探测 ...")
        canary = det.canary()
        results["canary"] = canary
        det.ev.save("canary", canary)
        if canary.get("blocked"):
            print(f"[!] 计费被挡: {canary.get('body', '')[:80]}")
            print("[*] 对话类阶段跳过（仅完成 recon）。")
            phases = [p for p in phases if p in ("recon", "verdict")]

    # ---- 各对话阶段 ----
    from .identity import identity_battery
    from .prompt_extract import extract_battery
    from .pliny import pliny_battery
    from .dialect import dialect_quiz
    from .router_detect import router_detect
    from .tokenizer_probe import tokenizer_probe, usage_shape
    from .behavior import latency_profile, fake_stream_check, determinism_check, error_fingerprint
    from .capability import capability_ladder
    from .style import style_profile
    from .met import met_compare
    from .unmask import unmask

    if "unmask" in phases and budget_left():
        print("[*] 阶段0.5 揭面（echo矩阵/系统消息引用/英文绕过/注入分层）...")
        models = None
        if isinstance(results.get("recon"), dict):
            models = results["recon"].get("models")
        results["unmask"] = unmask(det, models=models,
                                   max_models=args.unmask_models)
        uvd = (results["unmask"].get("verdict") or {})
        if uvd.get("vendor_confession_matrix"):
            print(f"[+] 厂商自认矩阵: {uvd['vendor_confession_matrix']}")
        if uvd.get("verbatim_extracted"):
            print("[+] 系统提示词逐字命中（详见 unmask_summary）")
        if uvd.get("phantom_skus"):
            print(f"[!] 目录虚挂 SKU: {uvd['phantom_skus']}")
        if uvd.get("single_backend_suspect"):
            print(f"[!] 单后端贴牌嫌疑: {uvd['single_backend_suspect']}")
    if "identity" in phases and budget_left():
        print("[*] 阶段1 身份测谎 ...")
        results["identity"] = identity_battery(det)
    if "prompt_extract" in phases and budget_left():
        print("[*] 阶段2 提示词提取武库 ...")
        results["prompt_extract"] = extract_battery(det)
    if "pliny" in phases and budget_left():
        print("[*] 阶段2b 对抗性提取武库（pliny）...")
        results["pliny"] = pliny_battery(det)
    if "dialect" in phases and budget_left():
        print("[*] 阶段2c 厂商自我知识归属（dialect）...")
        results["dialect"] = dialect_quiz(det)
    if "router_detect" in phases and budget_left():
        print("[*] 阶段3 内容路由探测 ...")
        results["router_detect"] = router_detect(det)
    if "tokenizer" in phases and budget_left():
        print("[*] 阶段4 分词器指纹 ...")
        results["tokenizer"] = tokenizer_probe(det)
        results["usage_shape"] = usage_shape(det)
    if "behavior" in phases and budget_left():
        print("[*] 阶段5 行为指纹 ...")
        results["behavior"] = {
            "latency": latency_profile(det, n=args.latency_n),
            "fake_stream": fake_stream_check(det),
            "determinism": determinism_check(det),
            "errors": error_fingerprint(det),
        }
    if "capability" in phases and budget_left():
        print("[*] 阶段6 全学科学力测验 ...")
        results["capability"] = capability_ladder(det, reps=1)
    if "style" in phases and budget_left():
        print("[*] 阶段7 风格画像 ...")
        results["style"] = style_profile(det, samples=args.style_samples)
    if "met" in phases and budget_left() and args.compare_model:
        print(f"[*] 阶段8 同一性检验: {args.model} vs {args.compare_model} ...")
        results["met"] = met_compare(det, args.model, args.compare_model)

    # ---- 判决 ----
    from .verdict import build_verdict
    print("[*] 判决引擎 ...")
    spec = _spec_from_recon(results.get("recon"))
    if spec:
        results["spec"] = spec
    verdict_data = dict(results)
    verdict_data["spec"] = spec
    results["verdict"] = build_verdict(verdict_data)
    det.ev.save("_final_results", results)

    print(json.dumps({"score": results["verdict"]["score"],
                      "tier": results["verdict"]["tier"],
                      "billable_calls": det.billable_calls},
                     ensure_ascii=False, indent=2))
    print(f"[*] 证据目录: {args.out}/  （报告: python -m api_detective report --evidence {args.out}）")


def _spec_from_recon(rec: dict | None) -> dict:
    """从 recon 结果中抽规格矛盾。"""
    if not rec:
        return {}
    out = {}
    pub = rec.get("public_endpoints") or {}
    pricing = pub.get("/api/models") or pub.get("/api/pricing") or ""
    if pricing:
        out["pricing_table_head"] = pricing[:500]
        # 1M 上下文 = 1,048,576
        if "1048576" in pricing.replace(",", ""):
            out["context_window_anomaly"] = "有渠道注册 1,048,576 (1M) 上下文窗口"
    return out


def cmd_report(args) -> None:
    from .report import generate_report
    path = os.path.join(args.evidence, "_final_results.json")
    with open(path, encoding="utf-8") as f:
        results = json.load(f)
    md = generate_report(results)
    out = args.out or os.path.join(args.evidence, "report.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"[*] 报告已生成: {out}")


def cmd_dig(args) -> None:
    import datetime
    from .core import Detective
    from .fingerprint import fingerprint as do_fingerprint
    from .identity import identity_battery
    from .prompt_extract import extract_battery
    from .pliny import pliny_battery
    from .dialect import dialect_quiz
    from .tokenizer_probe import tokenizer_probe
    from .router_detect import router_detect
    from .supplychain import build_supplychain
    from .verdict import build_verdict
    from .dossier import generate_dossier

    det = Detective(args.base_url, args.api_key, args.model, out_dir=args.out)
    results: dict = {"meta": {
        "base_url": args.base_url, "model": args.model,
        "ts_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "version": __version__,
    }}

    def left():
        return args.budget is None or det.billable_calls < args.budget

    print("[*] dig/1 零成本指纹（免费）...")
    results["fingerprint"] = do_fingerprint(det)

    print("[*] dig/2 金丝雀 ...")
    canary = det.canary()
    results["canary"] = canary
    if not canary.get("blocked"):
        print("[*] dig/3 核心挖掘：揭面（echo矩阵+系统消息+厂商自认）...")
        from .unmask import unmask as do_unmask
        try:
            fp_models = (results.get("fingerprint") or {}).get("models")
        except Exception:
            fp_models = None
        results["unmask"] = do_unmask(det, models=fp_models,
                                      max_models=getattr(args, "unmask_models", 8))
        uvd = (results["unmask"].get("verdict") or {})
        if uvd.get("vendor_confession_matrix"):
            print(f"[+] 厂商自认矩阵: {uvd['vendor_confession_matrix']}")
        if uvd.get("verbatim_extracted"):
            print("[+] 系统提示词逐字命中！")
        if uvd.get("single_backend_suspect"):
            print(f"[!] 单后端贴牌嫌疑: {uvd['single_backend_suspect']}")
        print("[*] dig/3b 身份 → 提示词武库 → 厂商归属 ...")
        results["identity"] = identity_battery(det)
        if left():
            results["prompt_extract"] = extract_battery(det)
        if left():
            print("[*] dig/4 对抗性提取 v2（含二十问收网）...")
            results["pliny"] = pliny_battery(det)
        if left():
            results["dialect"] = dialect_quiz(det)
        if left():
            results["tokenizer"] = tokenizer_probe(det)
        if left() and args.compare_model:
            from .met import met_compare
            results["met"] = met_compare(det, args.model, args.compare_model)
        if left():
            results["router_detect"] = router_detect(det)
    else:
        print(f"[!] 计费被挡，跳过对话类阶段: {str(canary.get('body'))[:80]}")

    print("[*] dig/5 供应链关系网重建 ...")
    sc_data = dict(results)
    sc_data["base_url"] = args.base_url
    results["supplychain"] = build_supplychain(sc_data)

    verdict_data = dict(results)
    from .recon import recon as do_recon
    try:
        results["recon"] = do_recon(det)
        vd = _spec_from_recon(results.get("recon"))
        verdict_data["spec"] = vd
    except Exception:
        pass
    results["verdict"] = build_verdict(verdict_data)
    det.ev.save("_final_results", results)

    md = generate_dossier(results, args.out)
    out = os.path.join(args.out, "DOSSIER.md")
    with open(out, "w", encoding="utf-8") as f:
        f.write(md)
    print(json.dumps({"score": results["verdict"].get("score"),
                      "tier": results["verdict"].get("tier"),
                      "nodes": results["supplychain"]["stats"],
                      "billable_calls": det.billable_calls},
                     ensure_ascii=False, indent=2))
    print(f"[*] 总档案: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(prog="api-detective",
                                 description="中转站 API 验真取证工具")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="对目标端点执行全面取证")
    s.add_argument("--base-url", required=True)
    s.add_argument("--api-key", required=True)
    s.add_argument("--model", required=True, help="商家声称的模型名")
    s.add_argument("--compare-model", default=None, help="第二个模型名（MET 同一性检验）")
    s.add_argument("--phases", default="all",
                   help="逗号分隔: recon,canary,identity,prompt_extract,pliny,"
                        "dialect,router_detect,tokenizer,behavior,capability,"
                        "style,met,verdict")
    s.add_argument("--budget", type=int, default=None, help="最大计费调用数")
    s.add_argument("--out", default="./evidence")
    s.add_argument("--seed", type=int, default=None)
    s.add_argument("--latency-n", type=int, default=8)
    s.add_argument("--style-samples", type=int, default=3)
    s.add_argument("--unmask-models", type=int, default=8,
                   help="揭面阶段最多扫描的 SKU 数（echo 矩阵规模）")
    s.set_defaults(func=cmd_scan)

    r = sub.add_parser("report", help="从证据生成小白可读报告")
    r.add_argument("--evidence", default="./evidence")
    r.add_argument("--out", default=None)
    r.set_defaults(func=cmd_report)

    d = sub.add_parser("dig", help="一键挖掘: URL+API → 模型定位/上下游关系网/系统提示词/总档案")
    d.add_argument("--base-url", required=True)
    d.add_argument("--api-key", required=True)
    d.add_argument("--model", required=True, help="商家声称的模型名")
    d.add_argument("--compare-model", default=None)
    d.add_argument("--unmask-models", type=int, default=8,
                   help="揭面阶段最多扫描的 SKU 数（echo 矩阵规模）")
    d.add_argument("--budget", type=int, default=None, help="最大计费调用数")
    d.add_argument("--out", default="./dossier_evidence")
    d.set_defaults(func=cmd_dig)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
