---
name: "github-repo-optimizer"
description: "Optimizes GitHub repositories to top open-source project standards: SEO metadata (topics/description/social preview), paper-style illustration generation, terminal demo GIF creation (pure PIL, no screen recorder), CI workflow setup, README golden structure, community files, and security scanning. Invoke when pushing a project to GitHub, optimizing an existing repo's presentation, or when user mentions repo SEO, README polish, demo GIF, CI badge, or social preview."
---

# GitHub Repository Optimizer

将任意 GitHub 仓库优化至顶尖开源项目标准的一站式技能。沉淀自真实项目实战（api-detective），所有命令与模板均经验证。

## 优化分层模型（执行顺序）

```
┌─ 仓库级 SEO ──── 描述(双语) / Topics×20 / 社交预览图
├─ 门面层 ──────── Hero图 / 徽章矩阵 / 30秒GIF / 双语切换
├─ 内容层 ──────── TOC / 三步上手 / 案例 / FAQ / Roadmap
├─ 工程层 ──────── CI / pyproject.toml / requirements.txt
├─ 社区层 ──────── CONTRIBUTING / SECURITY / Issue模板 / Release
└─ 安全层 ──────── 敏感信息扫描 / .gitignore分层
```

**核心原则**：每完成一项立即验证一项（API 查询 / 浏览器截图），不凭感觉宣布完成。

---

## Phase 1: 仓库级 SEO

### 描述（双语公式）
```
[中文它是什么]：[三个核心能力] | [English one-liner pitch]
```
```bash
curl -s -X PATCH https://api.github.com/repos/{owner}/{repo} \
  -H "Authorization: token $TOKEN" \
  -d '{"description":"..."}'   # 注意用 PATCH，PUT 会 404
```

### Topics（上限 20 个，四类词均衡）
```bash
curl -s -X PUT https://api.github.com/repos/{owner}/{repo}/topics \
  -H "Authorization: token $TOKEN" \
  -H "Accept: application/vnd.github.mercy-preview+json" \
  -d '{"names":["生态词...","领域大词...","竞品关联词...","功能词..."]}'
```
选词策略：语言生态（python/cli-tool）+ 领域大词（llm/ai-security）+ 竞品词（deepseek/openai-api——搜这些词的人能找到你）+ 功能词。

### 社交预览图
- 规格：**1280×640 (2:1)，<1MB，JPG**
- ⚠️ **无公开 API**（REST/GraphQL 均不暴露，实测内部端点也不接受 OAuth token）——只能网页手动上传
- 制作：AI 生成 16:9 → `scripts/crop_social_preview.py` 裁剪
- 上传：Settings → Social preview → Edit → Upload（40 秒手动步骤，向用户明示）
- 素材务必存 `assets/social_preview.jpg` 入库备用

---

## Phase 2: 配图生成（纸质知识风）

**统一 prompt 模板**（保持全仓库视觉一致性）：
```
[PURPOSE]: {用途}. Hand-drawn ink illustration on vintage cream notebook paper
with subtle grid texture, {主体元素}, red pen annotation circles and checkmarks,
fountain pen black ink and sepia tones with one red accent color, washi tape
pieces on corners, flat vintage stationery knowledge-card aesthetic, no text
```

| 图 | 规格 | README 位置 |
|---|---|---|
| Hero 横幅 | landscape_16_9 | 顶部 width=100% |
| 原理图 | landscape_16_9 | 技术节 width=88% |
| 案例图 | landscape_16_9 | 案例节 width=88% |
| 社交预览 | 裁剪 1280×640 | 仓库设置 |

关键：所有图共用同一组风格关键词（cream paper / fountain pen / sepia / one red accent / no text），形成视觉记忆点。

---

## Phase 3: 终端演示 GIF（无录屏纯代码方案）

**适用**：沙箱无 ttyrec/asciinema 时。用 PIL 逐帧渲染终端窗口动画。

```bash
python3 scripts/make_terminal_gif.py --lines-json '[
  ["$ your-command --flag", "cmd"],
  ["[*] phase output", "info"],
  ["[+] success line", "ok"],
  ["[!] warning line", "warn"],
  ["score: 33/100 -> VERDICT", "bad"]
]' --out assets/demo.gif --title "project — zsh"
```

**渲染三阶段**：命令打字效果（2字符/帧）→ 输出逐行出现（2帧/行）→ 停留+光标闪烁。
**配色**：GitHub dark（bg #0d1117），cmd=青 / ok=绿 / warn=黄 / bad=红 / info=前景白。
**坑**：
- 无 CJK 字体时（`fc-list | grep -i cjk` 为空）内容必须全英文，否则豆腐块
- 产物控制在 <1MB（GitHub 渲染友好）；820×500 约 110 帧 ≈ 540KB
- 演示内容必须来自真实运行输出（浓缩回放），不可虚构

---

## Phase 4: CI 工作流

```yaml
# .github/workflows/ci.yml 要点：
on: {push: {branches: [main]}, pull_request: null, workflow_dispatch: null}
jobs.test.strategy.matrix: {python-version: ['3.10','3.11','3.12','3.13']}
steps:
  - ruff check . --select F,E9        # 只查真实错误，风格噪声不挡 CI
  - CLI 入口冒烟（--version / --help）
  - 包导入测试
  - 零成本功能路径（如 --phases recon 秒级完成）
```

**坑**：
- 别在 CI 跑完整业务流程（带 sleep 重试的会拖几分钟）
- 本地彩排必须 `bash -c` 包裹——**zsh 不对未加引号变量分词**（`$cmd="scan --help"` 变单参数）
- 徽章：`[![CI](https://github.com/{o}/{r}/actions/workflows/ci.yml/badge.svg)](...)`

---

## Phase 5: README 黄金结构

```markdown
Hero图 → # 项目名+一句话价值 → 英文pitch(斜体) → 语言切换 → 徽章矩阵(8+)
## 🤔 这是什么（说人话：类比开场+定位）
### 能回答N个问题（表格）
## 🎬 30秒演示（GIF）
## 📑 目录（TOC锚点）
## 🚀 快速开始（环境要求表 → ①安装②命令③看结果）
## ⚙️ 工作原理（mermaid流程图）
## 🧪 技术实现（配图+技术×用途表）
## ⚔️ 对比同类项目（吸收了谁+差异化）
## 📖 实际案例（脱敏代号+发现×结论表+判决数字）
## ❓ FAQ（<details>折叠）
## 🗺️ 路线图（复选框）
## 🤝 参与贡献（本地验证命令+铁律）
## 🛡️ 免责声明 → ## 🌟 Star历史 → 底部关键词墙
```

排版微优化：表格窄列 `|:---:|` 居中；图片统一 88% 居中；FAQ 用 `<details>` 折叠；H2 间 `---` 分割。
锚点坑：GitHub 对 emoji 标题的锚点**去掉 emoji**（`## 🚀 快速开始` → `#-快速开始`）。

---

## Phase 6: 社区文件清单

| 文件 | 必含要点 |
|---|---|
| CONTRIBUTING.md | PR 5步 + 本地验证命令 + **脱敏铁律** + 欢迎方向 |
| SECURITY.md | 漏洞私密报告路径 + 密钥安全声明 |
| .github/ISSUE_TEMPLATE/bug_report.md | YAML frontmatter + 环境 + **脱敏提醒** |
| .github/ISSUE_TEMPLATE/feature_request.md | 先问题后方案 |
| pyproject.toml | `[project.scripts]` 提供命令 + 版本单一来源 `dynamic = ["version"]` |

## Phase 7: Release

```bash
gh release create vX.Y.Z --title "vX.Y.Z — 主题" --notes-file notes.md --target main
# Notes结构：定位一句话→核心能力→质量保障(CI/文档)→实战验证→compare链接
# 无GH_TOKEN时用 REST: POST /repos/{o}/{r}/releases
```
Tag 必须与 `__init__.py` 的 `__version__` 严格一致。

---

## 安全扫描（每轮推送前后必做）

```bash
# 推送前：暂存内容全量扫描
git diff --cached | grep -inE "sk-[A-Za-z0-9]{16,}|真实域名|手机号|QQ号|@foxmail" || echo PASS
```

**⚠️ .gitignore 泄露陷阱**：.gitignore 本身会被推送！里面写 `evidence_target-site/`、`target_case.md` 等具体名称 = 变相泄露目标身份。正确做法：
- 公开 .gitignore 只写泛化规则（`evidence*/`、`*.log`、`.env`、`*.key`）
- 具体文件名放 `.git/info/exclude`（纯本地，永不推送）

```bash
# 推送后：远端结构验证
curl -s https://api.github.com/repos/{o}/{r}/contents/ -H "Authorization: token $T" \
  | python3 -c "import json,sys; [print(f['path']) for f in json.load(sys.stdin)]"
# CI状态
curl -s "https://api.github.com/repos/{o}/{r}/actions/runs?per_page=1" -H "Authorization: token $T"
```

浏览器视觉验证（可派子代理）：图片加载/GIF播放/徽章全渲染/mermaid图/TOC锚点点击/表格无溢出/Topics展示。

---

## 认证问题速查（实战踩坑）

| 症状 | 根因 | 解法 |
|---|---|---|
| `createRepository` 403 | GitHub App 集成凭证无建仓权 | 用户网页手动建仓：`github.com/new?name=xxx&description=yyy` 预填参数 |
| 旧仓库可写新仓库 403 | App 安装范围不含新仓库 | settings/installations → Repository access → All repos |
| `Invalid username or token` | 重新授权撤销了旧 token | Device Flow：POST github.com/login/device/code → 用户本地浏览器授权 → 轮询 oauth/access_token |
| 网页 2FA 卡死 | 沙箱浏览器无验证器 | 同上 Device Flow（本地已登录浏览器授权，不触发 2FA） |
| 远端带初始 README | add/add 冲突 | `git merge origin/main --allow-unrelated-histories` + `checkout --ours README.md` |
| git push 凭证失败 | credential helper 失效 | `git push https://x-access-token:$TOKEN@github.com/{o}/{r}.git main:main` |
| dig/scan 本地挂起 | 沙箱代理劫持 | 冒烟改跑秒级零成本阶段（--phases recon） |

Device Flow 完整命令（client_id 需替换为实际 OAuth App）：
```bash
# 1. 发起
curl -s -X POST https://github.com/login/device/code -H "Accept: application/json" \
  -d "client_id={ID}&scope=repo"
# 2. 用户本地浏览器打开 verification_uri 输入 user_code
# 3. 轮询（标准端点是 /login/oauth/access_token，不是 /oauth/access_token！）
curl -s -X POST https://github.com/login/oauth/access_token -H "Accept: application/json" \
  -d "client_id={ID}&device_code={CODE}&grant_type=urn:ietf:params:oauth:grant-type:device_code"
```

---

## 交付验收清单

- [ ] 描述双语 + ≤120 字符
- [ ] Topics 满 20 个
- [ ] 社交预览图 1280×640 已上传（或明确告知用户手动步骤）
- [ ] README：Hero/双语切换/8+徽章/GIF/TOC/三步上手/Roadmap/贡献/免责
- [ ] README_EN 完整翻译并互链
- [ ] CI 矩阵全绿 + 徽章亮起
- [ ] pyproject.toml 可 `pip install git+...`
- [ ] CONTRIBUTING/SECURITY/Issue 模板就位
- [ ] Release 已发布且 Notes 完整
- [ ] `git diff --cached` 敏感扫描 PASS
- [ ] .gitignore 无具体目标名称
- [ ] 浏览器视觉验证全项通过
- [ ] 临时令牌已提醒用户删除/撤销
