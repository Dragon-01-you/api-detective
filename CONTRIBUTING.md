# 参与贡献 | Contributing

感谢你关注 API Detective！欢迎通过 Issue 和 Pull Request 参与。

Thank you for your interest! Issues and PRs are both welcome (English or Chinese).

## 快速上手

1. Fork 本仓库 / Fork the repo
2. 创建特性分支 / Create a feature branch
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. 提交更改 / Commit your changes
   ```bash
   git commit -m "feat: add amazing feature"
   ```
4. 推送并发起 PR / Push and open a Pull Request
   ```bash
   git push origin feature/amazing-feature
   ```

## 本地验证（提交前请跑通 / Run before submitting）

```bash
pip install -r requirements.txt ruff
ruff check . --select F,E9          # lint：真实错误必须为 0
python -m api_detective --version   # CLI 冒烟
python -m api_detective scan --help
```

CI 会对 Python 3.10–3.13 矩阵运行同样的检查，保持绿勾。

## 特别欢迎的贡献方向

- 🧪 新的提示词提取技术（prompt extraction techniques）
- 📊 官方 API 基线数据（tokenizer / 错误措辞 / 延迟画像）
- ⚖️ 判决引擎权重调优建议（附证据与理由）
- 🌍 文档翻译（英文 / 日文 / 其他）
- 🐛 Bug 报告：请附上脱敏后的证据 JSON 与复现命令

## 行为准则

- **严禁在任何提交/Issue/PR 中包含真实密钥、真实端点数据或可识别的站点信息**——取证数据一律脱敏（参考 `examples/relayx_case.md` 的写法）
- 保持友善和专业的讨论氛围
- 仅对你持有 Key 的端点做测试

## 举报安全问题

请勿公开 Issue 讨论安全漏洞，参见 [SECURITY.md](SECURITY.md)。
