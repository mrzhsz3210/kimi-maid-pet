# 没药女仆桌宠（Kimi Code 版）发布记录

## v0.1.0（2026-11-13）

首个版本，衍生自 bailong-desktop-pet v0.5.1。

- 后端从 Codex 替换为 Kimi Code：对话与任务通过 `kimi acp`（ACP 协议）进行，支持流式输出、思考摘要、工具进度与权限确认。
- 任务进展同步改为 Kimi Hooks（`TurnStarted`/`PostToolUse`/`Stop` 等事件），不再读取 Codex 本地数据库。
- 额度查询替换为 Kimi CLI 状态检查（Kimi 暂无公开额度接口）。
- 全新原创角色「没药」（星空女仆）：36 段 720×720 / 24fps 透明 WebM 差分，含新增 knockback 互动段。
- 自动启动改为监测 Kimi Code 桌面端进程。
