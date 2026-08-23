# 安全政策 | Security Policy

## 报告漏洞 | Reporting a Vulnerability

请勿通过公开 Issue 报告安全漏洞。

Please **do not** open public issues for security vulnerabilities.

通过 GitHub Security Advisories 私密报告：

1. 前本仓库页面 → **Security** 标签 → **Report a vulnerability**
2. 或直接联系维护者

我们会在 7 天内确认收到，30 天内给出评估结论。

## 使用安全 | Safe Usage

- API Key 仅在本地使用，通过命令行参数传入，**绝不**写入代码、配置文件或提交历史
- 所有证据默认保存在本地 `--out` 目录，工具零遥测、零上传
- 请仅对**你自己持有 Key** 的端点使用本工具
- 取证数据公开分享前请务必脱敏（站点身份、联系方式、密钥）
