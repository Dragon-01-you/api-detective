# GitHub 仓库优化方法论 Playbook

> 以 api-detective 项目实战为标准沉淀，可复制到任何新仓库。
> 使用方式：按「0→9」顺序执行，每项都有可直接复用的模板/命令/踩坑记录。

---

## 0. 总览：优化分层模型

```
┌─ 仓库级 SEO ──── 描述(双语) / Topics×20 / 社交预览图 / 默认分支保护
├─ 门面层 ──────── Hero图 / 徽章矩阵 / 30秒GIF / 双语切换
├─ 内容层 ──────── TOC / 三步上手 / 环境要求表 / 案例(脱敏) / FAQ / Roadmap
├─ 工程层 ──────── CI(GitHub Actions) / pyproject.toml / requirements.txt
├─ 社区层 ──────── CONTRIBUTING / SECURITY / Issue模板 / Release
└─ 安全层 ──────── 敏感信息扫描 / .gitignore分层 / 本地排除(.git/info/exclude)
```

**核心原则**：每个优化点都必须「可验证」——做完一项就用浏览器或 API 验证一项，不凭感觉。

---

## 1. 仓库级 SEO（最先做，权重最高）

### 1.1 描述（相当于 Meta Description）
```bash
curl -s -X PATCH https://api.github.com/repos/{owner}/{repo} \
  -H "Authorization: token $TOKEN" \
  -d '{"description":"中文核心价值 | English one-liner"}'
```
- 公式：`[它是什么]：[三个核心能力] | [English pitch]`
- 控制在 120 字符内让 About 栏不截断重要信息

### 1.2 Topics（GitHub 搜索流量入口，上限 20 个）
```bash
curl -s -X PUT https://api.github.com/repos/{owner}/{repo}/topics \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.mercy-preview+json" \
  -d '{"names":["llm","api-security", ...]}'
```
- 选词策略：**语言生态词**（python/cli-tool）+ **领域大词**（llm/ai-security）+ **竞品关联词**（deepseek/openai-api/claude——让搜这些词的人找到你）+ **功能词**（prompt-extraction/fraud-detection）

### 1.3 社交预览图（分享到社交平台的门面）
- 规格：**1280×640（2:1），<1MB，JPG/PNG**
- 制作：AI 生成 16:9 → PIL 裁剪到 2:1：
  ```python
  from PIL import Image
  im = Image.open("raw.jpg").convert("RGB")
  w, h = im.size
  im.crop((0, (h-w//2)//2, w, (h-w//2)//2 + w//2)).resize((1280,640)).save("social_preview.jpg", quality=88)
  ```
- ⚠️ 坑：**无公开 API**，只能网页手动上传（Settings → Social preview）。素材先存 `assets/` 备用。

---

## 2. README 结构（对标 40k★ 项目的黄金结构）

```markdown
Hero横幅图（width=100%）
# 项目名 + 一句话价值主张
英文 pitch（斜体一行）
语言切换：简体中文 | English
徽章矩阵（License/Python/CI/stars/forks/issues/Telemetry/PRs）
---
## 🤔 这是什么（说人话版）——类比开场 + 「验钞机」式定位
### 它能回答 N 个问题（表格）
## 🎬 30 秒演示（GIF）
## 📑 目录（TOC，锚点链接）
## 🚀 快速开始
  ### 环境要求（表格）
  ### 三步上手（①安装 ②核心命令 ③看结果）
  ### 分阶段运行（可选，模块×计费调用表格）
## ⚙️ 工作原理（mermaid 流程图）
## 🧪 技术实现（配图 + 技术×用途表 + 判决档位）
## ⚔️ 对比同类项目（吸收了谁 + 差异化是什么）
## 📖 实际案例（脱敏代号 + 配图 + 发现×结论表 + 判决数字）
## 📁 输出结构
## ❓ FAQ（<details> 折叠）
## 🗺️ 路线图（- [x]/- [ ] 复选框）
## 🤝 参与贡献（本地验证命令 + 铁律）
## 🛡️ 使用须知/免责声明
## 🌟 Star 历史
底部关键词墙（中英混排，给搜索引擎吃）
```

**排版细节**（实测有效的微优化）：
- 表格首列窄内容用 `|:---:|` 居中（如序号列）
- 图片统一 `width="88%"` 居中，hero 用 `100%`
- 长内容 FAQ 用 `<details><summary>` 折叠，减少滚动疲劳
- 每个 H2 之间用 `---` 分割，视觉节奏统一
- 锚点链接测试：GitHub 对 emoji 标题的锚点会**去掉 emoji**（`## 🚀 快速开始` → `#-快速开始`）

---

## 3. 配图规范（纸质知识风）

| 图 | 尺寸 | 位置 | 用途 |
|---|---|---|---|
| Hero 横幅 | landscape_16_9 | README 顶部 | 项目气质定调 |
| 原理图 | landscape_16_9 | 技术实现节 | 流程可视化 |
| 案例图 | landscape_16_9 | 实际案例节 | 氛围/代入感 |
| 社交预览 | **1280×640** | 仓库设置 | 社交分享门面 |

**纸质风 prompt 模板**（SDXL）：
```
[PURPOSE]: {用途}. Hand-drawn ink illustration on vintage cream notebook paper
with subtle grid texture, {主体元素}, red pen annotation circles and checkmarks,
fountain pen black ink and sepia tones with one red accent color, washi tape
pieces on corners, flat vintage stationery knowledge-card aesthetic, no text
```
- 关键词：`cream paper` `grid texture` `fountain pen ink` `sepia` `one red accent` `no text`
- 所有图**统一风格关键词**，形成视觉记忆点

---

## 4. 终端演示 GIF 制作（无录屏软件的纯代码方案）

**适用场景**：沙箱无 ttyrec/asciinema，但有 Python+PIL。

**流程**：
1. 跑一次真实命令，记录输出（保证演示内容真实）
2. PIL 渲染终端窗口逐帧动画：
   - 窗口：暗底 `#0d1117`（GitHub dark）+ 标题栏三点
   - 字体：`DejaVuSansMono.ttf`（无 CJK 字体时**内容用英文**）
   - 三阶段动画：命令打字效果（2字符/帧）→ 输出行逐行出现（2帧/行）→ 结尾停留+光标闪烁
   - 颜色语义：命令=青色 / `[+]`=绿 / `[!]`=黄 / 判决=红
3. 保存参数：`save_all=True, duration=分帧设置, loop=0, optimize=True`
4. 产物控制在 **<1MB**（GitHub 渲染友好）

**坑**：
- `fc-list | grep -i cjk` 先查字体——无 CJK 就全英文，别硬塞中文（豆腐块）
- 帧数 = 打字帧(~40) + 行数×2 + 停留帧(~14)，820×500 约 110 帧 → 538KB ✅

---

## 5. CI 工作流（GitHub Actions）

### 5.1 设计原则
- **只查真实错误**：`ruff check . --select F,E9`（pyflakes + 语法错误），风格类规则不进 CI——否则老项目永远红
- **矩阵测试**：Python 3.10–3.13 四版本
- **冒烟分层**：CLI 入口 → 包导入 → 零成本功能路径
- ⚠️ 坑：**不要**在 CI 里跑完整业务流程（如本项目的 `dig` 全流程带礼貌延时 sleep，死端点也要几分钟）；改跑 `--phases recon` 这类秒级路径

### 5.2 模板（可直接复用）
```yaml
name: CI
on:
  push: {branches: [main]}
  pull_request:
  workflow_dispatch:
jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix: {python-version: ['3.10', '3.11', '3.12', '3.13']}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "${{ matrix.python-version }}", cache: pip}
      - run: pip install -r requirements.txt ruff
      - run: ruff check . --select F,E9
      - run: python -m {pkg} --version
      - run: python -m {pkg} {subcmd} --help > /dev/null
      - run: python -c "import {pkg}; from {pkg} import core_modules"
```

### 5.3 徽章
```markdown
[![CI](https://github.com/{owner}/{repo}/actions/workflows/ci.yml/badge.svg)](https://github.com/{owner}/{repo}/actions/workflows/ci.yml)
```

### 5.4 提交前本地彩排（避免推上去才红）
```bash
bash -c 'ruff check . --select F,E9 && python -m {pkg} --version && ...'
```
⚠️ 坑：**zsh 不对未加引号变量分词**——`$cmd="scan --help"` 在 zsh 里是单个参数！彩排务必用 `bash -c` 包裹（CI 环境就是 bash）。

---

## 6. 打包配置（pyproject.toml）

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "项目名"
description = "同仓库描述"
readme = "README.md"
requires-python = ">=3.10"
dependencies = ["..."]
dynamic = ["version"]

[project.scripts]
命令名 = "包.cli:main"          # 提供 pip 装完即用的命令

[tool.setuptools.dynamic]
version = { attr = "包.__version__" }   # 版本单一来源：__init__.py
```
- README 安装区补一行：`pip install git+https://github.com/{owner}/{repo}.git`
- keywords 与仓库 Topics 保持一致（双入口 SEO）

---

## 7. 社区文档清单

| 文件 | 要点 |
|---|---|
| `CONTRIBUTING.md` | 5 步 PR 流程 + **本地验证命令** + 脱敏铁律 + 欢迎方向 |
| `SECURITY.md` | 漏洞私密报告路径（Security Advisories）+ 密钥安全声明 |
| `.github/ISSUE_TEMPLATE/bug_report.md` | YAML frontmatter（name/about/labels）+ 环境信息 + **脱敏提醒** |
| `.github/ISSUE_TEMPLATE/feature_request.md` | 先问题后方案 |

## 8. Release 流程

```bash
# 1. 版本号单一来源（__init__.py 的 __version__），tag 与之严格一致
# 2. Release Notes 结构：定位一句话 → 核心能力 → 质量保障(CI/文档) → 实战验证 → compare 链接
gh release create vX.Y.Z --title "vX.Y.Z — 主题" --notes-file notes.md --target main
```
- 发布即出现在 GitHub 动态流（followers 免费曝光）
- 用 `gh release create`；无 GH_TOKEN 时用 REST `POST /repos/{o}/{r}/releases`

---

## 9. 安全与验证（每轮推送前后必做）

### 9.1 推送前敏感信息扫描
```bash
# 暂存内容全量扫描（密钥格式/真实站名/联系方式/邮箱/QQ号）
git diff --cached | grep -inE "sk-[A-Za-z0-9]{16,}|真实域名|手机号|QQ号|foxmail" \
  || echo "SECURITY_SCAN_PASS"
```
⚠️ 坑：**.gitignore 本身也会被推送**——里面写 `evidence_target-site/`、`target_case.md` 等具体名称等于变相泄露目标身份。正确做法：
- 公开 `.gitignore` 只写**泛化规则**（`evidence*/`、`*.log`、`.env`）
- 具体文件名放 `.git/info/exclude`（纯本地，永不推送）

### 9.2 推送后远端验证
```bash
# 结构验证
curl -s https://api.github.com/repos/{o}/{r}/contents/ -H "Authorization: token $T" \
  | python3 -c "import json,sys; [print(f['path']) for f in json.load(sys.stdin)]"
# CI 状态
curl -s "https://api.github.com/repos/{o}/{r}/actions/runs?per_page=1" -H "Authorization: token $T"
```

### 9.3 浏览器视觉验证（子代理执行）
检查项：Hero/配图加载、GIF 播放、徽章全渲染（含动态数）、mermaid 图渲染、TOC 锚点点击、表格无横向溢出、Topics 展示、Release 页面完整。

---

## 附：本次实战踩坑速查

| 坑 | 现象 | 解法 |
|---|---|---|
| GitHub App 凭证无建仓权限 | `createRepository` 403 | 用户网页手动建仓（URL 预填参数 `/new?name=xxx&description=yyy`） |
| App 安装范围不含新仓库 | 旧仓库可写、新仓库 403 | github.com/settings/installations → Repository access → All repos |
| 重新授权撤销旧 token | `Invalid username or token` | 用 PAT（classic）临时令牌直推：`git push https://x-access-token:$PAT@...` |
| 远端带初始 README | add/add 冲突 | `git merge origin/main --allow-unrelated-histories` + `checkout --ours README.md` |
| zsh 不分词 | `$cmd` 含空格被当单参数 | CI 彩排用 `bash -c` 包裹 |
| 沙箱代理劫持本地端口 | 死端点请求挂起 | CI 冒烟改跑秒级零成本阶段（`--phases recon`） |
| 无 CJK 字体 | PIL 渲染中文变豆腐块 | GIF 内容用英文，中文留给 README |
| mermaid 图节点过多 | 嵌入渲染文字过小 | 精简节点数 / 用户可点开全屏 |

## 附：交付验收清单（一键自检）

- [ ] 仓库描述双语 + ≤120 字符
- [ ] Topics 满 20 个（生态+领域+竞品+功能词）
- [ ] 社交预览图 1280×640 已上传（或素材就位）
- [ ] README：Hero/双语切换/8+徽章/GIF/TOC/三步上手/Roadmap/贡献/免责
- [ ] README_EN 完整翻译并互链
- [ ] CI 四版本矩阵全绿 + 徽章亮起
- [ ] pyproject.toml 可 `pip install git+...`
- [ ] CONTRIBUTING/SECURITY/Issue 模板就位
- [ ] Release 已发布且 Notes 完整
- [ ] `git diff --cached` 敏感扫描 PASS
- [ ] .gitignore 无具体目标名称（泛化规则 only）
- [ ] 浏览器视觉验证全项通过
- [ ] 临时 PAT 已删除
