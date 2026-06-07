# SmartOpsDocs

个人自用版智能运维知识管理平台 MVP。

## 已实现

- FastAPI 后端
- SQLite 数据库
- 管理员登录，默认 `admin / admin123`
- 服务器资产 CRUD、SSH 测试、SSH 终端、服务器资源概览、一次性命令执行
- Docker 容器列表、启动、停止、重启、日志、inspect、进程 top、镜像、网络、卷
- K8s 集群接入、命名空间、Node、Pod、Deployment、StatefulSet、DaemonSet、Service、Ingress、Job、Event、Pod 日志/Describe/JSON、Deployment 重启/伸缩
- 文档上传、解析、Markdown-aware 切分、入库
- 知识库混合检索：Embedding 向量语义召回 + SQLite FTS5/LIKE 关键词召回
- 网页 URL 拉取入库，可单独配置知识拉取模型，并按知识库结构过滤噪声内容
- Word 等文档导入后生成标准 Markdown，图片按原文位置保存并在阅读页原位展示
- 查看文档解析全文和分块内容
- 文档解析任务状态、Markdown 修订版本和版本恢复
- 对文档生成 AI 优化稿；未配置大模型时返回本地格式化草稿
- AI 问答接口，支持同一会话近期上下文；未配置 OpenAI 时返回本地知识库检索片段
- Docker 容器 inspect、进程 top、网络/卷视图、可配置 tail 行数日志
- K8s Pod Describe、Pod JSON、Pod 日志、事件查看、Deployment 重启/伸缩
- Vue 3 + Element Plus 前端

## Docker 部署

推荐用 Docker Compose 部署。前端容器会暴露 Web 端口，后端只在 Compose 内部网络提供 API，由前端 Nginx 反向代理 `/api`。

### 1. 准备配置

首次部署先复制环境变量模板：

```bash
cd /root/SmartOpsDocs
cp .env.docker.example .env
```

编辑 `.env`，至少修改这些值：

```text
JWT_SECRET=请改成随机长字符串
INITIAL_ADMIN_PASSWORD=请改成强密码
FRONTEND_PORT=8080
```

常用可选配置：

```text
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
OPENAI_VISION_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
DOCX_VISION_MAX_IMAGES=20
MAX_UPLOAD_SIZE_MB=50
```

`OPENAI_API_KEY` 留空时，知识库仍可用关键词检索、文档解析和本地草稿；配置后会启用聊天问答、文档优化、网页清洗、图片理解和向量检索等模型能力。也可以部署后在前端「模型设置」里分别填写不同模型入口。

### 2. 启动

首次启动或代码更新后执行：

```bash
docker compose up -d --build
```

如果部署机使用旧版 Compose 二进制，把命令中的 `docker compose` 替换为 `docker-compose`。

访问：

```text
http://服务器IP:8080
```

默认管理员账号来自 `.env`：

```text
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=你配置的密码
```

### 3. 验证

```bash
docker compose ps
curl -f http://127.0.0.1:8080/api/health
docker compose logs --tail=100 backend
```

前端打开后建议依次检查：

- 登录是否成功
- 「模型设置」里各模型测试是否通过
- 「知识库」上传一篇 Markdown/TXT 文档后能否解析、检索
- 如果启用 OpenClaw，点击「知识库智能体」的测试按钮，确认 Gateway 显示可达

### 4. 常用运维

常用运维命令：

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose restart backend
docker compose down
```

升级代码后：

```bash
git pull
docker compose up -d --build
```

查看数据卷：

```bash
docker volume inspect smartopsdocs_smartopsdocs-data
```

备份数据卷到当前目录：

```bash
docker run --rm -v smartopsdocs_smartopsdocs-data:/data -v "$PWD":/backup alpine tar czf /backup/smartopsdocs-data.tgz -C /data .
```

恢复前请先停止服务，并确认会覆盖现有数据库和知识库文件：

```bash
docker compose down
docker run --rm -v smartopsdocs_smartopsdocs-data:/data -v "$PWD":/backup alpine sh -c 'cd /data && tar xzf /backup/smartopsdocs-data.tgz'
docker compose up -d
```

数据持久化在 Docker volume `smartopsdocs_smartopsdocs-data` 中，包含 SQLite 数据库、上传文件和知识库解析结果。

### 5. OpenClaw Gateway 知识库智能体

OpenClaw 模式只走 Gateway，不再把 CLI、本地兼容和多套调用入口混在一起。Docker 部署时，SmartOpsDocs 容器不能直接访问宿主机的 `127.0.0.1`，所以需要使用 `host.docker.internal` 或把 OpenClaw Gateway 放进同一个 Compose 网络。

宿主机运行 OpenClaw Gateway 时，在 `.env` 中配置：

```text
AGENT_RUNTIME=openclaw
OPENCLAW_ENDPOINT=http://host.docker.internal:<openclaw-port>
OPENCLAW_API_KEY=
OPENCLAW_AGENT=main
OPENCLAW_WEB_SKILLS=browser-automation
```

`docker-compose.yml` 已配置：

```yaml
extra_hosts:
  - "host.docker.internal:host-gateway"
```

如果 OpenClaw Gateway 只监听 `127.0.0.1` 且容器访问失败，需要让 Gateway 监听宿主机网卡可访问地址，或以独立服务加入同一个 Compose 网络。配置完成后重启后端：

```bash
docker compose restart backend
```

然后到前端「模型设置」测试「知识库智能体」。测试通过后，知识库问答、运维 Agent 回答和网页知识拉取都会优先把上下文交给 OpenClaw Gateway。

### 6. 常见问题

- 登录失败：检查 `.env` 中的 `INITIAL_ADMIN_USERNAME` / `INITIAL_ADMIN_PASSWORD`。如果数据库已初始化，修改环境变量不会覆盖已有用户，需要在数据库内重置或清空数据卷重新初始化。
- 前端能打开但 API 失败：检查 `docker compose ps`、`docker compose logs -f backend`，并确认 `curl http://127.0.0.1:8080/api/health` 返回正常。
- OpenClaw 测试成功但状态未保存：点击「保存配置」后后端才会持久化 Gateway URL；测试按钮会验证当前表单值。
- OpenClaw Gateway 不可达：不要把容器内的 Endpoint 配成 `http://127.0.0.1:<port>`，改用 `http://host.docker.internal:<port>` 或 Compose 服务名。
- 向量检索没有效果：确认 `OPENAI_EMBEDDING_MODEL` 和 Embedding API Key 可用；老文档需要重新解析或保存一次 Markdown 才会生成向量。

## 本地开发

启动后端：

```bash
cd /root/SmartOpsDocs/backend
python3 -m pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动前端：

```bash
cd /root/SmartOpsDocs/frontend
npm install
npm run dev
```

前端构建和 smoke 测试:

```bash
cd /root/SmartOpsDocs/frontend
npm run build
npm run smoke
```

## 后端测试和迁移

```bash
cd /root/SmartOpsDocs/backend
pytest
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```

当前仍保留启动时 `create_all` 的 MVP 兼容逻辑；后续正式部署建议用 Alembic 迁移管理表结构。

本地开发访问：

```text
http://服务器IP:5173
```

## OpenAI 配置

Docker 部署时编辑项目根目录 `.env`；本地开发时复制 `/root/SmartOpsDocs/backend/.env.example` 为 `/root/SmartOpsDocs/backend/.env`。

常用配置：

```text
JWT_SECRET=请改成随机长字符串
INITIAL_ADMIN_USERNAME=admin
INITIAL_ADMIN_PASSWORD=请改成强密码
CORS_ORIGINS=http://127.0.0.1:8080,http://localhost:8080
MAX_UPLOAD_SIZE_MB=50
OPENAI_API_KEY=你的 key
OPENAI_BASE_URL=
OPENAI_MODEL=gpt-4o-mini
OPENAI_VISION_MODEL=gpt-4o-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
DOCX_VISION_MAX_IMAGES=20
AGENT_RUNTIME=local-openclaw
OPENCLAW_ENDPOINT=
OPENCLAW_API_KEY=
OPENCLAW_AGENT=main
OPENCLAW_WEB_SKILLS=browser-automation
```

前端「模型设置」中可以分别配置：

- AI 助手模型：用于聊天问答
- 知识库优化模型：用于文档优化和 Word 图片理解
- 网页知识拉取模型：用于把网页内容清洗整理成 Markdown 后入库
- 向量检索模型：用于知识库语义检索；未配置时自动退回 FTS/LIKE 关键词检索
- OpenClaw Gateway 知识库智能体：开启后，知识库问答、运维 Agent 回答和网页知识拉取都会优先交给 OpenClaw Gateway；能力偏好通过 `OPENCLAW_WEB_SKILLS` 随请求传给 Gateway，由 OpenClaw 侧 Agent 配置决定实际可用工具。

图文 Word 解析策略：

- `.docx` 会按原文顺序转换为 Markdown，正文、表格和内嵌图片会尽量保持原始位置
- 图片会保存到 `KNOWLEDGE_DIR/<document_id>/assets/`，生成的 Markdown 保存在 `KNOWLEDGE_DIR/<document_id>/content.md`
- 配置 `OPENAI_API_KEY` 后，图片可交给视觉大模型解析，适合识别截图、报错、拓扑图、表格截图
- 未配置大模型时，会尝试本地 OCR；当前机器如果没有 `tesseract` 命令，会保留图片但不生成图片文字
- `DOCX_VISION_MAX_IMAGES` 用来限制每个 Word 最多解析多少张图片，避免成本失控

当前版本为自用 MVP。服务器 SSH 凭据、KubeConfig 和模型 Key 仍按明文字段存储；接口列表已避免回传 SSH 密码/私钥，但给多人使用前仍需要补加密、权限和审计。

> 当前规划备注：先不改安全类能力，短期继续按个人自用 MVP 推进功能和体验；安全加固作为已知风险保留，等准备多人使用或公网部署前再集中处理。

## 文档优化建议

AI 优化结果建议作为新草稿审核，不要直接覆盖原始文档。适合用于：

- 零散操作记录整理成 Runbook
- 提取故障排查步骤
- 规范部署、升级、回滚 SOP
- 补齐验证方法和注意事项的小节结构

## Agent 调用知识库

外部 AI 助手或 agent 可使用登录得到的 Bearer Token 调用结构化检索接口：

```http
POST /api/agent/knowledge/query
Authorization: Bearer <token>
Content-Type: application/json
```

```json
{
  "query": "如何排查 Pod 异常",
  "project": "default",
  "limit": 5
}
```

返回结果包含 `document_id`、`document_title`、`chunk_id`、`source`、`content` 和 `preview`，可直接作为 RAG 上下文。

配置向量检索模型后，新解析或重新保存的文档会为每个 chunk 写入 embedding。检索时会把向量相似度和关键词命中融合排序；老文档需要重新解析或保存一次 Markdown 才会生成向量索引。

## 网页知识拉取

知识库页面点击「拉取网页」，输入 URL 后会创建后台任务：

1. 抓取网页 HTML
2. 抽取正文并过滤导航、广告、版权、评论、推荐文章等低价值内容
3. 使用「网页知识拉取模型」整理成固定 Markdown 知识结构
4. 重建知识库索引

未配置网页知识拉取模型时，会使用规则过滤后的正文生成结构化 Markdown 草稿。

示例 URL：

```text
https://jimmysong.io/zh/book/kubernetes-handbook/architecture/
```
