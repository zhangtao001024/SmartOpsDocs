# SmartOpsDocs Backend

默认管理员账号:

```text
admin / admin123
```

推荐从项目根目录使用 Docker Compose 部署：

```bash
cd /root/SmartOpsDocs
cp .env.docker.example .env
# 编辑 .env，至少修改 JWT_SECRET 和 INITIAL_ADMIN_PASSWORD
docker compose up -d --build
```

访问：

```text
http://服务器IP:8080
```

部署到可访问网络前，请在项目根目录 `.env` 中修改：

```text
JWT_SECRET=请改成随机长字符串
INITIAL_ADMIN_PASSWORD=请改成强密码
FRONTEND_PORT=8080
```

后端容器只在 Compose 内部网络暴露 `8000`，外部统一访问前端端口，由前端 Nginx 代理 `/api` 到后端。

本地开发启动后端：

```bash
cd backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

可选模型配置：

```text
OPENAI_API_KEY=你的 key
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
OPENAI_VISION_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
AGENT_RUNTIME=local-openclaw
OPENCLAW_ENDPOINT=
OPENCLAW_API_KEY=
OPENCLAW_AGENT=main
OPENCLAW_WEB_SKILLS=browser-automation
```

OpenClaw 模式是 Gateway 知识库智能体模式。请在宿主机或独立服务启动 OpenClaw Gateway，并在项目根目录 `.env` 中配置：

```text
AGENT_RUNTIME=openclaw
OPENCLAW_ENDPOINT=http://host.docker.internal:<openclaw-port>
OPENCLAW_AGENT=main
```

Docker 容器内不要把 Gateway URL 配成 `127.0.0.1`。宿主机 Gateway 用 `host.docker.internal`，同一 Compose 网络内的 Gateway 用服务名。配置后执行：

```bash
docker compose restart backend
curl -f http://127.0.0.1:8080/api/health
```

常用维护命令：

```bash
docker compose ps
docker compose logs -f backend
docker compose up -d --build
docker compose down
```
