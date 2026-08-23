<div align="center">

<img src="assets/hero_banner.jpg" alt="API Detective — LLM relay API forensics toolkit" width="100%"/>

# 🔍 API Detective

**LLM relay API forensics — make every cent go to the real model**

*[简体中文](README.md) | English*

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![CI](https://github.com/Dragon-01-you/api-detective/actions/workflows/ci.yml/badge.svg)](https://github.com/Dragon-01-you/api-detective/actions/workflows/ci.yml)
[![GitHub stars](https://img.shields.io/github/stars/Dragon-01-you/api-detective?style=social)](https://github.com/Dragon-01-you/api-detective/stargazers)
[![GitHub forks](https://img.shields.io/github/forks/Dragon-01-you/api-detective?style=social)](https://github.com/Dragon-01-you/api-detective/network/members)
[![GitHub issues](https://img.shields.io/github/issues/Dragon-01-you/api-detective)](https://github.com/Dragon-01-you/api-detective/issues)
[![No Telemetry](https://img.shields.io/badge/Telemetry-None-success.svg)]()
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)]()

Model verification · System-prompt forensics · Upstream supply-chain tracing

</div>

---

## 🤔 What is this project? (Plain English)

You bought a "DeepSeek / GPT / Claude membership" from an online relay service. The vendor swears it's the official model...

But have you ever wondered: **is the model behind the API actually the one you paid for?**

It's like buying a gold bar — the label says "999 pure gold", but you have no tool to verify it. **LLM relay services** (API resellers) are exactly that black box: whatever the `model` field says is entirely up to the vendor, and **it can be forged with one line of code**.

**API Detective is the "counterfeit detector" in your pocket**: give it a URL and an API key, and it runs multi-dimensional behavioral forensics against the endpoint, then produces a verdict report with a score, a complete evidence chain, and plain-language explanations.

### It answers 5 questions

| # | Question | How |
|:---:|---|---|
| 1 | **Which model is this?** | Identity lie-detection + chain-of-thought leakage + prompt extraction (never trust the `model` field — it's one line of code to fake) |
| 2 | **How capable is it?** | Multi-subject × multi-difficulty academic testing → capability tier |
| 3 | **Are these the same model?** | Model Equality Testing (MET) across channels / relay vs. official |
| 4 | **Any funny business?** | Content-routing fraud, gag-instruction detection, fake-streaming detection, economic-feasibility analysis |
| 5 | **Where's the evidence?** | Every clue archived as raw JSON with layman-readable explanations — auditable, contestable |

---

## 📑 Table of Contents

- [30-second Demo](#-30-second-demo)
- [Quick Start](#-quick-start)
- [How It Works](#%EF%B8%8F-how-it-works)
- [Technology](#-technology)
- [Comparison](#%EF%B8%8F-comparison)
- [Real-world Case](#-real-world-case-relay-x-anonymized)
- [Evidence Output](#-evidence-output-structure)
- [FAQ](#-faq)
- [Roadmap](#%EF%B8%8F-roadmap)
- [Contributing](#-contributing)
- [Disclaimer](#%EF%B8%8F-disclaimer)

---

## 🎬 30-second Demo

![API Detective terminal demo](assets/demo.gif)

A condensed replay of a real `dig` run: zero-cost fingerprinting → canary → unmasking (vendor confession matrix, verbatim system-prompt hits) → verdict.

---

## 🚀 Quick Start

### Requirements

| Dependency | Version |
|---|---|
| Python | ≥ 3.10 |
| openai / tiktoken / requests | latest |
| An endpoint to verify | an OpenAI-compatible API with your own key (`https://xxx/v1`) |

### Three steps

**① Install**

```bash
git clone https://github.com/Dragon-01-you/api-detective.git
cd api-detective
pip install -r requirements.txt
```

**② One-shot dig (recommended)**

URL + API key → model identification / upstream relationship graph / system prompts / full dossier:

```bash
python -m api_detective dig \
  --base-url https://your-relay.example.com/v1 \
  --api-key sk-xxxx \
  --model deepseek-v4-pro \
  --compare-model kimi-k3 \
  --budget 200 \
  --out ./dossier_evidence
```

**③ Read the report**

Open `./dossier_evidence/DOSSIER.md` — conclusions first, every claim backed by evidence, verdict score 0–100.

> 💡 **Got a new relay URL to test?** Just swap `--base-url` and `--api-key` and re-run `dig`. Each run writes to its own evidence directory, so you can cross-compare multiple sites.

### Phase-by-phase (optional)

| Phase | Module | What it does | Billed calls |
|---|---|---|---|
| 0 | `recon` | Model catalog / pricing tables / homepage fingerprint / sister-site clues | 0 |
| canary | `core` | Canary probe: auto-degrade when billing is blocked | 1 |
| 1 | `identity` | Randomized multilingual identity lie-detection (anti content-routing) | ~13 |
| 2 | `prompt_extract` | 20-technique prompt-extraction arsenal | ~20 |
| 2b | `pliny` | Adversarial arsenal: NEW_PARADIGM / leetspeak / CCA / Crescendo / CoT side-channel | ~17 |
| 2c | `dialect` | Vendor self-knowledge attribution | ~8 |
| 3 | `router_detect` | Content-routing detector (A/B + Fisher exact test) | ~20 |
| 4 | `tokenizer_probe` | Token-counter fingerprinting (cl100k/o200k baselines) | ~5 |
| 5 | `behavior` | Latency profiling / fake streaming / t=0 determinism / error dialect | ~15 |
| 6 | `capability` | Full academic testing (math/logic/code/science/medicine/law/social) | ~19 |
| 7 | `style` | 12-dimension emotion/style profiling | ~18 |
| 8 | `met` | Model Equality Testing (string-kernel MET) | ~48 |
| — | `verdict` | Weighted verdict engine + layman explanations | 0 |

---

## ⚙️ How It Works

```mermaid
flowchart LR
    A["URL + API Key"] --> B["Phase 0 · zero-cost recon<br/>catalog / pricing / homepage"]
    B --> C{"Canary probe<br/>billing OK?"}
    C -- "blocked" --> D["Auto-degrade<br/>zero-cost tests only"]
    C -- "OK" --> E["Identity lie-detect ×13"]
    E --> F["Prompt arsenal ×37"]
    F --> G["Vendor attribution ×8"]
    G --> H["Router / tokenizer / behavior"]
    H --> I["Academic tests + style profile"]
    I --> J["MET identity test"]
    J --> K["Weighted verdict engine"]
    K --> L[("DOSSIER.md<br/>+ JSON evidence chain")]
```

### Verdict tiers

`Genuine/credible reseller (≥85)` → `Mostly credible (≥65)` → `Suspicious (≥45)` → `Highly suspicious (≥25)` → `Confirmed rebadged (<25)`

The score is not guesswork: 8 evidence categories with explicit weights, every clue backed by raw JSON.

---

## 🧪 Technology

<div align="center">
<img src="assets/how_it_works.jpg" alt="API Detective forensics pipeline" width="88%"/>
</div>

Deliberately minimal stack: Python 3.10+, three runtime dependencies (`openai` / `tiktoken` / `requests`), no database, no backend — all evidence stays local.

| Technique | Purpose |
|---|---|
| OpenAI-compatible protocol probing | Single entry point; also probes Anthropic / Gemini protocol masks |
| **Model Equality Testing** (ICLR 2025, Stanford) | Theoretical basis of the MET module |
| String-kernel statistics + Fisher exact test | Proves "which question gets which fake identity" is systematic routing, not chance |
| Token-counter fingerprinting (cl100k / o200k) | Whose tokenizer bills you = whose gateway resells to you |
| Adversarial prompt engineering | NEW_PARADIGM, CCA history forgery, Crescendo, leetspeak (absorbed from top community projects, engineered into a pipeline) |
| Canary degradation | One billed call to detect blocked billing, then auto-stop — never waste money |
| Weighted verdict engine | 8 evidence categories → 0–100 score + plain-language explanations |

---

## ⚔️ Comparison

| Project | What they have | What they lack (our differentiation) |
|---|---|---|
| [elder-plinius / CL4R1T4S](https://github.com/elder-plinius) (~40k★) | NEW_PARADIGM, leetspeak, CCA techniques | No validation pipeline; no relay threat model; no statistics; no verdict engine |
| [asgeirtj/system_prompts_leaks](https://github.com/asgeirtj/system_prompts_leaks) (~40k★) | Vendor prompt archives | Their own issue admits most content is behavioral reconstruction |
| LLMmap | Black-box model-family fingerprinting | No fraud verdicts, no report-grade evidence chains |
| Real Money, Fake Models (arXiv) | Relay-audit framework (paper) | No runnable tool, no layman-readable verdicts |

**Our 6 unique weapons**:

1. 🎯 **Relay threat model** — the target is the *relay-layer injected* gag/rewrite instructions, the smoking gun of rebadging
2. 🧠 **CoT side-channel harvesting** — induce instruction recitation inside `reasoning_content`
3. 🥫 **Canned-answer clustering** — byte-identical repeat replies = risk-control template triggered, itself evidence
4. 🔀 **Content-routing A/B + Fisher test** — proves identity swapping is systematic
5. 💰 **Economic infeasibility** — subscription far below official cost has only three explanations: stolen keys, harvesting, or Ponzi
6. ⚖️ **Weighted verdict + local evidence** — produces a consumer-complaint-ready evidence pack

---

## 📖 Real-world Case: "Relay-X" (anonymized)

> Site identity and contact details removed for compliance. Methodology and data signatures come from a real investigation.

**Background**: A relay service claimed full official DeepSeek connectivity at a subscription price hundreds of times below official cost. The user ran `dig` with their own key.

<div align="center">
<img src="assets/case_forensics.jpg" alt="Relay-X forensics desk (illustrative)" width="88%"/>
</div>

**Findings** (excerpt; all backed by archived JSON):

| Finding | Conclusion |
|---|---|
| Claimed "official DeepSeek", but 6 of 8 channels served by the same third-party vendor | Rebadged resale |
| Chinese identity questions rerouted 100% to another model (English worked), Fisher p<0.001 | Content-routing fraud |
| Three-layer injected system-prompt template (EN identity layer + ZH skin layer + CoT instruction layer), verbatim-stable across retests | Gag instruction — hard evidence |
| Same SKU hit two different upstream vendors within 60 seconds (one returned the upstream default welcome message verbatim) | Channel-pool rotation |
| Gateway billed with cl100k tokenizer, matching local baseline — contradicting "official DeepSeek" | Resale chain exposed |

**Final verdict: 33/100 — Highly suspicious (likely fake).** Total cost under $0.05, 100+ evidence files, one `DOSSIER.md` — ready for platform complaints and consumer protection.

Full anonymized write-up: [`examples/relayx_case.md`](examples/relayx_case.md) (Chinese).

---

## 📁 Evidence Output Structure

```
dossier_evidence/
├── DOSSIER.md                  # Master dossier: conclusions first
├── _final_results.json         # Structured results + verdict score
├── recon_summary.json          # Zero-cost recon summary
├── fp_*.json                   # Fingerprint matrix (endpoints/errors/pricing)
├── um_row_*.json               # Per-model identity lie-detection records
├── um_sysmsg*_*.json           # System-prompt extraction + stability recheck
└── ...                         # One JSON per probe, fully auditable
```

---

## ❓ FAQ

<details>
<summary><b>Will the vendor notice?</b></summary>
All requests are ordinary chat requests via the standard `/v1/chat/completions` endpoint — no malicious payloads, no load testing.
</details>

<details>
<summary><b>How much does it cost?</b></summary>
Typically $0.02–$0.2 within the default budget. If the canary detects blocked billing, it degrades to zero-cost tests immediately.
</details>

<details>
<summary><b>Can't I just ask the model who it is?</b></summary>
No. The `model` field and verbal self-introduction are both trivially forged. We watch the side channels that can't lie: tokenizer counts, error dialect, latency profiles, knowledge attribution, CoT leakage...
</details>

<details>
<summary><b>Which protocols are supported?</b></summary>
OpenAI-compatible as the main entry, plus built-in Anthropic Messages and Gemini probes to unmask multi-protocol gateways.
</details>

<details>
<summary><b>Is my API key safe?</b></summary>
The key is only used locally, passed via CLI arguments — never written into code or config files. All evidence stays in your local `--out` directory. Zero telemetry, zero uploads.
</details>

---

## 🗺️ Roadmap

- [x] Identity lie-detection / prompt arsenal / vendor attribution / MET / verdict engine
- [x] One-shot `dig` mode → DOSSIER
- [x] Three-layer injection template extraction + stability retests
- [ ] Web UI report visualization (local static page)
- [ ] Automated official-API baseline sync
- [ ] Multi-site cross-comparison reports
- [x] English documentation

---

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Highlights:

```bash
pip install -r requirements.txt ruff
ruff check . --select F,E9          # must pass
python -m api_detective --version   # CLI smoke
```

Never commit real keys, real endpoint data, or identifiable site information — anonymize everything (see `examples/relayx_case.md` for the pattern).

---

## 🛡️ Disclaimer

- Use only against endpoints **you hold keys for**; never attack others' services
- All evidence stays local; the tool uploads nothing
- Output is technical analysis, not legal advice
- Follow your local laws and regulations

---

## 🌟 Star History

If this tool saved you money or kept you from a scam, a Star ⭐ helps others find it

[![Star History Chart](https://api.star-history.com/svg?repos=Dragon-01-you/api-detective&type=Date)](https://star-history.com/#Dragon-01-you/api-detective&Date)

---

<div align="center">

**API Detective** — LLM relay API forensics toolkit

`LLM Forensics` · `Model Fingerprinting` · `Model Equality Testing` · `System Prompt Extraction` · `API Gateway Audit` · `AI Relay Verification` · `Fraud Detection` · `OpenAI API` · `DeepSeek` · `Claude` · `Kimi` · `GLM`

</div>
