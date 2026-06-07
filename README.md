# SmartOpsDocs

个人自用版智能运维知识管理平台 MVP。

## 已实现

- FastAPI 后端
- SQLite 数据库
- 管理员登录，默认 `admin / admin123`
- 服务器资产 CRUD、SSH 测试、SSH 终端、服务器资源概览、一次性命令执行
- Docker 容器列表、启动、停止、重启、日志、inspect、进程 top、镜像、网络、卷
- K8s 集群接入、命名空间、Node、Pod、Deployment、StatefulSet、DaemonSet、Service、Ingress、Job、Event、Pod 日志/Describe/JSON、Deployment 重启/伸缩
- 文档上传、解析、切分、入库
- 网页 URL 拉取入库，可单独配置知识拉取模型
- Word 等文档导入后生成标准 Markdown，图片按原文位置保存并在阅读页原位展示
- 查看文档解析全文和分块内容
- 文档解析任务状态、Markdown 修订版本和版本恢复
- 对文档生成 AI 优化稿；未配置大模型时返回本地格式化草稿
- AI 问答接口，支持同一会话近期上下文；未配置 OpenAI 时返回本地知识库检索片段
- Docker 容器 inspect、进程 top、网络/卷视图、可配置 tail 行数日志
- K8s Pod Describe、Pod JSON、Pod 日志、事件查看、Deployment 重启/伸缩
- Vue 3 + Element Plus 前端

## Docker 部署（推荐）

首次部署先准备环境变量：

```bash
cd /root/SmartOpsDocs
cp .env.docker.example .env
```

编辑 `.env`，至少修改：

```text
JWT_SECRET=请改成随机长字符串
INITIAL_ADMIN_PASSWORD=请改成强密码
FRONTEND_PORT=8080
```

启动：

```bash
docker compose up -d --build
```

如果部署机使用旧版 Compose 二进制，把命令中的 `docker compose` 替换为 `docker-compose`。

访问：

```text
http://服务器IP:8080
```

常用运维命令：

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f frontend
docker compose restart backend
docker compose down
```

数据持久化在 Docker volume `smartopsdocs-data` 中，包含 SQLite 数据库、上传文件和知识库解析结果。后端服务只在 Compose 内部网络暴露，外部统一通过前端 Nginx 的 `/api` 反向代理访问。

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
DOCX_VISION_MAX_IMAGES=20
```

前端「模型设置」中可以分别配置：

- AI 助手模型：用于聊天问答
- 知识库优化模型：用于文档优化和 Word 图片理解
- 网页知识拉取模型：用于把网页内容清洗整理成 Markdown 后入库

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

## 网页知识拉取

知识库页面点击「拉取网页」，输入 URL 后会创建后台任务：

1. 抓取网页 HTML
2. 抽取正文
3. 使用「网页知识拉取模型」整理成 Markdown
4. 重建知识库索引

未配置网页知识拉取模型时，会使用本地抽取文本作为 Markdown 草稿。

示例 URL：

```text
https://jimmysong.io/zh/book/kubernetes-handbook/architecture/
```

## Agent 规划

后续 agent 接入预留 OpenClaw 作为内核方向。真实接入时需要确认 OpenClaw 的部署方式、API 地址、认证方式和工具调用协议，再把当前 `/api/agent/knowledge/query` 作为知识检索工具挂入 agent runtime。
