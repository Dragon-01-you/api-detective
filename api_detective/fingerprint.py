"""零成本指纹采集：错误矩阵 / 特征端点 / 响应头 / 定价表 / 姊妹站发现。

本模块全部探测不需要计费额度，是 dig 模式的第一阶段。
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

FEATURE_PATHS = [
    "/v1/dashboard/billing/subscription",
    "/v1/dashboard/billing/usage",
    "/api/status",
    "/api/about",
    "/api/models",
    "/api/pricing",
    "/api/notice",
    "/api/setup",
    "/api/public/guest-package-purchase",
    "/api/public/key-summary",
]

ERR_CASES = [
    ("empty_body", b""),
    ("no_messages", {"model": "deepseek-chat"}),
    ("model_empty", {"model": "", "messages": [{"role": "user", "content": "x"}]}),
    ("temp_over_range", {"model": "deepseek-chat", "messages": [{"role": "user", "content": "x"}], "temperature": 5}),
    ("unknown_param", {"model": "deepseek-chat", "messages": [{"role": "user", "content": "x"}], "totally_unknown_kwarg": 1}),
    ("bad_role", {"model": "deepseek-chat", "messages": [{"role": "systemd", "content": "x"}]}),
]

FRAMEWORK_SIGS = {
    "express": r"Cannot (GET|POST) ",
    "one_api": r"未登录或登录已过期|one-api",
    "new_api": r"new-api|无权进行此操作",
    "flask_debug": r"Werkzeug|Flask",
    "fastapi": r"FastAPI|detail",
    "openai_official": r"missing_required_parameter",
}

MODEL_NAME_RED_FLAGS = [
    (r"gpt-5\.[0-9]+-(sol|terra|luna|nova|apex)", "自造 GPT 变体名（非 OpenAI 官方 SKU 命名法）"),
    (r"deepseek-v[0-9]+", "宣称的 DeepSeek 版本需与官方发布记录核对"),
    (r"-pro|-flash|-turbo|-max", "营销后缀（官方 API 极少使用）"),
]


def _req(method, url, body=None, key=None, timeout=20):
    headers = {}
    if key:
        headers["Authorization"] = "Bearer " + key
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")[:4000]
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode("utf-8", "replace")[:2000]
    except Exception as e:
        return None, {}, str(e)


def fingerprint(det):
    out = {"errors": {}, "endpoints": {}, "pricing": None, "sibling_sites": [],
           "self_exposure": [], "red_flags": [], "framework_guess": []}
    base = det.base_url.rstrip("/")
    root = base.split("/v1")[0]

    for name, body in ERR_CASES:
        code, hdrs, text = _req("POST", base + "/chat/completions", body, key=det.api_key)
        out["errors"][name] = {"code": code, "snippet": text[:400]}
        det.ev.save("fp_err_" + name, {"http": code, "body": text[:400]})
        time.sleep(0.6)

    for p in FEATURE_PATHS:
        code, hdrs, text = _req("GET", root + p, key=det.api_key)
        out["endpoints"][p] = {"code": code, "snippet": text[:400]}
        det.ev.save("fp_ep_" + p.strip("/").replace("/", "_"), {"http": code, "body": text[:400]})
        m = re.search(r"(中转站|gateway)[^\"<>]{0,80}", text)
        if m and code == 404:
            out["self_exposure"].append({"path": p, "quote": m.group(0)})
        if p.endswith("/api/models") and code == 200:
            try:
                out["pricing"] = json.loads(text)
            except Exception:
                out["pricing_raw"] = text[:2000]
        time.sleep(0.5)

    code, hdrs, text = _req("GET", root + "/", timeout=20)
    det.ev.save("fp_homepage", {"http": code, "size": len(text)})
    for u in sorted(set(re.findall(r'https?://[^\s"\'<>]+', text))):
        host = re.sub(r"https?://([^/]+).*", r"\1", u)
        if host not in ("", None) and not host.startswith(det.base_url.split("//")[-1].split("/")[0]):
            if re.search(r"gpt|ai|agent|api|model|chat", host):
                out["sibling_sites"].append(u)
    for fam in set(re.findall(r"FAMILY_ORDER\s*=\s*\[([^\]]+)\]", text)):
        out["channel_pools_js"] = fam
        det.ev.save("fp_channel_pools", {"js": fam})
    for gpt in sorted(set(re.findall(r"[Gg][Pp][Tt]-[0-9][0-9.x]*", text))):
        if gpt not in out["red_flags"]:
            out["red_flags"].append(gpt)

    all_text = json.dumps(out["errors"], ensure_ascii=False) + json.dumps(out["endpoints"], ensure_ascii=False)
    for fw, sig in FRAMEWORK_SIGS.items():
        if re.search(sig, all_text):
            out["framework_guess"].append(fw)

    if out["pricing"]:
        for m in out["pricing"]:
            mid = m.get("model_id", "")
            for pat, why in MODEL_NAME_RED_FLAGS:
                if re.search(pat, mid):
                    out["red_flags"].append(f"{mid}: {why}")

    det.ev.save("fp_summary", out)
    return out
