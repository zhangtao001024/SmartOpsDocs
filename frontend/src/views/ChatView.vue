<template>
  <div class="chat-page">
    <section class="chat-hero">
      <div class="page-heading">
        <p class="page-kicker">AI operations console</p>
        <h2 class="page-title">AI 运维助手</h2>
        <p class="page-subtitle">把知识库问答和运维工具调用放在一个会话里，保留引用、审计和执行上下文。</p>
        <div class="chat-status-strip">
          <span><strong>{{ mode === 'agent' ? 'Agent' : 'Knowledge' }}</strong> 当前模式</span>
          <span><strong>{{ messages.length }}</strong> 历史消息</span>
          <span><strong>{{ activeContextCount }}</strong> 上下文项</span>
        </div>
      </div>
      <div class="chat-actions">
        <el-radio-group v-model="mode" size="small">
          <el-radio-button label="knowledge">知识库问答</el-radio-button>
          <el-radio-button label="agent">运维 Agent</el-radio-button>
        </el-radio-group>
        <el-input v-model="project" class="project-input" placeholder="知识库项目" />
        <el-button icon="Delete" text @click="clearHistory">清空历史</el-button>
      </div>
    </section>
    <div class="agent-console" :class="{ 'with-context': mode === 'agent' }">
      <aside v-if="mode === 'agent'" class="agent-context panel">
        <div class="context-header">
          <h3>Agent 上下文</h3>
          <el-tag size="small" :type="dryRun ? 'warning' : 'danger'">{{ dryRun ? 'dry-run' : '执行写操作' }}</el-tag>
        </div>
        <el-form label-position="top" class="context-form">
          <el-form-item label="服务器">
            <el-select v-model="agentContext.server_id" clearable placeholder="选择服务器">
              <el-option v-for="server in servers" :key="server.id" :label="server.ip + ' ' + (server.hostname || '')" :value="server.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="K8s 集群">
            <el-select v-model="agentContext.cluster_id" clearable placeholder="选择集群" @change="loadNamespaces">
              <el-option v-for="cluster in clusters" :key="cluster.id" :label="cluster.name" :value="cluster.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="命名空间">
            <el-select v-model="agentContext.namespace" clearable filterable placeholder="选择命名空间">
              <el-option v-for="ns in namespaces" :key="ns" :label="ns" :value="ns" />
            </el-select>
          </el-form-item>
          <el-form-item label="容器 ID / 名称">
            <el-input v-model="agentContext.container_id" clearable placeholder="用于容器日志、Inspect、操作" />
          </el-form-item>
          <el-form-item label="Pod 名称">
            <el-input v-model="agentContext.pod_name" clearable placeholder="用于 Pod 日志、Describe、删除" />
          </el-form-item>
          <el-form-item label="远程路径">
            <el-input v-model="agentContext.path" clearable placeholder="用于文件浏览或读取" />
          </el-form-item>
          <el-form-item label="SSH 命令">
            <el-input v-model="agentContext.command" type="textarea" :rows="3" placeholder="仅选择 ssh.command 工具时使用" />
          </el-form-item>
          <el-form-item label="工具">
            <el-select v-model="selectedTools" multiple collapse-tags collapse-tags-tooltip clearable placeholder="自动选择">
              <el-option
                v-for="tool in tools"
                :key="tool.name"
                :label="tool.name"
                :value="tool.name"
              >
                <span>{{ tool.name }}</span>
                <span class="tool-module">{{ tool.read_only ? '只读' : '写操作' }}</span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item>
            <el-switch v-model="dryRun" active-text="拦截写操作" inactive-text="允许写操作" />
          </el-form-item>
        </el-form>
      </aside>
      <div class="chat panel">
      <div class="messages" ref="msgBox">
        <div v-if="messages.length === 0" class="empty-hint">
          <div class="empty-icon"><el-icon><ChatDotRound /></el-icon></div>
          <h3>开始一次运维会话</h3>
          <p>Agent 模式会展示工具调用审计，写操作默认被 dry-run 拦截。</p>
          <div class="prompt-suggestions">
            <button type="button" @click="question = '根据知识库总结当前项目的部署步骤'">总结部署步骤</button>
            <button type="button" @click="question = '检查当前服务器 Docker 容器并分析异常'">检查容器异常</button>
            <button type="button" @click="question = '如何排查 Kubernetes Pod 一直 Pending'">排查 Pod Pending</button>
          </div>
        </div>
        <div v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
          <div class="bubble">
            <div v-if="message.role === 'user'" class="text">{{ message.content }}</div>
            <div v-else class="markdown-body" v-html="renderMd(message.content)" />
            <div v-if="message.tool_calls?.length" class="tool-calls">
              <div v-for="call in message.tool_calls" :key="call.tool" class="tool-call">
                <div>
                  <strong>{{ call.tool }}</strong>
                  <span>{{ call.status }}</span>
                </div>
                <pre v-if="call.error">{{ call.error }}</pre>
                <pre v-else>{{ formatToolResult(call.result) }}</pre>
              </div>
            </div>
            <div v-if="message.references?.length" class="refs">
              <el-tag
                v-for="(ref, i) in message.references"
                :key="i"
                size="small"
                type="info"
                class="ref-tag"
                @click="openReference(ref)"
              >
                {{ ref.source }}
              </el-tag>
            </div>
          </div>
        </div>
        <div v-if="loading" class="message assistant">
          <div class="bubble typing">思考中<span class="dots"></span></div>
        </div>
      </div>
      <div class="composer">
        <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          :placeholder="mode === 'agent' ? '输入 Agent 目标，例如：检查当前服务器 Docker 容器并分析异常（Enter 发送，Shift+Enter 换行）' : '输入故障现象或运维问题（Enter 发送，Shift+Enter 换行）'"
          @keydown.enter="onEnter"
          :disabled="loading"
        />
        <el-button type="primary" icon="Promotion" :loading="loading" @click="send" :disabled="!question.trim()">发送</el-button>
      </div>
      </div>
    </div>

  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import client, { getApiErrorMessage } from '../api/client'

const STORAGE_KEY = 'smartopsdocs_chat_history'
const router = useRouter()

marked.setOptions({ breaks: true })

const project = ref('default')
const mode = ref('agent')
const question = ref('')
const loading = ref(false)
const messages = ref([])
const msgBox = ref(null)
const sessionId = ref(Date.now().toString(36))
const servers = ref([])
const clusters = ref([])
const namespaces = ref([])
const tools = ref([])
const selectedTools = ref([])
const dryRun = ref(true)
const agentContext = reactive({
  server_id: null,
  cluster_id: null,
  namespace: '',
  container_id: '',
  pod_name: '',
  path: '',
  command: '',
  timeout: 30,
  tail: 300,
})

const activeContextCount = computed(() => {
  const contextCount = Object.values(agentContext).filter((value) => {
    return value !== null && value !== undefined && String(value).trim() !== ''
  }).length
  return contextCount + selectedTools.value.length
})

function renderMd(text) {
  if (!text) return ''
  return marked.parse(text)
}

function loadHistory() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) messages.value = JSON.parse(raw)
  } catch { /* ignore */ }
}

function saveHistory() {
  try {
    const keep = messages.value.slice(-60)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(keep))
  } catch { /* ignore */ }
}

function clearHistory() {
  ElMessageBox.confirm('确定清空所有聊天记录？', '确认', { type: 'warning', center: true }).then(() => {
    messages.value = []
    localStorage.removeItem(STORAGE_KEY)
    sessionId.value = Date.now().toString(36)
    ElMessage.success('已清空')
  }).catch(() => {})
}

function scrollBottom() {
  nextTick(() => {
    const el = msgBox.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

function onEnter(e) {
  if (e.shiftKey) return
  e.preventDefault()
  send()
}

function openReference(ref) {
  if (ref.document_id) {
    router.push({ path: '/documents', query: { doc: ref.document_id } })
  }
}

function formatToolResult(result) {
  if (!result) return ''
  const text = typeof result === 'string' ? result : JSON.stringify(result, null, 2)
  return text.length > 1800 ? text.slice(0, 1800) + '\n...已截断' : text
}

function buildAgentContext() {
  const context = {}
  Object.entries(agentContext).forEach(([key, value]) => {
    if (value !== null && value !== undefined && String(value).trim() !== '') context[key] = value
  })
  return context
}

async function loadAgentMeta() {
  try {
    const [serverResp, clusterResp, toolResp] = await Promise.all([
      client.get('/api/servers'),
      client.get('/api/k8s/clusters'),
      client.get('/api/ai/agent/tools'),
    ])
    servers.value = serverResp.data
    clusters.value = clusterResp.data
    tools.value = toolResp.data
  } catch {
    tools.value = []
  }
}

async function loadNamespaces() {
  namespaces.value = []
  agentContext.namespace = ''
  if (!agentContext.cluster_id) return
  try {
    namespaces.value = (await client.get(`/api/k8s/clusters/${agentContext.cluster_id}/namespaces`)).data
    agentContext.namespace = namespaces.value[0] || ''
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取命名空间失败'))
  }
}

async function send() {
  const text = question.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', content: text })
  question.value = ''
  loading.value = true
  scrollBottom()
  try {
    const payload = mode.value === 'agent'
      ? {
          goal: text,
          project: project.value,
          session_id: sessionId.value,
          tools: selectedTools.value,
          dry_run: dryRun.value,
          context: buildAgentContext(),
        }
      : {
          question: text,
          project: project.value,
          session_id: sessionId.value,
        }
    const resp = await client.post(mode.value === 'agent' ? '/api/ai/agent' : '/api/ai/chat', payload)
    const data = resp.data
    messages.value.push({
      role: 'assistant',
      content: data.answer,
      references: data.references,
      tool_calls: data.tool_calls || []
    })
    saveHistory()
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: getApiErrorMessage(error, 'AI 问答失败，请稍后重试')
    })
  } finally {
    loading.value = false
    scrollBottom()
  }
}

watch(messages, saveHistory, { deep: true })

onMounted(() => {
  loadHistory()
  loadAgentMeta()
  scrollBottom()
})
</script>

<style scoped>
.chat-page {
  display: grid;
  gap: 18px;
}

.chat-hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  padding: 24px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background:
    linear-gradient(90deg, rgba(15, 118, 110, 0.1), transparent 42%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.18)),
    var(--app-surface);
  box-shadow: var(--app-shadow);
}

:global(html.dark) .chat-hero {
  background:
    linear-gradient(90deg, rgba(45, 212, 191, 0.1), transparent 44%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.015)),
    var(--app-surface);
}

.chat-status-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

.chat-status-strip span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 6px 10px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius);
  color: var(--app-muted);
  background: color-mix(in srgb, var(--app-surface-raised) 76%, transparent);
  box-shadow: var(--app-shadow-xs);
  font-size: 12px;
  font-weight: 650;
}

.chat-status-strip strong {
  color: var(--app-text-heading);
  font-variant-numeric: tabular-nums;
}

.chat-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.project-input {
  width: 180px;
}

.agent-console {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
}

.agent-console.with-context {
  grid-template-columns: minmax(290px, 330px) minmax(0, 1fr);
}

.agent-context {
  min-height: calc(100dvh - 244px);
  align-self: start;
  position: sticky;
  top: 86px;
  max-height: calc(100dvh - 112px);
  overflow: auto;
}

.context-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}

.context-header h3 {
  margin: 0;
  color: var(--app-text-heading);
  font-size: 16px;
}

.context-form :deep(.el-form-item) {
  margin-bottom: 12px;
}

.tool-module {
  float: right;
  color: var(--app-muted-soft);
  font-size: 12px;
}

.chat {
  min-height: calc(100dvh - 244px);
  display: grid;
  grid-template-rows: 1fr auto;
  gap: 16px;
  padding: 16px;
}

.messages {
  overflow: auto;
  padding: 4px 4px 0;
}

.empty-hint {
  width: min(100%, 560px);
  margin: 72px auto 0;
  padding: 28px;
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-lg);
  color: var(--app-muted);
  background: var(--app-surface-soft);
  text-align: center;
}

.empty-hint p {
  margin: 8px auto 0;
  max-width: 48ch;
  line-height: 1.7;
}

.empty-hint h3 {
  margin: 14px 0 0;
  color: var(--app-text-heading);
  font-size: 20px;
}

.empty-icon {
  display: grid;
  width: 44px;
  height: 44px;
  margin: 0 auto;
  border-radius: var(--app-radius-md);
  color: var(--app-primary);
  background: var(--app-primary-soft);
  place-items: center;
  font-size: 22px;
}

.prompt-suggestions {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px;
  margin-top: 18px;
}

.prompt-suggestions button {
  padding: 8px 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  color: var(--app-text-soft);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-xs);
  font-size: 12px;
  font-weight: 650;
  cursor: pointer;
  transition: border-color 0.16s ease, background-color 0.16s ease, color 0.16s ease, transform 0.16s ease;
}

.prompt-suggestions button:hover {
  border-color: var(--app-primary-border);
  color: var(--app-primary);
  background: var(--app-primary-softer);
  transform: translateY(-1px);
}

.message {
  display: flex;
  margin-bottom: 12px;
  animation: msgIn 0.3s ease-out;
}

@keyframes msgIn {
  from { opacity: 0; transform: translateY(8px); }
  to   { opacity: 1; transform: translateY(0); }
}

.message.user {
  justify-content: flex-end;
}

.bubble {
  max-width: min(800px, 88%);
  padding: 13px 16px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-surface-raised);
  box-shadow: var(--app-shadow-xs);
  line-height: 1.7;
  transition: background-color 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.message.user .bubble {
  border-color: var(--app-primary);
  color: #fff;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.14), transparent),
    var(--app-primary);
  box-shadow: 0 10px 26px rgba(15, 118, 110, 0.18);
}

.message.user .bubble .text {
  white-space: pre-wrap;
  word-break: break-word;
}

.bubble.typing {
  color: var(--app-muted-soft);
  font-style: italic;
}

.dots::after {
  content: '';
  animation: dots 1.5s steps(4, end) infinite;
}

@keyframes dots {
  0% { content: ''; }
  25% { content: '.'; }
  50% { content: '..'; }
  75% { content: '...'; }
}

.bubble :deep(pre) {
  background: var(--app-code-bg);
  padding: 10px 14px;
  border-radius: var(--app-radius);
  overflow-x: auto;
  font-size: 13px;
  font-family: var(--app-font-mono);
  margin: 8px 0;
}

.bubble :deep(code) {
  font-family: var(--app-font-mono);
  font-size: 13px;
  background: var(--app-code-bg);
  color: var(--app-code-text);
  padding: 1px 5px;
  border-radius: 3px;
}

.user .bubble :deep(pre),
.user .bubble :deep(code) {
  background: rgba(255,255,255,0.15);
  color: rgba(255,255,255,0.95);
}

.bubble :deep(table) {
  border-collapse: collapse;
  margin: 8px 0;
  width: 100%;
}

.bubble :deep(th),
.bubble :deep(td) {
  border: 1px solid var(--app-border-strong);
  padding: 6px 10px;
  text-align: left;
}

.bubble :deep(th) {
  background: var(--app-surface-soft);
  font-weight: 600;
}

.bubble :deep(h1), .bubble :deep(h2), .bubble :deep(h3) {
  margin: 12px 0 6px;
  color: var(--app-text-heading);
}

.bubble :deep(ul), .bubble :deep(ol) {
  padding-left: 20px;
  margin: 4px 0;
}

.bubble :deep(blockquote) {
  border-left: 3px solid var(--app-border-strong);
  padding-left: 12px;
  margin: 6px 0;
  color: var(--app-muted);
}

.refs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 10px;
  padding-top: 8px;
  border-top: 1px solid var(--app-border-soft);
}

.tool-calls {
  display: grid;
  gap: 8px;
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--app-border-soft);
}

.tool-call {
  padding: 10px;
  border-radius: var(--app-radius);
  background: var(--app-code-bg);
}

.tool-call div {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 6px;
}

.tool-call strong {
  color: var(--app-text-heading);
}

.tool-call span {
  color: var(--app-muted-soft);
  font-size: 12px;
}

.tool-call pre {
  max-height: 220px;
  overflow: auto;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.ref-tag {
  cursor: pointer;
}

.composer {
  display: grid;
  grid-template-columns: 1fr 120px;
  align-items: stretch;
  gap: 10px;
  padding-top: 14px;
  border-top: 1px solid var(--app-border-soft);
}

.composer :deep(.el-textarea__inner) {
  min-height: 84px !important;
  resize: none;
}

.composer .el-button {
  min-height: 84px;
}

@media (max-width: 900px) {
  .chat-hero {
    align-items: stretch;
    flex-direction: column;
    padding: 20px;
  }

  .chat-actions {
    justify-content: flex-start;
  }

  .agent-console.with-context {
    grid-template-columns: 1fr;
  }

  .agent-context {
    position: static;
    min-height: auto;
    max-height: none;
  }

  .composer {
    grid-template-columns: 1fr;
  }

  .composer .el-button {
    min-height: 42px;
  }

  .bubble {
    max-width: 100%;
  }
}
</style>
