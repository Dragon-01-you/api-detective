# 更新日志

本项目遵循 [语义化版本](https://semver.org/lang/zh-CN/)。所有重要变更都会记录在此文件。

格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)。

---

## [0.6.0] — 2026-08-25

> 本次为**品牌重塑 + 工程化补全**版本，探针与判决逻辑无改动。

### 变更
- **项目更名为「芯火 XH」**，GitHub 仓库由 `api-detective` 迁移至 [`xh-forensics`](https://github.com/Dragon-01-you/xh-forensics)。
  旧仓库地址会由 GitHub 自动 301 重定向，历史链接与 clone 不受影响。
- PyPI 包名统一为 `xh-forensics`，新增命令 `xh` 与 `xh-forensics`；
  原 `api-detective` 命令**保留为兼容别名**，已有脚本无需修改。
- Python 导入路径 `api_detective.*` **保持不变**，属于内部实现，不随品牌改名。

### 新增
- `MANIFEST.in`：sdist 打包清单，确保公开情报库（`intel/`）、基线模板、Skill 包、
  文档与回归用例随源码包一起分发。
- `[tool.setuptools.data-files]`：wheel 安装时把 `intel/`、`baselines/_template.json`、
  Skill 包释放到 `<prefix>/share/xh-forensics/`，解决此前「pip 安装后情报库丢失」的问题。
- `CHANGELOG.md`（本文件）、`CODE_OF_CONDUCT.md`、`.github/dependabot.yml`、
  `.github/pull_request_template.md`。
- Python 3.14 分类器；新增 `dev` 可选依赖（`build`、`ruff`）。
- `pyproject.toml` 补充 `Repository` / `Changelog` / `Intelligence` 项目链接。

### 修复
- wheel 不再遗漏公开情报库数据文件。
- **合规修复（重要）**：此前 `MANIFEST.in` 缺省时，含可识别站点域名与商号的未脱敏案例
  `examples/yunjunet_case.md` 会被打进 sdist。现已在 `MANIFEST.in` 加硬排除、
  并把同名规则写进 `.gitignore` 随仓库传播，双重拦截。已验证 sdist 与 wheel 均不含该文件。
- **修复两处死链**：`README.md` 与 `intel/cross_site_comparison.md` 此前指向未公开的
  未脱敏案例文件（公网 404）。改为指向可公开的 `intel/cross_site_comparison.md`
  与 `examples/relayx_case.md`。

---

## [0.5.0] — 2026-08-24

### 新增
- **公开情报库 `intel/`**：从 2026-06 至 2026-08 真实取证案件提炼的机器可读欺诈特征库。
  - `intel/README.md` — 30 秒速查表 + 9 大类欺诈特征索引。
  - `intel/fraud_patterns.json` — 9 大类机器可读特征（自造 SKU / 命名空间泄露 / 换皮 /
    封口令 / 内容路由 / 分词器指纹 / 软件指纹 / 过期日期 / 经济不可行），
    每条附 regex、判定方法、证据等级、来源案件。
  - `intel/cross_site_comparison.md` — 多站点横向对比手法矩阵（含 2026-08 复测更新）。
- **判决回归基准 `tests/run_regression.py`**：5 个历史用例覆盖边界混合、真货阳性收缩、
  覆盖不足守卫、单后端换皮、弱信号中危档位，防止判决引擎改动引入回归。
- 学术引用支持：`CITATION.cff`，方法论对标 LLMmap (USENIX Security '25) /
  Model Equality Testing (ICLR 2025) / Real Money, Fake Models。

### 变更
- README 首屏重排：公开情报库前置，无需安装工具即可消费。

---

## 0.5.0 之前

早期迭代完成了核心探针体系与工程化基建，未打版本标签：

- 12+ 探针模块：LLMmap 预训练指纹（52 模板最近邻）、加密签名验证（Claude thinking
  signature / OpenAI reasoning tokens）、内容路由 Fisher 精确检验、计费分词器指纹、
  三层注入模板系统提示词提取、安全审计 5 探针、身份测谎、能力测验、模型同一性检验（MET）、
  供应链溯源。
- Softmax 判决引擎 v2（类别归一化 + 概率化 0–100 打分 + 证据不足守卫）。
- 零依赖 Web UI 本地控制台；DOSSIER 小白可读总档案。
- CI：Python 3.10–3.13 四版本矩阵、7 个 CLI 入口冒烟、判决引擎单测、回归基准、
  LLMmap 优雅降级验证、零成本 recon 冒烟。
- 双语文档（README.md / README_EN.md）、社区规范、演示素材。
