# Deployment Guide

## Prerequisites
- Docker Engine / Docker daemon available
- `docker-compose` command available
- `.env` created from `.env.example`
- Required API keys configured

## Start
```bash
docker-compose up -d postgres api frontend prometheus grafana backup
```

## Verify
```bash
docker-compose ps
curl -f http://127.0.0.1:8000/health
curl -f http://127.0.0.1:5173/
curl -f http://127.0.0.1:9090/-/healthy
curl -f http://127.0.0.1:3000/api/health
```

## Migrations
- API container runs `alembic upgrade head` on boot through `docker-entrypoint.sh`.
- If manual execution is needed:
```bash
docker-compose exec api uv run alembic upgrade head
```

## Backup & Restore
### Backup
- `backup` service writes daily `pg_dump` files into the `backup_data` volume and retains 7 days.

### Restore
1. Stop API writes:
```bash
docker-compose stop api web frontend
```
2. Restore from a chosen dump:
```bash
docker-compose exec -T postgres psql -U postgres -d hybrid_agent < /path/to/backup.sql
```
3. Start services again:
```bash
docker-compose up -d api frontend web
```

## Shutdown
```bash
docker-compose down
```

## Troubleshooting
- `docker-compose up` fails with `/var/run/docker.sock`: Docker daemon is not running.
- API healthcheck fails: inspect `docker-compose logs api`.
- Frontend loads but API calls fail: confirm `API_UPSTREAM` and container network resolution.
