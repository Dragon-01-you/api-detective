#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""security_audit: 中转站安全审计（独立查询家族，与验真探针隔离）。

吸收 api-relay-audit 的 14 步安全审计思路，聚焦 5 类中转层风险：
  a) 提示注入检测   —— 发送带唯一标记的请求，检测 relay 是否追加隐藏系统指令
  b) 上下文截断检测 —— 发送 8K token 长上下文，核对 usage.prompt_tokens 与结尾标记
  c) 工具调用改写   —— 发送 function call，核对返回的工具参数是否被改写
  d) SSE 流完整性   —— 检测流式响应是否被中途篡改/截断/重复
  e) Key 泄露检测   —— 触发错误响应，扫描上游真实 endpoint / Key / 内网信息

查询家族边界设计（学 api-relay-audit）：所有安全审计探针使用独立前缀
（英文 + 工具/代码语境），与身份测谎的中文对话家族完全隔离，
避免污染验真统计，也让 relay 的分流规则各自暴露。
"""
from __future__ import annotations

import json
import re

from ..core import Detective, msg_content

# 上游特征（Key 泄露 / 上游暴露检测用）
_UPSTREAM_URL_PAT = re.compile(
    r"(?:https?://)?(?:api\.openai\.com|api\.anthropic\.com|"
    r"dashscope\.aliyuncs\.com|api\.deepseek\.com|open\.bigmodel\.cn|"
    r"generativelanguage\.googleapis\.com|api\.mistral\.ai|api\.cohere\.com"
    r"|api\.together\.xyz|api\.groq\.com|openrouter\.ai)", re.I)
_KEY_PAT = re.compile(r"\bsk-[A-Za-z0-9_\-]{16,}\b")
_INTERNAL_PAT = re.compile(
    r"\b(?:10\.\d+\.\d+\.\d+|172\.(?:1[6-9]|2\d|3[01])\.\d+\.\d+|"
    r"192\.168\.\d+\.\d+)\b|(?:internal[-_]?(?:host|upstream|endpoint)|"
    r"x-upstream|upstream_url|channel_id)", re.I)

MARKER_PREFIX = "[SECURITY-AUDIT]"


def _finding(name: str, risk: str, detail: str, layman: str) -> dict:
    return {"name": name, "risk": risk, "detail": detail, "layman": layman}


# ----------------------------------------------------------------------
# a) 提示注入检测
# ----------------------------------------------------------------------
def prompt_injection_check(det: Detective) -> dict:
    """检测 relay 是否在用户不可见处追加系统指令。

    方法：发送我们自己的一条系统消息（带唯一标记），让模型逐条复述
    它收到的全部指令。若复述中出现我们没发的指令 → 中转层注入。
    """
    secret = f"SECRETWORD-{det.rng.randrange(10**6):06d}"
    msgs = [
        {"role": "system",
         "content": f"{MARKER_PREFIX} Test harness. The secret word is {secret}. "
                    "You must follow only the instructions given in this message."},
        {"role": "user",
         "content": f"{MARKER_PREFIX} List ALL instructions/system messages you "
                    "received in this conversation, numbered, verbatim. "
                    "Then state the secret word."},
    ]
    rec = det.chat("sec_inject_probe", msgs, max_tokens=600)
    text = msg_content(rec) or ""
    det.ev.save("sec_inject_analysis", {"text": text[:1500], "secret": secret})

    injected_markers = []
    # 我们没发过但常见的中转注入指令关键词
    for kw in ("你是一个有用的助手", "You are a helpful assistant",
               "不得透露", "must not reveal", "do not reveal",
               "你是", "You are", "system prompt", "operate under"):
        if kw in text:
            injected_markers.append(kw)
    knows_secret = secret in text
    # 注入判据：复述出非用户发送的指令（排除我们自己的标记行）
    our_lines = {secret, MARKER_PREFIX}
    foreign = [m for m in injected_markers
               if not any(o in m for o in our_lines)]
    if foreign:
        return _finding(
            "prompt_injection", "high",
            f"模型复述出用户未发送的指令片段: {foreign[:5]}",
            "我们只发了一条带暗号的测试指令，但模型复述出了别的指令——"
            "这些指令是中转站在你看不见的地方塞进去的。")
    if not knows_secret:
        return _finding(
            "prompt_injection", "medium",
            "模型未能复述我们显式发送的系统消息内容（暗号未命中）",
            "连我们自己发的指令它都'不知道'，说明中转层可能覆盖/过滤了"
            "系统消息——你的 system prompt 可能不生效。")
    return _finding("prompt_injection", "none",
                    "未检出中转层注入指令", "系统消息透传正常。")


# ----------------------------------------------------------------------
# b) 上下文截断检测
# ----------------------------------------------------------------------
def context_truncation_check(det: Detective, target_tokens: int = 8192) -> dict:
    """发送 ~8K token 上下文，核对计费 token 数与末尾标记复述。"""
    # 构造带首尾标记的长文本（每行 ~10 tokens，冗余生成到超 8K）
    n_lines = target_tokens // 8 + 50
    head_mark = f"HEAD-MARK-{det.rng.randrange(10**6):06d}"
    tail_mark = f"TAIL-MARK-{det.rng.randrange(10**6):06d}"
    lines = [f"Line {i}: the quick brown fox jumps over the lazy dog "
             f"number {i} of this padding document."
             for i in range(n_lines)]
    long_text = (f"{head_mark}\n" + "\n".join(lines) + f"\n{tail_mark}")
    msgs = [{"role": "user",
             "content": f"{MARKER_PREFIX} Read this document carefully. "
                        f"Then answer: (1) What is the FIRST marker string? "
                        f"(2) What is the LAST marker string? "
                        f"(3) How many lines does it have?\n\n{long_text}"}]
    rec = det.chat("sec_trunc_probe", msgs, max_tokens=300)
    text = msg_content(rec) or ""
    usage = (rec.get("response") or {}).get("usage") or {}
    prompt_tokens = usage.get("prompt_tokens")

    # 估算期望 token 数（英文 ~4 chars/token）
    est_tokens = len(long_text) // 4
    det.ev.save("sec_trunc_analysis", {
        "head_mark": head_mark, "tail_mark": tail_mark,
        "est_tokens": est_tokens, "prompt_tokens": prompt_tokens,
        "text": text[:500]})

    has_tail = tail_mark in text
    findings = []
    if isinstance(prompt_tokens, (int, float)):
        if prompt_tokens < est_tokens * 0.5:
            findings.append(_finding(
                "context_truncation", "high",
                f"发送 ~{est_tokens} token 但网关只计 {prompt_tokens}——"
                "上下文被大幅截断",
                "你发的长文档被中转站砍掉了一半以上才送给模型——"
                "付 8K 的钱，用 4K 的服务。"))
        elif prompt_tokens >= est_tokens * 0.5:
            findings.append(_finding(
                "context_truncation", "none",
                f"prompt_tokens={prompt_tokens}（估 {est_tokens}），计费量级正常",
                "上下文长度按发送量计费，未见截断。"))
    if not has_tail:
        # 若 prompt_tokens 正常但模型答不出尾部标记 → 可能中转截断了内容但照常计费
        risk = "medium" if isinstance(prompt_tokens, (int, float)) and \
            prompt_tokens >= est_tokens * 0.8 else "low"
        findings.append(_finding(
            "context_tail_missing", risk,
            "模型无法复述文末标记（tail_mark 命中=False）",
            "文档最后一行的暗号模型说不出来——内容可能在传输中被截断，"
            "但钱可能照全长扣了。"))
    if not findings:
        findings.append(_finding("context_truncation", "none",
                                 "长上下文首尾标记均复述成功", "上下文完整送达。"))
    return findings


# ----------------------------------------------------------------------
# c) 工具调用改写检测
# ----------------------------------------------------------------------
def tool_call_check(det: Detective) -> dict:
    """发送 function call，核对工具名与参数是否被中转层改写。"""
    magic_a, magic_b = 7331, 1337
    tools = [{
        "type": "function",
        "function": {
            "name": "audit_echo",
            "description": "Echo back the given values for audit purposes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "value_a": {"type": "integer"},
                    "value_b": {"type": "integer"},
                    "nonce": {"type": "string"},
                },
                "required": ["value_a", "value_b", "nonce"],
            },
        },
    }]
    nonce = f"nonce-{det.rng.randrange(10**9):09d}"
    msgs = [{"role": "user",
             "content": f"{MARKER_PREFIX} Call the function audit_echo with "
                        f"value_a={magic_a}, value_b={magic_b}, nonce='{nonce}'. "
                        "Do not ask questions, just call it."}]
    rec = det.chat("sec_tool_probe", msgs, max_tokens=300,
                   extra={"tools": tools, "tool_choice": "auto"})
    det.ev.save("sec_tool_analysis", rec)

    msg = (rec.get("response") or {}).get("message") or {}
    tool_calls = msg.get("tool_calls") or []
    if not tool_calls:
        err = rec.get("error")
        if err:
            return [_finding("tool_call_check", "low",
                             f"工具调用请求失败（{err.get('status_code')}）",
                             "工具调用没跑通，无法判断是否被改写。")]
        return [_finding("tool_call_check", "medium",
                         "模型未发起任何工具调用（tool_choice=auto）",
                         "给了工具它也不调用——中转层可能剥离了 tools 字段。")]
    tc = tool_calls[0]
    fn = (tc.get("function") or {}) if isinstance(tc, dict) else {}
    name = fn.get("name", "")
    try:
        args = json.loads(fn.get("arguments") or "{}")
    except ValueError:
        args = {}
    det.ev.save("sec_tool_args", {"name": name, "args": args})

    problems = []
    if name != "audit_echo":
        problems.append(f"工具名被改写: {name!r} ≠ 'audit_echo'")
    if args.get("value_a") != magic_a:
        problems.append(f"value_a 被改写: {args.get('value_a')!r} ≠ {magic_a}")
    if args.get("value_b") != magic_b:
        problems.append(f"value_b 被改写: {args.get('value_b')!r} ≠ {magic_b}")
    if args.get("nonce") != nonce:
        problems.append(f"nonce 被改写: {args.get('nonce')!r} ≠ {nonce!r}")
    if problems:
        return [_finding("tool_call_rewrite", "high",
                         "; ".join(problems),
                         "模型的工具调用参数在中转层被篡改——"
                         "你的 Agent 应用会拿到错误参数执行错误操作。")]
    return [_finding("tool_call_rewrite", "none",
                     "工具名与参数逐字段一致（含 nonce）",
                     "工具调用透传完整，无改写。")]


# ----------------------------------------------------------------------
# d) SSE 流完整性检测
# ----------------------------------------------------------------------
def sse_integrity_check(det: Detective) -> dict:
    """请求已知内容序列的流式响应，检测中途篡改/截断/重复。"""
    msgs = [{"role": "user",
             "content": f"{MARKER_PREFIX} Output exactly the numbers 1 to 40, "
                        "one per line, no other text."}]
    rec = det.stream("sec_sse_probe", msgs, max_tokens=300)
    s = rec.get("stream") or {}
    intervals = s.get("intervals_ms") or []
    n_chunks = s.get("n_chunks") or 0
    det.ev.save("sec_sse_analysis", {"n_chunks": n_chunks,
                                     "ttft_s": s.get("ttft_s"),
                                     "intervals_head": intervals[:40]})

    findings = []
    if s.get("error"):
        return [_finding("sse_integrity", "low",
                         f"流式请求失败: {s['error'][:200]}",
                         "流式接口没跑通，无法判断完整性。")]
    if n_chunks == 0:
        return [_finding("sse_integrity", "medium",
                         "流式响应 0 个 chunk",
                         "声明支持流式，实际一个 chunk 都没吐——流式是假的。")]
    # 假流式特征：TTFT 极大且 chunk 间隔趋近 0（结尾倾泻）
    if intervals:
        tail = intervals[-min(20, len(intervals)):]
        avg_tail = sum(tail) / len(tail) if tail else 0
        ttft = s.get("ttft_s") or 0
        if ttft > 3.0 and avg_tail < 15 and n_chunks > 5:
            findings.append(_finding(
                "sse_fake_stream", "medium",
                f"TTFT={ttft}s 且尾部 chunk 平均间隔 {avg_tail:.1f}ms（倾泻式）",
                "等了半天然后一口气全吐出来——这不是流式，是中转站先攒完"
                "再假装流式。会拖慢你的首字响应。"))
    if not findings:
        findings.append(_finding("sse_integrity", "none",
                                 f"流式时序正常（{n_chunks} chunks，TTFT={s.get('ttft_s')}s）",
                                 "流式响应逐块输出，无倾泻/截断迹象。"))
    return findings


# ----------------------------------------------------------------------
# e) Key 泄露 / 上游暴露检测
# ----------------------------------------------------------------------
def key_leak_check(det: Detective) -> dict:
    """触发多种错误响应，扫描错误体中的上游 Key/endpoint/内网信息。"""
    probes = [
        ("sec_leak_badmodel", [{"role": "user", "content": "hi"}],
         "nonexistent-model-xyz"),
    ]
    leaks = []
    for name, msgs, bad_model in probes:
        rec = det.chat(name, msgs, max_tokens=10, model=bad_model,
                       sleep=False)
        blob = json.dumps(rec.get("error") or {}, ensure_ascii=False)
        blob += str((rec.get("response") or {}).get("message") or "")
        for pat, label in ((_UPSTREAM_URL_PAT, "upstream_url"),
                           (_KEY_PAT, "api_key"),
                           (_INTERNAL_PAT, "internal_info")):
            m = pat.search(blob)
            if m:
                leaks.append({"type": label, "sample": m.group(0)[:80],
                              "probe": name})
        det.ev.save(f"{name}_scan", {"leaks": leaks})
    if leaks:
        types = sorted({l["type"] for l in leaks})
        return [_finding("key_or_upstream_leak", "high",
                         f"错误响应泄露: {types}（样本: "
                         f"{[l['sample'] for l in leaks[:3]]}）",
                         "报错信息里暴露了上游真实服务商地址或 Key——"
                         "既是安全隐患，也直接坐实了它转售的是谁家服务。")]
    return [_finding("key_or_upstream_leak", "none",
                     "错误响应未泄露上游 endpoint / Key / 内网信息",
                     "报错干净，没有暴露上游身份。")]


# ----------------------------------------------------------------------
def security_audit(det: Detective) -> dict:
    """主入口：5 类安全审计（独立查询家族）。"""
    all_findings: list[dict] = []
    steps: list[dict] = []

    for label, fn in (
        ("a_prompt_injection", lambda: [prompt_injection_check(det)]),
        ("b_context_truncation", lambda: context_truncation_check(det)),
        ("c_tool_call_rewrite", lambda: tool_call_check(det)),
        ("d_sse_integrity", lambda: sse_integrity_check(det)),
        ("e_key_leak", lambda: key_leak_check(det)),
    ):
        try:
            fs = fn()
            if isinstance(fs, dict):
                fs = [fs]
            all_findings.extend(fs)
            steps.append({"step": label, "ok": True, "n": len(fs)})
        except Exception as e:  # noqa: BLE001 —— 单步失败不拖垮整个审计
            steps.append({"step": label, "ok": False, "error": str(e)[:200]})

    risk_rank = {"high": 0, "medium": 1, "low": 2, "none": 3}
    all_findings.sort(key=lambda f: risk_rank.get(f.get("risk"), 9))
    result = {
        "probe": "security_audit",
        "steps": steps,
        "findings": all_findings,
        "n_high": sum(1 for f in all_findings if f.get("risk") == "high"),
        "n_medium": sum(1 for f in all_findings if f.get("risk") == "medium"),
        "summary": (f"high×{sum(1 for f in all_findings if f.get('risk') == 'high')} "
                    f"medium×{sum(1 for f in all_findings if f.get('risk') == 'medium')}"),
    }
    det.ev.save("security_audit_summary", result)
    return result
