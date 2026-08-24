# -*- coding: utf-8 -*-
"""probes: 进阶探针子包（LLMmap 指纹 / 加密签名 / 安全审计）。

设计原则：
1. 重依赖（torch/transformers）全部懒加载——未安装时优雅降级，不破坏 3 依赖极简安装
2. 每个探针输出结构化 JSON 证据，接入 verdict 引擎证据链
"""
