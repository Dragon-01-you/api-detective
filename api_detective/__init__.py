"""api-detective: 中转站 API 验真取证工具包。

给任何 OpenAI 兼容端点做"验真体检"：它背后到底是什么模型？
方法论对标:
- Model Equality Testing (ICLR 2025, Stanford) — 同一性两样本检验
- Real Money, Fake Models: Deceptive Model Claims in Shadow APIs (arXiv:2603.01919)
- LLMmap — 黑盒指纹
- CL4R1T4S / asgeirtj/system_prompts_leaks — 系统提示词泄露档案与提取技术谱系
- elder-plinius 对抗性提取分类学（NEW_PARADIGM / leetspeak / 假设框架）

差异化能力（上述项目均不具备）:
- 中转站威胁模型、reasoning_content 侧信道收割、罐头答案聚类、
  多实例日期指纹、内容路由 A/B + Fisher 检验、计费分词器交叉验证、
  假流式时序检测、厂商自我知识归属、经济不可行性测算、小白可读判决引擎
v0.3.0 新增:
- dig 一键模式: URL+API → 全自动挖掘 → DOSSIER.md 总档案
- fingerprint 零成本指纹: 错误矩阵/特征端点/定价表/自曝消息/姊妹站发现
- pliny v2: Policy Puppetry / 配置合成 / 二十问假设确认收网 / FITD 登门槛
- supplychain: 供应链关系网 mermaid 图谱 + 置信度分级边清单
"""

__version__ = "0.3.0"
