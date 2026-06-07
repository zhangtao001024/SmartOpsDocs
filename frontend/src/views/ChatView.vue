<template>
  <div class="chat-page">
    <section class="chat-hero console-hero">
      <div class="page-heading">
        <p class="page-kicker">Knowledge agent console</p>
        <h2 class="page-title">知识库智能体</h2>
        <p class="page-subtitle">OpenClaw 模式会把知识库片段、会话历史和引用交给 Gateway 智能体；内置模式保留本地检索问答。</p>
        <div class="chat-status-strip console-status-strip">
          <span><strong>{{ mode === 'agent' ? 'Ops Agent' : 'Knowledge Agent' }}</strong> 当前模式</span>
          <span><strong>{{ messages.length }}</strong> 历史消息</span>
          <span><strong>{{ activeContextCount }}</strong> 上下文项</span>
          <span v-if="mode === 'agent'" :class="{ 'run-status-live': !dryRun }">
            <strong>{{ dryRun ? 'Dry-run' : '真实执行' }}</strong> 写操作
          </span>
        </div>
      </div>
      <div class="chat-actions">
        <el-radio-group v-model="mode" size="small">
          <el-radio-button value="knowledge">知识库智能体</el-radio-button>
          <el-radio-button value="agent">运维 Agent</el-radio-button>
        </el-radio-group>
        <div v-if="mode === 'agent'" :class="['dry-run-control', { 'is-live': !dryRun }]">
          <span>
            <strong>{{ dryRun ? 'Dry-run 已开启' : 'Dry-run 已关闭' }}</strong>
            <small>{{ dryRun ? '写操作会被拦截' : '允许写操作' }}</small>
          </span>
          <el-switch v-model="dryRun" inline-prompt active-text="拦" inactive-text="写" />
        </div>
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
                <span class="tool-module">{{ tool.read_only ? '只读' : tool.risk_level || '写操作' }}</span>
              </el-option>
            </el-select>
          </el-form-item>
          <el-form-item label="文档 ID">
            <el-input-number v-model="agentContext.document_id" :min="1" controls-position="right" placeholder="用于优化知识库文档" />
          </el-form-item>
          <el-form-item>
            <el-switch v-model="dryRun" active-text="拦截写操作" inactive-text="允许写操作" />
          </el-form-item>
          <el-form-item>
            <el-switch v-model="autoKnowledge" active-text="生成知识草稿" inactive-text="不沉淀知识" />
          </el-form-item>
        </el-form>
      </aside>
      <div class="chat panel">
      <div class="messages" ref="msgBox">
        <div v-if="messages.length === 0" class="empty-hint">
          <div class="empty-icon"><el-icon><ChatDotRound /></el-icon></div>
          <h3>{{ mode === 'agent' ? '开始一次运维会话' : '向知识库智能体提问' }}</h3>
          <p>{{ mode === 'agent' ? 'Agent 模式会展示工具调用审计，写操作默认被 dry-run 拦截。' : '它会先检索 SmartOpsDocs 知识库，再由 OpenClaw Gateway 或内置模型基于引用回答。' }}</p>
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
            <div v-if="message.mode || message.knowledge_drafts?.length" class="runtime-meta">
              <el-tag v-if="message.mode" size="small" effect="plain">{{ message.mode }}</el-tag>
              <el-tag
                v-for="draft in message.knowledge_drafts || []"
                :key="draft.document_id"
                size="small"
                type="success"
                effect="plain"
                @click="openDraft(draft)"
              >
                草稿 #{{ draft.document_id }}
              </el-tag>
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
      <div class="composer" :class="{ 'with-run-control': mode === 'agent' }">
        <el-input
          v-model="question"
          type="textarea"
          :rows="3"
          :placeholder="mode === 'agent' ? '输入 Agent 目标，例如：检查当前服务器 Docker 容器并分析异常（Enter 发送，Shift+Enter 换行）' : '问知识库智能体，例如：这套系统 Docker 部署有哪些注意事项（Enter 发送，Shift+Enter 换行）'"
          @keydown.enter="onEnter"
          :disabled="loading"
        />
        <div v-if="mode === 'agent'" :class="['composer-run-control', { 'is-live': !dryRun }]">
          <span>{{ dryRun ? 'Dry-run' : '真实执行' }}</span>
          <el-switch v-model="dryRun" inline-prompt active-text="拦" inactive-text="写" />
        </div>
        <el-button type="primary" icon="Promotion" :loading="loading" @click="send" :disabled="!question.trim()">发送</el-button>
      </div>
      </div>
    </div>

    <Teleport to="body">
      <transition name="confirm-fade">
        <div v-if="clearConfirmVisible" class="confirm-overlay" @click.self="closeClearConfirm">
          <section class="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="clear-history-title">
            <div class="confirm-mark">!</div>
            <div class="confirm-copy">
              <h3 id="clear-history-title">清空聊天历史</h3>
              <p>只会删除当前浏览器保存的聊天记录，并重新开始一个会话；不会删除知识库、服务器资产或 OpenClaw 会话文件。</p>
            </div>
            <div class="confirm-actions">
              <button type="button" class="confirm-button secondary" @click="closeClearConfirm">取消</button>
              <button type="button" class="confirm-button danger" @click="confirmClearHistory">清空历史</button>
            </div>
          </section>
        </div>
      </transition>
    </Teleport>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import DOMPurify from 'dompurify'
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
const clearConfirmVisible = ref(false)
const servers = ref([])
const clusters = ref([])
const namespaces = ref([])
const tools = ref([])
const selectedTools = ref([])
const dryRun = ref(true)
const autoKnowledge = ref(true)
const agentContext = reactive({
  server_id: null,
  cluster_id: null,
  namespace: '',
  container_id: '',
  pod_name: '',
  document_id: null,
  path: '',
  command: '',
  timeout: 30,
  tail: 300,
})

const activeContextCount = computed(() => {
  const contextCount = Object.entries(agentContext).filter(([key, value]) => {
    if (['timeout', 'tail'].includes(key)) return false
    return value !== null && value !== undefined && String(value).trim() !== ''
  }).length
  return contextCount + selectedTools.value.length + (autoKnowledge.value ? 1 : 0)
})

function renderMd(text) {
  if (!text) return ''
  return DOMPurify.sanitize(marked.parse(text))
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
  clearConfirmVisible.value = true
}

function closeClearConfirm() {
  clearConfirmVisible.value = false
}

function confirmClearHistory() {
  messages.value = []
  localStorage.removeItem(STORAGE_KEY)
  sessionId.value = Date.now().toString(36)
  clearConfirmVisible.value = false
  ElMessage.success('已清空')
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
  context.auto_knowledge = autoKnowledge.value
  return context
}

function openDraft(draft) {
  if (draft.document_id) router.push({ path: '/documents', query: { doc: draft.document_id } })
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
      tool_calls: data.tool_calls || [],
      mode: data.mode,
      knowledge_drafts: data.knowledge_drafts || []
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
  grid-template-rows: auto minmax(0, 1fr);
  gap: 16px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.chat-status-strip .run-status-live {
  border-color: color-mix(in srgb, var(--app-danger) 46%, var(--app-border-soft));
  color: var(--app-danger);
  background: color-mix(in srgb, var(--app-danger) 10%, var(--app-surface-raised));
}

.chat-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.dry-run-control,
.composer-run-control {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid color-mix(in srgb, var(--app-warning) 42%, var(--app-border-soft));
  border-radius: var(--app-radius);
  background: color-mix(in srgb, var(--app-warning) 9%, var(--app-surface-raised));
  color: var(--app-text);
  box-shadow: var(--app-shadow-xs);
}

.dry-run-control {
  min-height: 48px;
  padding: 8px 16px;
}

.dry-run-control span {
  display: grid;
  gap: 2px;
  min-width: 106px;
}

.dry-run-control strong,
.composer-run-control span {
  color: var(--app-text-heading);
  font-size: 12px;
  font-weight: 750;
  line-height: 1.1;
}

.dry-run-control small {
  color: var(--app-muted);
  font-size: 11px;
  line-height: 1.1;
}

.dry-run-control.is-live,
.composer-run-control.is-live {
  border-color: color-mix(in srgb, var(--app-danger) 58%, var(--app-border-soft));
  background: color-mix(in srgb, var(--app-danger) 11%, var(--app-surface-raised));
}

.dry-run-control.is-live strong,
.composer-run-control.is-live span {
  color: var(--app-danger);
}

.project-input {
  width: 180px;
}

.agent-console {
  display: grid;
  grid-template-columns: 1fr;
  gap: 16px;
  min-height: 0;
  height: 100%;
  overflow: hidden;
}

.agent-console.with-context {
  grid-template-columns: 320px minmax(0, 1fr);
}

.agent-context {
  min-height: 0;
  height: 100%;
  align-self: stretch;
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
  font-family: var(--app-font-display);
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

.context-form :deep(.el-input-number) {
  width: 100%;
}

.chat {
  min-height: 0;
  height: 100%;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: 16px;
  padding: 16px;
}

.messages {
  min-height: 0;
  overflow: auto;
  padding: 8px 8px 0;
}

.empty-hint {
  width: min(100%, 560px);
  margin: 48px auto 0;
  padding: 24px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-lg);
  color: var(--app-muted);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--app-surface-raised) 70%, transparent), transparent),
    repeating-linear-gradient(135deg, rgba(16, 23, 19, 0.025) 0 1px, transparent 1px 18px),
    var(--app-surface-soft);
  box-shadow: var(--app-shadow-xs);
  text-align: center;
}

.empty-hint p {
  margin: 8px auto 0;
  max-width: 48ch;
  line-height: 1.7;
}

.empty-hint h3 {
  margin: 16px 0 0;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
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
  margin-top: 24px;
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
  margin-bottom: 16px;
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
  padding: 16px 24px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--app-surface-raised) 84%, transparent), transparent),
    var(--app-surface-raised);
  box-shadow: var(--app-shadow-xs);
  line-height: 1.7;
  transition: background-color 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.message.user .bubble {
  border-color: var(--app-primary);
  color: #fff;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.15), transparent),
    linear-gradient(140deg, transparent 58%, color-mix(in srgb, var(--app-accent) 34%, transparent)),
    var(--app-primary);
  box-shadow: 0 10px 26px rgba(12, 118, 111, 0.2);
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
  padding: 16px;
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
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border-soft);
}

.tool-calls {
  display: grid;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border-soft);
}

.tool-call {
  padding: 16px;
  border-radius: var(--app-radius);
  border: 1px solid var(--app-border-soft);
  background: var(--app-code-bg);
}

.tool-call div {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 8px;
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

.runtime-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border-soft);
}

.runtime-meta .el-tag {
  cursor: pointer;
}

.ref-tag {
  cursor: pointer;
}

.composer {
  display: grid;
  grid-template-columns: 1fr 120px;
  align-items: stretch;
  gap: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--app-border-soft);
}

.composer.with-run-control {
  grid-template-columns: 1fr 184px 120px;
}

.composer :deep(.el-textarea__inner) {
  min-height: 72px !important;
  resize: none;
}

.composer .el-button {
  min-height: 72px;
}

.composer-run-control {
  justify-content: center;
  min-height: 72px;
  padding: 8px 16px;
}

.composer-run-control span {
  min-width: 52px;
}

.confirm-overlay {
  position: fixed;
  inset: 0;
  z-index: 3000;
  display: grid;
  place-items: center;
  padding: 24px;
  background: color-mix(in srgb, #07100c 48%, transparent);
  backdrop-filter: blur(5px);
}

.confirm-dialog {
  display: grid;
  grid-template-columns: 48px minmax(0, 1fr);
  gap: 16px;
  width: 448px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-lg);
  padding: 24px;
}

.confirm-mark {
  display: grid;
  width: 48px;
  height: 48px;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--app-warning) 42%, var(--app-border));
  border-radius: var(--app-radius);
  color: var(--app-warning);
  background: var(--app-warning-soft);
  font-family: var(--app-font-display);
  font-size: 20px;
  font-weight: 900;
}

.confirm-copy h3 {
  margin: 0;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 18px;
  font-weight: 820;
}

.confirm-copy p {
  margin: 8px 0 0;
  color: var(--app-muted);
  font-size: 13px;
  line-height: 1.65;
}

.confirm-actions {
  grid-column: 1 / -1;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding-top: 8px;
}

.confirm-button {
  min-height: 38px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  padding: 0 16px;
  color: var(--app-text);
  background: var(--app-surface-raised);
  font: inherit;
  font-size: 13px;
  font-weight: 760;
  cursor: pointer;
  transition: transform 0.15s ease, border-color 0.15s ease, background 0.15s ease;
}

.confirm-button:hover {
  transform: translateY(-1px);
  border-color: var(--app-border-strong);
  background: var(--app-surface-hover);
}

.confirm-button.danger {
  border-color: var(--app-danger);
  color: #fff;
  background: var(--app-danger);
}

.confirm-button.danger:hover {
  border-color: color-mix(in srgb, var(--app-danger) 86%, #000);
  background: color-mix(in srgb, var(--app-danger) 86%, #000);
}

.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 0.16s ease;
}

.confirm-fade-enter-active .confirm-dialog,
.confirm-fade-leave-active .confirm-dialog {
  transition: transform 0.16s ease, opacity 0.16s ease;
}

.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}

.confirm-fade-enter-from .confirm-dialog,
.confirm-fade-leave-to .confirm-dialog {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}

</style>
