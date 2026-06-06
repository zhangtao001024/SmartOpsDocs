# SmartOpsDocs Backend

默认管理员账号:

```text
admin / admin123
```

推荐从项目根目录使用 Docker Compose 部署：

```bash
cd /root/SmartOpsDocs
cp .env.docker.example .env
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
```

本地开发启动后端：

```bash
cd backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```
