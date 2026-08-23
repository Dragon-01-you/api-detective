#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""core: 证据存储 + 随机化探测客户端。

设计要点（来自实战教训）:
1. 所有请求/响应原样留档 —— 证据链是一切的根基
2. 请求间随机抖动 —— 防止被网关识别为脚本流量
3. 探针措辞随机化入口 —— 由各阶段模块注入
4. 计费感知 —— 金丝雀探针先探 402，防止烧钱
"""
from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone

from openai import OpenAI


class Evidence:
    """把每一条测试记录原样落盘，文件名即索引。"""

    def __init__(self, out_dir: str):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.n_saved = 0

    def save(self, name: str, record: dict) -> None:
        path = os.path.join(self.out_dir, f"{name}.json")
        i = 0
        while os.path.exists(path):
            i += 1
            path = os.path.join(self.out_dir, f"{name}_{i}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)
        self.n_saved += 1


class Detective:
    """随机化、留痕、计费感知的探测客户端。"""

    def __init__(self, base_url: str, api_key: str, model: str,
                 out_dir: str = "./evidence", seed: int | None = None,
                 min_gap: float = 0.8, max_gap: float = 2.5):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.client = OpenAI(base_url=f"{self.base_url}/v1"
                             if not self.base_url.endswith("/v1") else self.base_url,
                             api_key=api_key, timeout=180)
        self.ev = Evidence(out_dir)
        self.rng = random.Random(seed)
        self.min_gap, self.max_gap = min_gap, max_gap
        self.billable_calls = 0        # 成功计费调用计数（预算控制）
        self.billing_blocked = False   # 金丝雀发现计费被挡
        self.last_error = None

    # ------------------------------------------------------------------
    def polite_sleep(self):
        time.sleep(self.rng.uniform(self.min_gap, self.max_gap))

    # ------------------------------------------------------------------
    def canary(self, max_tokens: int = 5) -> dict:
        """金丝雀：一次极小请求，探测端点可用性/计费状态。"""
        try:
            r = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": "1"}],
                max_tokens=max_tokens,
            )
            self.billable_calls += 1
            return {"ok": True, "model_field": getattr(r, "model", None)}
        except Exception as e:  # noqa: BLE001 —— 报错本身就是指纹
            self.last_error = str(e)[:500]
            code = getattr(getattr(e, "response", None), "status_code", None)
            body = ""
            try:
                body = getattr(e, "response", None).text[:500]
            except Exception:
                pass
            blocked = code in (402, 429) or "充值" in body or "billing" in body.lower()
            if blocked:
                self.billing_blocked = True
            return {"ok": False, "status_code": code, "body": body, "blocked": blocked}

    # ------------------------------------------------------------------
    def chat(self, name: str, messages: list, model: str | None = None,
             temperature: float | None = None, max_tokens: int = 400,
             extra: dict | None = None, meta: dict | None = None,
             sleep: bool = True) -> dict:
        """发起一次留痕对话。返回完整记录（含错误）。"""
        model = model or self.model
        rec = {
            "test": name,
            "ts": datetime.now(timezone.utc).isoformat(),
            "request": {"model": model, "messages": messages,
                        "temperature": temperature, "max_tokens": max_tokens,
                        "extra": extra or {}},
            "meta": meta or {},
        }
        if sleep:
            self.polite_sleep()
        t0 = time.monotonic()
        kwargs = {"model": model, "messages": messages, "max_tokens": max_tokens}
        if temperature is not None:
            kwargs["temperature"] = temperature
        if extra:
            kwargs.update(extra)
        try:
            resp = self.client.chat.completions.create(**kwargs)
            self.billable_calls += 1
            rec["latency_s"] = round(time.monotonic() - t0, 3)
            ch = (resp.choices or [{}])[0]
            msg = ch.get("message", {}) if isinstance(ch, dict) else getattr(ch, "message", None)
            msg = msg if isinstance(msg, dict) else _dump_message(msg)
            rec["response"] = {
                "id": getattr(resp, "id", None),
                "model": getattr(resp, "model", None),
                "system_fingerprint": getattr(resp, "system_fingerprint", None),
                "finish_reason": ch.get("finish_reason") if isinstance(ch, dict) else getattr(ch, "finish_reason", None),
                "message": msg,
                "usage": _dump_usage(getattr(resp, "usage", None)),
            }
        except Exception as e:  # noqa: BLE001
            rec["latency_s"] = round(time.monotonic() - t0, 3)
            ro = getattr(e, "response", None)
            rec["error"] = {
                "error_type": type(e).__name__,
                "status_code": getattr(ro, "status_code", None) if ro is not None else None,
                "body": _safe_body(ro),
                "str": str(e)[:1000],
            }
        self.ev.save(name, rec)
        return rec

    # ------------------------------------------------------------------
    def stream(self, name: str, messages: list, model: str | None = None,
               max_tokens: int = 200, meta: dict | None = None) -> dict:
        """流式时序探针：TTFT / chunk 间隔 / 假流式检测。"""
        model = model or self.model
        self.polite_sleep()
        t0 = time.monotonic()
        chunks, ttft, err = [], None, None
        try:
            s = self.client.chat.completions.create(
                model=model, messages=messages, max_tokens=max_tokens, stream=True)
            for ev_ in s:
                t = time.monotonic() - t0
                if ttft is None and (ev_.choices or [None])[0].delta and \
                        getattr((ev_.choices or [None])[0].delta, "content", None):
                    ttft = t
                chunks.append(t)
            self.billable_calls += 1
        except Exception as e:  # noqa: BLE001
            err = str(e)[:500]
        total = round(time.monotonic() - t0, 3)
        intervals = [round(chunks[i] - chunks[i - 1], 4) for i in range(1, len(chunks))]
        rec = {
            "test": name, "ts": datetime.now(timezone.utc).isoformat(),
            "request": {"model": model, "messages": messages, "max_tokens": max_tokens},
            "meta": meta or {},
            "stream": {
                "n_chunks": len(chunks), "ttft_s": ttft, "total_s": total,
                "intervals_ms": [round(x * 1000, 2) for x in intervals][:200],
                "error": err,
            },
        }
        self.ev.save(name, rec)
        return rec


# ----------------------------------------------------------------------
def _dump_message(m) -> dict:
    if m is None:
        return {}
    if isinstance(m, dict):
        return m
    d = {}
    for k in ("role", "content", "reasoning_content", "tool_calls", "refusal"):
        v = getattr(m, k, None)
        if v is not None:
            d[k] = v if not isinstance(v, (list, tuple)) else str(v)
    # 兜底: 模型可能带额外字段（如 reasoning_content 在 model_extra）
    extra = getattr(m, "model_extra", None) or {}
    for k, v in extra.items():
        d.setdefault(k, v)
    return d


def _dump_usage(u) -> dict | None:
    if u is None:
        return None
    if isinstance(u, dict):
        return u
    d = {}
    for k in ("prompt_tokens", "completion_tokens", "total_tokens",
              "prompt_tokens_details", "completion_tokens_details"):
        v = getattr(u, k, None)
        if v is not None:
            d[k] = str(v) if not isinstance(v, (int, float)) else v
    extra = getattr(u, "model_extra", None) or {}
    d.update({k: v for k, v in extra.items()})
    return d or None


def _safe_body(ro) -> str | None:
    if ro is None:
        return None
    try:
        return ro.text[:800]
    except Exception:
        return None


def msg_content(rec: dict) -> str:
    """从 chat() 记录里取正文。"""
    r = rec.get("response") or {}
    m = (r.get("message") or {})
    return m.get("content") or ""


def msg_reasoning(rec: dict) -> str:
    r = rec.get("response") or {}
    return (r.get("message") or {}).get("reasoning_content") or ""


def model_field(rec: dict):
    return (rec.get("response") or {}).get("model")
