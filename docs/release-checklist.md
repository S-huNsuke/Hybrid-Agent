# Release Checklist

## Code & Tests
- `uv run python scripts/release_check.py`
- 默认要求包含：Python 回归测试、前端 build、`e2e:smoke`、`docker-compose config/version`
- E2E 策略由 `RELEASE_E2E_MODE` 控制：
- `required`（默认）：E2E 失败即发布失败
- `auto`：检测到环境限制时允许降级，并输出 `[WARN]`
- `skip`：显式跳过；必须设置 `RELEASE_E2E_SKIP_REASON`

## Deployment
- `docker-compose config`
- `docker-compose up -d postgres api frontend prometheus grafana backup`
- Verify health endpoints
- Confirm Grafana datasource loads
- Confirm backup service writes dumps

## Product Flow
- Register/login
- Provider create + health check
- Admin create user
- Upload document
- Chat response

## Recovery
- Backup file exists
- Restore procedure tested once
- Rollback owner identified
