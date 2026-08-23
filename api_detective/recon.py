#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""recon: 基础设施侦察（不消耗对话配额）。

- /v1/models 模型清单（SDK）
- 常见中转站框架公开端点探测（new-api / one-api / veloera 系）:
  /api/models, /api/status, /api/pricing, /api/public/key-logs, /api/packages
- 首页 HTML 指纹: title / generator / 框架特征
- 服务器响应头指纹
"""
from __future__ import annotations

import re

import requests

from .core import Detective

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"


def _get(url: str, key: str | None = None, timeout: float = 20.0) -> dict:
    headers = {"User-Agent": UA}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        ct = r.headers.get("content-type", "")
        body = r.text[:20000] if "text" in ct or "json" in ct or "html" in ct else "<binary>"
        return {"url": url, "status": r.status_code,
                "headers": dict(r.headers), "body_head": body[:2000]}
    except Exception as e:  # noqa: BLE001
        return {"url": url, "error": str(e)[:300]}


def recon(det: Detective) -> dict:
    base = det.base_url
    if base.endswith("/v1"):
        origin = base[:-3]
    else:
        origin = base
    key = det.api_key
    out: dict = {"origin": origin}

    # 1. /v1/models
    try:
        models = [m.id for m in det.client.models.list()]
        out["models"] = models
    except Exception as e:  # noqa: BLE001
        out["models_error"] = str(e)[:300]

    # 2. 中转站框架公开端点（不同框架暴露不同组合，全部试一遍）
    endpoints = [
        "/api/models", "/api/status", "/api/pricing",
        "/api/public/key-logs", "/api/packages", "/api/notice",
        "/api/about", "/api/homepage_content",
    ]
    found = {}
    for ep in endpoints:
        r = _get(origin + ep, key=key)
        if r.get("status") == 200 and r.get("body_head"):
            found[ep] = r["body_head"]
    out["public_endpoints"] = found

    # 3. 首页指纹
    home = _get(origin + "/")
    title = re.search(r"<title>(.*?)</title>", home.get("body_head", ""), re.S)
    out["homepage"] = {
        "status": home.get("status"),
        "title": title.group(1).strip() if title else None,
        "framework_hints": [sig for sig in
                            ("new-api", "one-api", "veloera", "chatgpt-next-web",
                             "VoAPI", "shell-api", "done-hub")
                            if sig.lower() in (home.get("body_head") or "").lower()],
        "interesting_strings": _scan_interesting(home.get("body_head") or ""),
    }

    # 4. 服务器头
    head = _get(origin + "/v1/models")
    out["server_headers"] = {k: v for k, v in (head.get("headers") or {}).items()
                             if k.lower() in ("server", "x-powered-by", "via",
                                              "cf-ray", "x-request-id")}
    return out


def _scan_interesting(html: str) -> list:
    """扫首页里暴露的其他站点/产品名（多站马甲线索）。"""
    pats = [
        r"[A-Za-z0-9.-]+\.(?:com|cn|net|org|ai|io)",          # 域名
        r"GPT[- ]?\d(?:\.\d)?",                               # GPT 版本字样
        r"(?:Claude|Gemini|Grok|Kimi|Doubao|Qwen|GLM|MiniMax|文心)",
    ]
    hits = set()
    for p in pats:
        hits.update(re.findall(p, html, re.I))
    return sorted(hits)[:60]
