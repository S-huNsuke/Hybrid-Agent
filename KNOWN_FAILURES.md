# 已知 Agent 失败模式
> 每当 Agent 尝试推进模块却被底层缺失阻挡时，将情形写在这里，避免重复试错。

## M0 阶段
- **文档与代码现实不一致**：说明里说 M0 早已完成，实际仓库虽有 CLAUDE.md、docs/architecture.md、docs/conventions.md、tests/test_architecture.py、scripts/check.py、CI 配置等工件，但它们与代码现状、依赖方向、部署流程仍未完全对齐，验证过程屡屡失败。
- **前端因 M0  未验收就进入 M9**：Vue/M9 结构已经存在但缺乏 JWT/auth、设计系统、布局和数据绑定，继续做前端页面会被基础权限/接口不一致拖慢反复返工，必须先让 M0 验证通过。

## 后端现状
- **单体 FastAPI + SQLite + 固定 Chroma 还在**：PostgreSQL/Alembic、JWT/RBAC、group 隔离、版本化 API、异步文档任务、监控链路尚未实现，试图推进 M1-M8 之前无法复现计划中的 Phase 1/2 环境。
- **API 路由绕过现有架构分层**：`chat`、`documents` 路由直接触发处理逻辑，未通过 service/repository 抽象，未来结构性测试和 CI 会持续报错。

## 故障应对
- 按 Two-Strike 规则：若某次 Agent 修复后仍然失败，请先确认上述模式是否为根因，若是，记录在此再发起新尝试；连续两次失败需升级给人工并标注时间。
