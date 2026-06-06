<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">AI 运维助手</h2>
      <div style="display: flex; gap: 8px; align-items: center">
        <el-input v-model="project" placeholder="知识库项目" style="width: 180px" />
        <el-button icon="Delete" text @click="clearHistory">清空历史</el-button>
      </div>
    </div>
    <div class="chat panel">
      <div class="messages" ref="msgBox">
        <div v-if="messages.length === 0" class="empty-hint">
          <p>💡 基于知识库文档回答运维问题</p>
          <p>未配置 OpenAI 时返回本地片段检索</p>
        </div>
        <div v-for="(message, index) in messages" :key="index" :class="['message', message.role]">
          <div class="bubble">
            <div v-if="message.role === 'user'" class="text">{{ message.content }}</div>
            <div v-else class="markdown-body" v-html="renderMd(message.content)" />
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
          placeholder="输入故障现象或运维问题（Enter 发送，Shift+Enter 换行）"
          @keydown.enter="onEnter"
          :disabled="loading"
        />
        <el-button type="primary" icon="Promotion" :loading="loading" @click="send" :disabled="!question.trim()">发送</el-button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { nextTick, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { marked } from 'marked'
import client from '../api/client'

const STORAGE_KEY = 'smartopsdocs_chat_history'
const router = useRouter()

marked.setOptions({ breaks: true })

const project = ref('default')
const question = ref('')
const loading = ref(false)
const messages = ref([])
const msgBox = ref(null)
const sessionId = ref(Date.now().toString(36))

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

async function send() {
  const text = question.value.trim()
  if (!text || loading.value) return
  messages.value.push({ role: 'user', content: text })
  question.value = ''
  loading.value = true
  scrollBottom()
  try {
    const resp = await client.post('/api/ai/chat', {
      question: text, project: project.value, session_id: sessionId.value
    })
    const data = resp.data
    messages.value.push({
      role: 'assistant',
      content: data.answer,
      references: data.references
    })
    saveHistory()
  } catch (error) {
    messages.value.push({
      role: 'assistant',
      content: '❌ ' + (error.response?.data?.detail || 'AI 问答失败，请稍后重试')
    })
  } finally {
    loading.value = false
    scrollBottom()
  }
}

watch(messages, saveHistory, { deep: true })

onMounted(() => {
  loadHistory()
  scrollBottom()
})
</script>

<style scoped>
.chat {
  min-height: calc(100vh - 150px);
  display: grid;
  grid-template-rows: 1fr auto;
  gap: 14px;
}

.messages {
  overflow: auto;
  padding-right: 4px;
}

.empty-hint {
  text-align: center;
  color: var(--app-muted-soft);
  margin-top: 60px;
}

.empty-hint p {
  margin: 6px 0;
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
  padding: 12px 16px;
  border-radius: var(--app-radius-md);
  background: var(--app-surface-soft);
  line-height: 1.7;
  transition: background-color 0.3s;
}

.message.user .bubble {
  color: #fff;
  background: var(--app-primary);
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

.ref-tag {
  cursor: pointer;
}

.composer {
  display: grid;
  grid-template-columns: 1fr 120px;
  align-items: stretch;
  gap: 10px;
}

@media (max-width: 700px) {
  .composer {
    grid-template-columns: 1fr;
  }
  .bubble {
    max-width: 100%;
  }
}
</style>
