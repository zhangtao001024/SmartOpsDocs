<template>
  <div class="knowledge-page">
    <div class="toolbar">
      <h2 class="page-title">知识库</h2>
      <div class="toolbar-actions">
        <el-input v-model="project" placeholder="项目" clearable @change="load" />
        <el-button icon="Refresh" @click="load">刷新</el-button>
      </div>
    </div>

    <div class="knowledge-shell">
      <aside class="kb-nav">
        <el-upload
          drag
          action="/api/documents/upload"
          :headers="headers"
          :data="{ project: project || 'default' }"
          :on-success="onSuccess"
          :on-error="onError"
          accept=".docx,.md,.pdf,.txt"
          class="upload-box"
        >
          <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
          <div class="el-upload__text">上传文档</div>
        </el-upload>

        <div class="doc-list" v-loading="loading">
          <button
            v-for="doc in documents"
            :key="doc.id"
            :class="['doc-item', { active: selectedId === doc.id }]"
            type="button"
            @click="openDocument(doc)"
          >
            <span class="doc-title">{{ doc.title }}</span>
            <span class="doc-meta">
              <el-tag :type="statusType(doc.status)" size="small">{{ doc.status }}</el-tag>
              <span>{{ doc.chunk_count || 0 }} chunks</span>
            </span>
          </button>
        </div>
      </aside>

      <main class="reader" ref="articleRef">
        <template v-if="detail">
          <header class="reader-header">
            <div>
              <h1>{{ detail.title }}</h1>
              <div class="reader-meta">
                <span>{{ detail.project }}</span>
                <span>{{ detail.chunks?.length || 0 }} chunks</span>
                <span>{{ documentStats.words }} 字</span>
                <span>约 {{ documentStats.minutes }} 分钟</span>
              </div>
            </div>
            <div class="reader-actions">
              <el-button icon="EditPen" @click="openEditor(detail)">编辑</el-button>
              <el-button icon="Clock" @click="openTasks(detail)">任务</el-button>
              <el-button icon="Files" @click="openRevisions(detail)">版本</el-button>
              <el-button icon="Refresh" :loading="reprocessing" @click="reprocess(detail)">重新解析</el-button>
              <el-button icon="MagicStick" type="primary" @click="openOptimize(detail)">优化</el-button>
              <el-popconfirm title="确定删除此文档？" confirm-button-text="删除" @confirm="removeDoc(detail)">
                <template #reference>
                  <el-button icon="Delete" type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </header>

          <el-alert
            v-if="detail.status !== 'completed'"
            :title="detail.latest_task?.message || detail.error_message || statusText(detail.status)"
            :type="detail.status === 'failed' ? 'error' : 'warning'"
            :closable="false"
            show-icon
            class="reader-alert"
          />

          <article class="article-body markdown-body" v-html="renderMd(detail.content || '')" />
        </template>

        <div v-else class="empty-reader">
          <el-empty description="暂无可阅读文档" />
        </div>
      </main>

      <aside class="kb-aside">
        <section class="aside-section">
          <div class="aside-title">检索</div>
          <el-input
            v-model="searchText"
            placeholder="搜索知识库"
            clearable
            @keyup.enter="searchKnowledge"
          >
            <template #append>
              <el-button icon="Search" :loading="searching" @click="searchKnowledge" />
            </template>
          </el-input>
          <div class="search-results">
            <button
              v-for="item in searchResults"
              :key="item.chunk_id"
              type="button"
              class="search-result"
              @click="openSearchResult(item)"
            >
              <strong>{{ item.document_title }}</strong>
              <span>{{ item.preview }}</span>
            </button>
          </div>
        </section>

        <section class="aside-section">
          <div class="aside-title">目录</div>
          <div v-if="toc.length" class="toc">
            <button
              v-for="(item, index) in toc"
              :key="index"
              type="button"
              :class="'toc-level-' + item.level"
              @click="scrollToHeading(item)"
            >
              {{ item.text }}
            </button>
          </div>
          <p v-else class="aside-empty">当前文档没有标题层级</p>
        </section>

        <section class="aside-section agent-section">
          <div class="aside-title">Agent API</div>
          <code>POST /api/agent/knowledge/query</code>
          <pre>{
  "query": "{{ searchText || '如何排查 Pod 异常' }}",
  "project": "{{ project || 'default' }}",
  "limit": 5
}</pre>
        </section>
      </aside>
    </div>

    <el-dialog v-model="optimizeVisible" title="AI 优化文档" width="980px">
      <el-alert
        title="建议把优化结果作为新草稿审核，不要直接覆盖原始文档。"
        type="info"
        show-icon
        :closable="false"
        style="margin-bottom: 12px"
      />
      <el-input
        v-model="instruction"
        type="textarea"
        :rows="3"
        placeholder="可选：例如整理成部署 Runbook、提取故障排查步骤、规范成 SOP"
      />
      <div class="optimize-actions">
        <el-button type="primary" icon="MagicStick" :loading="optimizing" @click="optimize">生成优化稿</el-button>
        <el-tag v-if="optimizeMode" size="small">{{ optimizeMode }}</el-tag>
      </div>
      <pre class="optimized-output">{{ optimizedText || '点击生成后显示优化结果' }}</pre>
    </el-dialog>

    <el-dialog v-model="editorVisible" title="编辑 Markdown" width="1080px">
      <el-input
        v-model="editorContent"
        type="textarea"
        :rows="24"
        class="markdown-editor"
      />
      <template #footer>
        <el-button @click="editorVisible = false">取消</el-button>
        <el-button type="primary" icon="Check" :loading="editorSaving" @click="saveEditor">保存并重建索引</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tasksVisible" title="文档任务" width="760px">
      <el-table :data="tasks" v-loading="tasksLoading">
        <el-table-column prop="task_type" label="类型" width="120" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column label="进度" width="180">
          <template #default="{ row }">
            <el-progress :percentage="row.progress || 0" />
          </template>
        </el-table-column>
        <el-table-column prop="message" label="消息" />
        <el-table-column prop="updated_at" label="更新时间" width="180" />
      </el-table>
    </el-dialog>

    <el-dialog v-model="revisionsVisible" title="文档版本" width="860px">
      <el-table :data="revisions" v-loading="revisionsLoading">
        <el-table-column prop="version" label="版本" width="90" />
        <el-table-column prop="note" label="来源" width="130" />
        <el-table-column prop="preview" label="预览" />
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button size="small" @click="restoreRevision(row)">恢复</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { marked } from 'marked'
import client from '../api/client'

marked.setOptions({ breaks: true })

const route = useRoute()
const project = ref('default')
const documents = ref([])
const loading = ref(false)
const detail = ref(null)
const selectedId = ref(null)
const articleRef = ref(null)
const searchText = ref('')
const searchResults = ref([])
const searching = ref(false)
const optimizeVisible = ref(false)
const selectedDocument = ref(null)
const instruction = ref('')
const optimizedText = ref('')
const optimizeMode = ref('')
const optimizing = ref(false)
const reprocessing = ref(false)
const editorVisible = ref(false)
const editorContent = ref('')
const editorSaving = ref(false)
const tasksVisible = ref(false)
const tasksLoading = ref(false)
const tasks = ref([])
const revisionsVisible = ref(false)
const revisionsLoading = ref(false)
const revisions = ref([])
const headers = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('smartopsdocs_token') || ''}` }))

const documentStats = computed(() => {
  const text = detail.value?.content || ''
  const words = text.replace(/\s/g, '').length
  return { words, minutes: Math.max(1, Math.ceil(words / 600)) }
})

const toc = computed(() => {
  const text = detail.value?.content || ''
  const rows = []
  for (const line of text.split('\n')) {
    const match = /^(#{1,4})\s+(.+)$/.exec(line.trim())
    if (match) rows.push({ level: match[1].length, text: match[2].replace(/[#`*_]/g, '').trim() })
  }
  return rows.slice(0, 40)
})

function renderMd(text) {
  if (!text) return '<p class="muted">暂无解析内容</p>'
  return marked.parse(text)
}

function statusType(status) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'parsing') return 'warning'
  return 'info'
}

function statusText(status) {
  if (status === 'parsing') return '文档正在解析'
  if (status === 'uploaded') return '文档已上传，等待解析'
  return status || '未知状态'
}

async function load() {
  loading.value = true
  try {
    documents.value = (await client.get('/api/knowledge/tree', { params: { project: project.value || undefined } })).data
    const routeDocId = Number(route.query.doc || 0)
    if (routeDocId && selectedId.value !== routeDocId) {
      await openDocumentById(routeDocId)
    } else if (!detail.value && documents.value.length) {
      await openDocument(documents.value[0])
    } else if (selectedId.value && !documents.value.some((doc) => doc.id === selectedId.value)) {
      detail.value = null
      selectedId.value = null
    }
  } finally {
    loading.value = false
  }
}

async function openDocument(doc) {
  selectedId.value = doc.id
  detail.value = (await client.get(`/api/documents/${doc.id}`)).data
  nextTick(() => {
    if (articleRef.value) articleRef.value.scrollTop = 0
  })
}

async function openDocumentById(id) {
  const doc = documents.value.find((item) => item.id === id) || { id }
  await openDocument(doc)
}

function onSuccess() {
  ElMessage.success('已上传，后台正在解析')
  setTimeout(load, 800)
}

function onError(error) {
  ElMessage.error(error.message || '上传失败')
}

async function searchKnowledge() {
  const q = searchText.value.trim()
  if (!q) {
    searchResults.value = []
    return
  }
  searching.value = true
  try {
    const { data } = await client.get('/api/knowledge/search', {
      params: { q, project: project.value || 'default', limit: 8 }
    })
    searchResults.value = data.results || []
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '检索失败')
  } finally {
    searching.value = false
  }
}

async function openSearchResult(item) {
  await openDocumentById(item.document_id)
}

function scrollToHeading(item) {
  nextTick(() => {
    const root = articleRef.value
    if (!root) return
    const headings = Array.from(root.querySelectorAll(`.article-body h${item.level}`))
    const target = headings.find((node) => node.textContent.trim() === item.text)
    if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
}

function openOptimize(row) {
  selectedDocument.value = row
  instruction.value = ''
  optimizedText.value = ''
  optimizeMode.value = ''
  optimizeVisible.value = true
}

function openEditor(row) {
  selectedDocument.value = row
  editorContent.value = row.raw_content || row.content || ''
  editorVisible.value = true
}

async function saveEditor() {
  if (!selectedDocument.value) return
  editorSaving.value = true
  try {
    const { data } = await client.put(`/api/documents/${selectedDocument.value.id}/markdown`, {
      content: editorContent.value
    })
    detail.value = data
    selectedId.value = data.id
    editorVisible.value = false
    ElMessage.success('Markdown 已保存，索引已重建')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存失败')
  } finally {
    editorSaving.value = false
  }
}

async function reprocess(row) {
  reprocessing.value = true
  try {
    const { data } = await client.post(`/api/documents/${row.id}/reprocess`)
    detail.value = data
    selectedId.value = data.id
    ElMessage.success('已重新解析')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '重新解析失败')
  } finally {
    reprocessing.value = false
  }
}

async function openTasks(row) {
  selectedDocument.value = row
  tasksVisible.value = true
  tasksLoading.value = true
  try {
    tasks.value = (await client.get(`/api/documents/${row.id}/tasks`)).data
  } finally {
    tasksLoading.value = false
  }
}

async function openRevisions(row) {
  selectedDocument.value = row
  revisionsVisible.value = true
  revisionsLoading.value = true
  try {
    revisions.value = (await client.get(`/api/documents/${row.id}/revisions`)).data
  } finally {
    revisionsLoading.value = false
  }
}

async function restoreRevision(row) {
  if (!selectedDocument.value) return
  try {
    const { data } = await client.post(`/api/documents/${selectedDocument.value.id}/revisions/${row.id}/restore`)
    detail.value = data
    selectedId.value = data.id
    revisionsVisible.value = false
    ElMessage.success('已恢复该版本')
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '恢复失败')
  }
}

async function optimize() {
  if (!selectedDocument.value) return
  optimizing.value = true
  try {
    const { data } = await client.post(`/api/documents/${selectedDocument.value.id}/optimize`, {
      instruction: instruction.value
    })
    optimizedText.value = data.optimized
    optimizeMode.value = data.mode === 'llm' ? '大模型生成' : '本地草稿'
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '优化失败')
  } finally {
    optimizing.value = false
  }
}

async function removeDoc(row) {
  try {
    await client.delete(`/api/documents/${row.id}`)
    ElMessage.success('文档已删除')
    detail.value = null
    selectedId.value = null
    await load()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除失败')
  }
}

watch(() => route.query.doc, () => {
  const id = Number(route.query.doc || 0)
  if (id) openDocumentById(id)
})

onMounted(load)
</script>

<style scoped>
.knowledge-page {
  min-height: calc(100vh - 96px);
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.toolbar-actions .el-input {
  width: 180px;
}

.knowledge-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 280px;
  gap: 16px;
  min-height: calc(100vh - 150px);
}

.kb-nav,
.reader,
.kb-aside {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  box-shadow: var(--app-shadow);
  transition: background-color 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.kb-nav {
  overflow: hidden;
  display: grid;
  grid-template-rows: auto 1fr;
}

.upload-box {
  padding: 12px;
  border-bottom: 1px solid var(--app-border-soft);
}

.upload-box :deep(.el-upload-dragger) {
  padding: 18px 10px;
}

.doc-list {
  overflow: auto;
  padding: 8px;
}

.doc-item {
  display: block;
  width: 100%;
  padding: 10px;
  border: 0;
  border-radius: var(--app-radius);
  color: var(--app-text-soft);
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.15s;
}

.doc-item:hover,
.doc-item.active {
  background: var(--app-primary-softer);
}

.doc-title {
  display: block;
  overflow: hidden;
  font-weight: 600;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--app-text-heading);
}

.doc-meta {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-top: 6px;
  color: var(--app-muted);
  font-size: 12px;
}

.reader {
  overflow: auto;
  padding: 32px 44px;
}

.reader-header {
  display: flex;
  gap: 16px;
  align-items: flex-start;
  justify-content: space-between;
  padding-bottom: 18px;
  border-bottom: 1px solid var(--app-border);
}

.reader-header h1 {
  margin: 0;
  color: var(--app-text-heading);
  font-size: 30px;
  line-height: 1.25;
}

.reader-meta,
.reader-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
}

.reader-meta {
  margin-top: 10px;
  color: var(--app-muted);
  font-size: 13px;
}

.reader-alert {
  margin-top: 18px;
}

.article-body {
  max-width: 860px;
  padding: 22px 0 48px;
  color: var(--app-text);
  line-height: 1.82;
}

.article-body :deep(h1),
.article-body :deep(h2),
.article-body :deep(h3),
.article-body :deep(h4) {
  margin: 28px 0 12px;
  color: var(--app-text-heading);
  line-height: 1.35;
}

.article-body :deep(h1) {
  font-size: 28px;
}

.article-body :deep(h2) {
  padding-bottom: 8px;
  border-bottom: 1px solid var(--app-border);
  font-size: 23px;
}

.article-body :deep(h3) {
  font-size: 19px;
}

.article-body :deep(p),
.article-body :deep(ul),
.article-body :deep(ol) {
  margin: 10px 0;
}

.article-body :deep(ul),
.article-body :deep(ol) {
  padding-left: 24px;
}

.article-body :deep(pre) {
  overflow-x: auto;
  padding: 14px 16px;
  border-radius: var(--app-radius);
  color: var(--app-terminal-text);
  background: var(--app-terminal-bg);
  font-size: 13px;
  line-height: 1.65;
}

.article-body :deep(code) {
  border-radius: var(--app-radius-sm);
  background: var(--app-code-bg);
  color: var(--app-code-text);
  padding: 2px 5px;
  font-family: var(--app-font-mono);
  font-size: 0.92em;
}

.article-body :deep(pre code) {
  padding: 0;
  color: inherit;
  background: transparent;
}

.article-body :deep(table) {
  width: 100%;
  margin: 14px 0;
  border-collapse: collapse;
}

.article-body :deep(th),
.article-body :deep(td) {
  border: 1px solid var(--app-border-strong);
  padding: 8px 10px;
  text-align: left;
}

.article-body :deep(th) {
  background: var(--app-surface-soft);
}

.empty-reader {
  display: grid;
  height: 100%;
  min-height: 420px;
  place-items: center;
}

.kb-aside {
  overflow: auto;
  padding: 14px;
}

.aside-section + .aside-section {
  margin-top: 22px;
}

.aside-title {
  margin-bottom: 10px;
  color: var(--app-text-heading);
  font-size: 14px;
  font-weight: 700;
}

.search-results {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.search-result {
  width: 100%;
  padding: 9px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s;
}

.search-result:hover {
  border-color: var(--app-primary-border);
  background: var(--app-primary-soft);
}

.search-result strong,
.search-result span {
  display: block;
}

.search-result strong {
  overflow: hidden;
  color: var(--app-text-heading);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.search-result span {
  display: -webkit-box;
  overflow: hidden;
  margin-top: 5px;
  color: var(--app-muted);
  font-size: 12px;
  line-height: 1.45;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
}

.toc {
  display: grid;
  gap: 3px;
}

.toc button {
  overflow: hidden;
  width: 100%;
  padding: 5px 0;
  border: 0;
  color: var(--app-text-soft);
  background: transparent;
  text-align: left;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: pointer;
  transition: color 0.15s;
}

.toc button:hover {
  color: var(--app-primary);
}

.toc-level-2 {
  padding-left: 10px !important;
}

.toc-level-3,
.toc-level-4 {
  padding-left: 20px !important;
  font-size: 12px;
}

.aside-empty {
  margin: 0;
  color: var(--app-muted-soft);
  font-size: 13px;
}

.agent-section code,
.agent-section pre {
  display: block;
  overflow: auto;
  border-radius: var(--app-radius);
  background: var(--app-code-bg);
  color: var(--app-code-text);
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.agent-section code {
  padding: 7px 9px;
}

.agent-section pre {
  margin: 8px 0 0;
  padding: 9px;
  white-space: pre-wrap;
}

.optimized-output {
  min-height: 260px;
  max-height: 60vh;
  overflow: auto;
  margin: 12px 0 0;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  background: var(--app-surface-soft);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--app-font-mono);
  font-size: 13px;
  line-height: 1.65;
  transition: background-color 0.3s, border-color 0.3s;
}

.markdown-editor :deep(.el-textarea__inner) {
  font-family: var(--app-font-mono);
  font-size: 13px;
  line-height: 1.65;
}

.optimize-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 12px 0;
}

@media (max-width: 1180px) {
  .knowledge-shell {
    grid-template-columns: 240px minmax(0, 1fr);
  }

  .kb-aside {
    grid-column: 1 / -1;
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 16px;
  }

  .aside-section + .aside-section {
    margin-top: 0;
  }
}

@media (max-width: 780px) {
  .toolbar-actions,
  .reader-header,
  .reader-actions {
    align-items: stretch;
    flex-direction: column;
  }

  .toolbar-actions .el-input {
    width: 100%;
  }

  .knowledge-shell {
    grid-template-columns: 1fr;
  }

  .reader {
    padding: 20px;
  }

  .kb-aside {
    display: block;
  }

  .aside-section + .aside-section {
    margin-top: 22px;
  }
}
</style>
