---
name: "api-detective"
description: "AI relay API forensics: verify the model behind an API key, extract injected system prompts, and trace the upstream supply chain. Invoke when user mentions testing an API relay, checking if a purchased model is fake, verifying API relay authenticity, extracting system prompts, or detecting rebranded/counterfeit models."
---

# API Detective — AI 中转站 API 验真取证（Hermes Agent 格式）

对 OpenAI 兼容端点执行多维度行为取证，产出评分 0–100 的判决报告与完整证据链。

## When to use

- 用户给出中转站 URL + API Key，想验证模型真伪
- 用户怀疑买到的 GPT/Claude/DeepSeek 是贴牌或换芯货
- 用户想提取中转站注入的系统提示词
- 用户想溯源上游供应链（多家 SKU 是否共用一个后端）

## How to use

### 环境准备（首次）

```bash
git clone https://github.com/Dragon-01-you/api-detective.git
cd api-detective
pip install -r requirements.txt
```

### 一键取证

```bash
python -m api_detective dig \
  --base-url <URL> \
  --api-key <KEY> \
  --model <MODEL> \
  --budget 200 \
  --out ./dossier_evidence
```

### 参数速查

| 参数 | 必填 | 说明 |
|---|---|---|
| `--base-url` | ✅ | OpenAI 兼容地址（通常以 `/v1` 结尾） |
| `--api-key` | ✅ | 用户自己的 Key（仅本地使用） |
| `--model` | ✅ | 商家声称的模型 SKU 名 |
| `--compare-model` | — | 同站第二个模型，MET 同一性检验 |
| `--budget` | — | 最大计费调用数（默认无限，建议 ≤200） |
| `--baseline` | — | 官方基线名（如 `gpt-4o`），启用严格比对模式 |
| `--out` | — | 证据输出目录（默认 `./dossier_evidence`） |

## Output

| 文件 | 内容 |
|---|---|
| `DOSSIER.md` | 判决报告：评分 + 档位 + 小白解释 + 供应链关系网 |
| `_final_results.json` | 结构化结果（`verdict.score` / `verdict.tier` / 逐条 clue） |
| `*.json`（100+ 个） | 每次探测的原始请求/响应留档，可复核可反驳 |

### 判决档位

≥85 正品 · ≥65 大体可信 · ≥45 可疑 · ≥25 高度可疑 · <25 确证贴牌

## Report to user

1. 读 `DOSSIER.md` 开头的判决块（评分 + 档位）
2. 引用 3–5 条最强证据（厂商自认矩阵 / 系统提示词逐字命中 / 路由改道率 / 分词器指纹）
3. 用小白语言解释「为什么这条证据说明是假的」
4. 提醒：结论是技术分析意见；维权可凭 `--out` 目录证据包走平台投诉/12315

## Constraints

- 仅测用户自己持有 Key 的端点
- Key 不落盘、不外传（工具零遥测）
- 金丝雀探针发现计费被挡 → 自动降级为零成本测试
