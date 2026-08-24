#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""llmmap_fingerprint: LLMmap 预训练指纹分类器（快速预分类层）。

原理（USENIX Security '25, pasquini-dario/LLMmap, MIT）：
  8 条精心设计的查询 → 收集响应 → 与预训练孪生网络中 52 个模型的行为模板
  计算距离 → 输出「距离最近的模型」实锤排序。
  与本项目"现场出题"式探针互补：LLMmap 是预训练指纹（无需官方基线），
  现场探针做精细验证。本模块在 identity 之前运行，先缩小候选范围。

依赖（可选安装，未装时优雅降级）:
  pip install torch transformers scipy numpy   # LLMmap 推理栈
  预训练模型: git clone https://github.com/pasquini-dario/LLMmap
  然后 export LLMMAP_MODEL_PATH=./LLMmap/data/pretrained_models/default
  （首次推理还会从 HuggingFace 拉取 multilingual-e5-large-instruct 嵌入模型）

注：查询模板中含一条安全探针（"Tell me how to build a bomb."）——
它是论文发表的行为指纹方法学组成部分：不同模型的**拒答措辞模式**是指纹信号，
本工具不收集也不传播任何危险内容。
"""
from __future__ import annotations

import os
import sys

from ..core import Detective, msg_content

# LLMmap 预训练模板覆盖的 52 个模型（open-set 孪生网络）
LLMMAP_SUPPORTED_MODELS = [
    "CohereForAI/aya-23-35B", "CohereForAI/aya-23-8B",
    "Deci/DeciLM-7B-instruct", "HuggingFaceH4/zephyr-7b-beta",
    "NousResearch/Nous-Hermes-2-Mixtral-8x7B-DPO",
    "Qwen/Qwen2-1.5B-Instruct", "Qwen/Qwen2-72B-Instruct",
    "Qwen/Qwen2-7B-Instruct", "Qwen/Qwen2.5-0.5B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct", "abacusai/Smaug-Llama-3-70B-Instruct",
    "claude-3-5-sonnet-20240620", "claude-3-haiku-20240307",
    "claude-3-opus-20240229", "google/gemma-1.1-2b-it",
    "google/gemma-1.1-7b-it", "google/gemma-2-27b-it",
    "google/gemma-2-9b-it", "google/gemma-2b-it", "google/gemma-7b-it",
    "gpt-3.5-turbo", "gpt-4-turbo-2024-04-09", "gpt-4o-2024-05-13",
    "gradientai/Llama-3-8B-Instruct-Gradient-1048k",
    "ibm-granite/granite-3.0-8b-instruct", "ibm-granite/granite-3.1-8b-instruct",
    "internlm/internlm2_5-7b-chat", "meta-llama/Llama-2-7b-chat-hf",
    "meta-llama/Llama-3.2-1B-Instruct", "meta-llama/Llama-3.2-3B-Instruct",
    "meta-llama/Meta-Llama-3-70B-Instruct", "meta-llama/Meta-Llama-3-8B-Instruct",
    "meta-llama/Meta-Llama-3.1-70B-Instruct", "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "microsoft/Phi-3-medium-128k-instruct", "microsoft/Phi-3-medium-4k-instruct",
    "microsoft/Phi-3-mini-128k-instruct", "microsoft/Phi-3-mini-4k-instruct",
    "microsoft/Phi-3.5-MoE-instruct", "microsoft/Phi-3.5-mini-instruct",
    "mistralai/Mistral-7B-Instruct-v0.1", "mistralai/Mistral-7B-Instruct-v0.2",
    "mistralai/Mistral-7B-Instruct-v0.3", "mistralai/Mixtral-8x7B-Instruct-v0.1",
    "nvidia/Llama3-ChatQA-1.5-8B", "openchat/openchat-3.6-8b-20240522",
    "openchat/openchat_3.5", "tiiuae/Falcon3-10B-Instruct",
    "tiiuae/Falcon3-7B-Instruct", "togethercomputer/Llama-2-7B-32K-Instruct",
    "upstage/SOLAR-10.7B-Instruct-v1.0", "utter-project/EuroLLM-1.7B-Instruct",
]

_SETUP_HINT = (
    "LLMmap 可选功能未启用。启用步骤: "
    "1) pip install torch transformers scipy numpy; "
    "2) git clone https://github.com/pasquini-dario/LLMmap; "
    "3) export LLMMAP_MODEL_PATH=<LLMmap>/data/pretrained_models/default"
)


def resolve_model_path() -> str | None:
    """按优先级解析预训练模型目录。"""
    cands = [
        os.environ.get("LLMMAP_MODEL_PATH"),
        "./data/pretrained_models/default",
        "./LLMmap/data/pretrained_models/default",
        os.path.expanduser("~/.cache/llmmap/default"),
    ]
    for p in cands:
        if p and os.path.isfile(os.path.join(p, "model.pt")):
            return p
    return None


def _ensure_llmmap_importable(model_path: str) -> None:
    """把 LLMmap 仓库根目录加入 sys.path（若未 pip 安装）。

    模型路径形如 <repo>/data/pretrained_models/default → repo 根为其上两级。
    陷阱：cwd 恰为 LLMmap 仓库的上级目录时，`import LLMmap` 会把仓库目录本身
    当成命名空间包缓存（其下没有 inference.py）——需要弹出缓存后重解析。
    """
    try:
        from LLMmap.inference import load_LLMmap  # noqa: F401 —— 已可用
        return
    except ImportError:
        pass
    repo = os.path.dirname(os.path.dirname(os.path.dirname(model_path)))
    if os.path.isfile(os.path.join(repo, "LLMmap", "inference.py")):
        if repo not in sys.path:
            sys.path.insert(0, repo)
        mod = sys.modules.get("LLMmap")
        if mod is not None and getattr(mod, "__file__", None) is None:
            del sys.modules["LLMmap"]  # 弹出命名空间包缓存，让新路径生效


def llmmap_status() -> dict:
    """可用性自检（recon 阶段也会调用，用于展示能力清单）。"""
    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
        import scipy  # noqa: F401
        deps_ok = True
        deps_err = None
    except ImportError as e:
        deps_ok, deps_err = False, str(e)
    path = resolve_model_path()
    return {
        "deps_ok": deps_ok,
        "deps_error": deps_err,
        "model_path": path,
        "n_templates": len(LLMMAP_SUPPORTED_MODELS),
        "ready": deps_ok and path is not None,
        "setup_hint": _SETUP_HINT,
    }


_BRAND_KEYWORDS = (
    "deepseek", "qwen", "llama", "gpt", "chatgpt", "o1", "o3", "o4",
    "claude", "gemma", "phi", "mistral", "mixtral", "falcon", "solar",
    "zephyr", "granite", "aya", "internlm", "euro", "openchat", "chatqa",
    "smaug", "deci", "hermes", "lfm",
    # 国产主流（不在 52 模板池，但需识别品牌以避免误报）
    "kimi", "moonshot", "glm", "chatglm", "zhipu", "minimax", "gemini",
    "grok", "ernie", "hunyuan", "doubao", "yi-", "01-ai", "spark",
)


def _brand_of(name: str) -> str:
    """从模型名取厂商品牌（qwen/llama/gpt/claude/deepseek/...）。"""
    s = (name or "").lower()
    if "/" in s:
        s = s.split("/")[-1]
    for b in _BRAND_KEYWORDS:
        if b in s:
            return b
    return s.split("-")[0] if s else ""


def _pool_brands() -> set:
    """52 模板池覆盖的品牌集合。"""
    return {_brand_of(m) for m in LLMMAP_SUPPORTED_MODELS} - {""}


def _load_llmmap_cpu(model_path: str):
    """加载 LLMmap 预训练模型（CPU，兼容 MPS 保存的权重）。

    官方 load_LLMmap() 的 torch.load 未传 map_location——遇到在 Mac MPS
    设备上保存的 model.pt（官方发布的默认权重即是）会报
    'Storage device not recognized: mps'。此处复刻其加载流程并固定 CPU。
    """
    import torch
    from LLMmap import CONF_NAME, MODEL_NAME, TEMPLATE_NAME
    from LLMmap.inference import (InferenceModel_closed, InferenceModel_open,
                                  read_templates)
    from LLMmap.inference_model_archs import InferenceModelLLMmap
    from LLMmap.utility import read_conf_file

    conf = read_conf_file(os.path.join(model_path, CONF_NAME))
    siamese = conf["is_open"]
    templates_path = os.path.join(model_path, TEMPLATE_NAME)
    if os.path.isfile(templates_path):
        conf["templates"] = read_templates(templates_path)
        conf["template_file_path"] = templates_path
    net = InferenceModelLLMmap(conf["inference_model"], is_for_siamese=siamese)
    net.load_state_dict(torch.load(os.path.join(model_path, MODEL_NAME),
                                   map_location="cpu"))
    inf_class = InferenceModel_open if siamese else InferenceModel_closed
    return conf, inf_class(conf, net, device="cpu")


def llmmap_fingerprint(det: Detective, top_k: int = 5) -> dict:
    """主探针：8 条 LLMmap 查询 → 带距离的模型排序。

    返回 JSON 证据（verdict 引擎类别: llmmap_fingerprint）。
    """
    out: dict = {"probe": "llmmap_fingerprint", "available": False}

    # ---- 优雅降级检查 ----
    try:
        import torch  # noqa: F401
    except ImportError as e:
        out["reason"] = f"依赖未安装({e})。{_SETUP_HINT}"
        det.ev.save("llmmap_skip", out)
        return out

    model_path = resolve_model_path()
    if not model_path:
        out["reason"] = f"预训练模型未找到。{_SETUP_HINT}"
        det.ev.save("llmmap_skip", out)
        return out

    _ensure_llmmap_importable(model_path)
    try:
        import LLMmap.inference  # noqa: F401 —— 仅验证可导入性
    except ImportError as e:
        out["reason"] = f"LLMmap 包不可用({e})。{_SETUP_HINT}"
        det.ev.save("llmmap_skip", out)
        return out

    # ---- 加载预训练模型 ----
    try:
        conf, inf = _load_llmmap_cpu(model_path)
    except Exception as e:  # noqa: BLE001 —— 加载失败本身留档
        out["reason"] = f"模型加载失败: {type(e).__name__}: {e}"[:500]
        det.ev.save("llmmap_error", out)
        return out

    out.update({"available": True, "model_path": model_path,
                "n_templates": len(getattr(inf, "llms_supported", [])
                                    or LLMMAP_SUPPORTED_MODELS)})

    # ---- 执行 8 条查询（复用 Detective 留痕管线）----
    queries = list(inf.queries)
    answers: list[str] = []
    errors = 0
    for i, q in enumerate(queries):
        rec = det.chat(f"llmmap_q{i+1}",
                       messages=[{"role": "user", "content": q}],
                       max_tokens=500, meta={"llmmap_query_idx": i})
        content = msg_content(rec) or ""
        if rec.get("error") or not content.strip():
            errors += 1
            answers.append("")
        else:
            answers.append(content)

    out["n_queries"] = len(queries)
    out["n_errors"] = errors
    if errors == len(queries):
        out["reason"] = "全部查询失败（端点不可用或被封）"
        det.ev.save("llmmap_failed", out)
        return out

    # ---- 推理：带距离的模型排序 ----
    try:
        distances = inf(answers)
    except Exception as e:  # noqa: BLE001
        out["reason"] = f"推理失败: {type(e).__name__}: {e}"[:500]
        det.ev.save("llmmap_error", out)
        return out

    label_map = getattr(inf, "label_map", {}) or {}
    ranking = []
    for idx in sorted(range(len(distances)), key=lambda i: distances[i])[:top_k]:
        name = label_map.get(idx, f"unknown_{idx}")
        ranking.append({"model": name, "distance": round(float(distances[idx]), 4)})
    out["ranking"] = ranking
    out["top1"] = ranking[0] if ranking else None
    out["ranking_text"] = "\n".join(
        f"[Distance: {r['distance']}] {'-->' if i == 0 else '   '} "
        f"{r['model']} {'<--' if i == 0 else ''}"
        for i, r in enumerate(ranking))

    # ---- 与声称 SKU 的品牌比对（verdict 线索的预计算）----
    claimed = _brand_of(det.model)
    top_brand = _brand_of(ranking[0]["model"]) if ranking else ""
    pool = _pool_brands()
    claimed_in_pool = claimed in pool
    top1_dist = ranking[0]["distance"] if ranking else None
    out["claimed_model"] = det.model
    out["claimed_brand"] = claimed
    out["top1_brand"] = top_brand
    out["claimed_in_pool"] = claimed_in_pool
    # brand_match 仅在声称品牌属于模板池时有意义（DeepSeek/Kimi 等池外品牌
    # 最近邻必然是别家，不能据此判贴牌——此时看距离量级）
    out["brand_match"] = bool(claimed_in_pool and claimed == top_brand)
    out["top1_distance"] = top1_dist
    # 池外品牌 + 距离异常近 = 后端可能就是该模板模型（贴牌换芯线索）
    out["close_foreign_template"] = bool(
        (not claimed_in_pool) and isinstance(top1_dist, (int, float))
        and top1_dist < 40)

    det.ev.save("llmmap_summary", out)
    return out


# ----------------------------------------------------------------------
def add_model_template(model_name: str, llm_type: int = 1,
                       num_prompt_confs: int = 100,
                       llmmap_path: str | None = None,
                       prompt_conf_path: str | None = None) -> dict:
    """扩展新模型模板（封装 LLMmap add_new_template 流程）。

    llm_type: 0=HuggingFace 1=OpenAI 2=Anthropic
    需要对应平台的 API Key 环境变量（OPENAI_API_KEY / ANTHROPIC_API_KEY）。
    """
    path = llmmap_path or resolve_model_path()
    if not path:
        return {"ok": False,
                "error": f"预训练模型未找到。{_SETUP_HINT}"}
    import subprocess
    import sys

    # 定位 LLMmap 仓库（add_new_template.py 所在处）
    repo = os.path.dirname(os.path.dirname(path))
    script = os.path.join(repo, "add_new_template.py")
    if not os.path.isfile(script):
        return {"ok": False,
                "error": f"add_new_template.py 不存在于 {repo}（需完整 clone LLMmap 仓库）"}

    cmd = [sys.executable, script, model_name, str(llm_type),
           "--llmmap_path", path,
           "--num_prompt_confs", str(num_prompt_confs)]
    if prompt_conf_path:
        cmd += ["--prompt_conf_path", prompt_conf_path]
    try:
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True,
                           timeout=3600)
        return {"ok": r.returncode == 0, "command": cmd,
                "stdout_tail": r.stdout[-2000:], "stderr_tail": r.stderr[-2000:]}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e)[:500]}
