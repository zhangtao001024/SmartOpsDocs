<template>
  <div class="knowledge-page">
    <section class="knowledge-hero console-hero">
      <div class="page-heading">
        <p class="page-kicker">Knowledge reader</p>
        <h2 class="page-title">知识库</h2>
        <p class="page-subtitle">把文档、网页和解析片段整理成可阅读、可检索、可引用的运维知识。</p>
        <div class="hero-insights console-status-strip" aria-label="知识库状态">
          <span><strong>{{ documents.length }}</strong> 篇文档</span>
          <span><strong>{{ project || 'default' }}</strong> 当前项目</span>
          <span><strong>{{ detail?.chunks?.length || 0 }}</strong> 当前片段</span>
        </div>
      </div>
      <div class="toolbar-actions">
        <el-input v-model="project" placeholder="项目" clearable />
        <el-input v-model="documentQuery" placeholder="搜索文档标题 / 状态" clearable />
        <el-select v-model="statusFilter" placeholder="状态" clearable class="status-filter">
          <el-option label="完成" value="completed" />
          <el-option label="解析中" value="parsing" />
          <el-option label="待解析" value="uploaded" />
          <el-option label="草稿" value="draft" />
          <el-option label="失败" value="failed" />
        </el-select>
        <el-button icon="Link" type="primary" @click="openPullWeb">拉取网页</el-button>
        <el-button icon="Refresh" @click="load">刷新</el-button>
      </div>
    </section>

    <div class="knowledge-shell" :class="{ 'toc-collapsed': tocPanelCollapsed }">
      <aside class="kb-nav" aria-label="文档库">
        <div class="nav-head">
          <div>
            <p>Library</p>
            <h3>文档库</h3>
          </div>
          <el-tag size="small" effect="plain">{{ documents.length }} 篇</el-tag>
        </div>

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
          <div class="upload-content">
            <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
            <div>
              <strong>上传文档</strong>
              <span>DOCX / Markdown / PDF / TXT</span>
            </div>
          </div>
        </el-upload>

        <div class="doc-list" v-loading="loading">
          <div v-if="!loading && documents.length === 0" class="doc-empty">
            当前项目还没有文档，可以上传文件或拉取网页。
          </div>
          <button
            v-for="doc in documents"
            :key="doc.id"
            :class="['doc-item', { active: selectedId === doc.id }]"
            type="button"
            @click="openDocument(doc)"
          >
            <span :class="['doc-source-mark', 'source-' + sourceKind(doc)]">{{ sourceShortLabel(doc) }}</span>
            <span class="doc-copy">
              <span class="doc-title" :title="sourceHint(doc) || doc.title">{{ displayTitle(doc) }}</span>
              <span class="doc-subtitle">{{ documentSubtitle(doc) }}</span>
            </span>
            <span class="doc-meta">
              <el-tag :type="statusType(doc.status)" size="small" effect="plain">{{ statusLabel(doc.status) }}</el-tag>
              <span>{{ doc.chunk_count || 0 }} 片段</span>
            </span>
          </button>
        </div>
      </aside>

      <main class="reader" ref="articleRef">
        <template v-if="detail">
          <header class="reader-header">
            <div class="reader-title-block">
              <h1>{{ displayTitle(detail) }}</h1>
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
          <div class="empty-copy">
            <h3>选择一篇文档开始阅读</h3>
            <p>左侧会显示当前项目下的文档。上传文件或拉取网页后，解析完成的内容会在这里以阅读器模式展示。</p>
            <el-button icon="Link" type="primary" @click="openPullWeb">拉取网页</el-button>
          </div>
        </div>
      </main>

      <aside class="kb-aside">
        <button class="aside-collapse" type="button" @click="tocPanelCollapsed = !tocPanelCollapsed">
          <el-icon><component :is="tocPanelCollapsed ? 'ArrowLeft' : 'ArrowRight'" /></el-icon>
          <span>{{ tocPanelCollapsed ? '展开' : '收起' }}</span>
        </button>

        <section class="aside-section document-tools">
          <div class="aside-heading">
            <span>Tools</span>
            <strong>文档操作</strong>
          </div>
          <div class="reader-actions">
            <el-button icon="EditPen" :disabled="!detail" @click="openEditor(detail)">编辑</el-button>
            <el-button icon="MagicStick" type="primary" :disabled="!detail" @click="openOptimize(detail)">优化</el-button>
            <el-button icon="Clock" :disabled="!detail" @click="handleReaderCommand('tasks')">解析任务</el-button>
            <el-button icon="Files" :disabled="!detail" @click="handleReaderCommand('revisions')">文档版本</el-button>
            <el-button icon="Refresh" :loading="reprocessing" :disabled="!detail" @click="handleReaderCommand('reprocess')">重新解析</el-button>
            <el-button icon="Delete" type="danger" text :disabled="!detail" @click="handleReaderCommand('delete')">删除文档</el-button>
          </div>
        </section>

        <section class="aside-section search-section">
          <div class="aside-heading">
            <span>Search</span>
            <strong>知识检索</strong>
          </div>
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
            <p v-if="searchText.trim() && !searching && searchResults.length === 0" class="aside-empty search-empty">
              没有匹配的知识片段
            </p>
            <button
              v-for="item in searchResults"
              :key="item.chunk_id"
              type="button"
              class="search-result"
              @click="openSearchResult(item)"
            >
              <strong>{{ displayTitle(item) }}</strong>
              <span>{{ item.preview }}</span>
            </button>
          </div>
        </section>

        <section class="aside-section toc-section">
          <div class="aside-heading">
            <span>Outline</span>
            <strong>目录</strong>
          </div>
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

      </aside>
    </div>

    <el-dialog v-model="optimizeVisible" title="AI 优化文档" width="980px">
      <el-alert
        title="建议把优化结果作为新草稿审核，不要直接覆盖原始文档。"
        type="info"
        show-icon
        :closable="false"
        class="optimize-alert"
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

    <el-dialog v-model="pullVisible" title="拉取网页到知识库" width="780px">
      <el-form label-width="90px">
        <el-form-item label="URL">
          <el-input v-model="pullForm.url" placeholder="https://example.com/article" />
        </el-form-item>
        <el-form-item label="项目">
          <el-input v-model="pullForm.project" />
        </el-form-item>
        <el-form-item label="要求">
          <el-input
            v-model="pullForm.instruction"
            type="textarea"
            :rows="3"
            placeholder="可选：例如只提取架构、组件职责和关键概念"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pullVisible = false">取消</el-button>
        <el-button type="primary" icon="Download" :loading="pulling" :disabled="!pullForm.url.trim()" @click="pullWeb">开始拉取</el-button>
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
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import client, { getApiErrorMessage } from '../api/client'

marked.setOptions({ breaks: true })

const route = useRoute()
const project = ref('default')
const documentQuery = ref('')
const statusFilter = ref('')
const documents = ref([])
const loading = ref(false)
const detail = ref(null)
const selectedId = ref(null)
const articleRef = ref(null)
const tocPanelCollapsed = ref(false)
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
const pullVisible = ref(false)
const pulling = ref(false)
const pullForm = ref({
  url: 'https://jimmysong.io/zh/book/kubernetes-handbook/architecture/',
  project: 'default',
  instruction: '整理 Kubernetes 架构知识，保留组件职责、控制面、节点、网络和调度相关概念。',
})
const tasksVisible = ref(false)
const tasksLoading = ref(false)
const tasks = ref([])
const revisionsVisible = ref(false)
const revisionsLoading = ref(false)
const revisions = ref([])
const headers = computed(() => ({ Authorization: `Bearer ${localStorage.getItem('smartopsdocs_token') || ''}` }))
let listTimer = null

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
  return DOMPurify.sanitize(marked.parse(text))
}

function cleanSourceText(value) {
  let text = String(value || '').trim()
  try {
    text = decodeURIComponent(text)
  } catch (_error) {
    // Keep the original value when it is not URL-encoded text.
  }
  return text.replace(/\\/g, '/').replace(/\s+/g, ' ').trim()
}

function titleSource(value) {
  if (value && typeof value === 'object') {
    return value.title || value.document_title || value.source_hint || value.source || ''
  }
  return value
}

function displayTitle(value) {
  const source = cleanSourceText(titleSource(value))
  if (!source) return '未命名文档'
  if (/^https?:\/\//i.test(source)) {
    try {
      const url = new URL(source)
      const lastPart = url.pathname.split('/').filter(Boolean).pop() || url.hostname
      const cleanPathTitle = cleanSourceText(lastPart)
        .replace(/\.(html?|md|txt|pdf)$/i, '')
        .replace(/[-_]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
      return cleanPathTitle || url.hostname.replace(/^www\./i, '')
    } catch (_error) {
      return source
    }
  }
  const basename = source.split('/').filter(Boolean).pop() || source
  return basename
    .replace(/\.(docx?|pdf|md|txt)$/i, '')
    .replace(/[-_]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim() || source
}

function sourceKind(doc) {
  const kind = String(doc?.source_kind || '').trim()
  if (kind) return kind
  const title = cleanSourceText(doc?.title || '')
  if (/^https?:\/\//i.test(title)) return 'web'
  const suffix = title.toLowerCase().split('.').pop()
  if (suffix === 'pdf') return 'pdf'
  if (['doc', 'docx'].includes(suffix)) return 'word'
  if (suffix === 'md') return 'markdown'
  if (suffix === 'txt') return 'text'
  if (doc?.status === 'draft') return 'draft'
  return 'document'
}

function sourceLabel(doc) {
  const labels = {
    web: '网页',
    word: 'Word',
    pdf: 'PDF',
    markdown: 'Markdown',
    text: '文本',
    draft: '草稿',
    document: '文档',
  }
  return labels[sourceKind(doc)] || '文档'
}

function sourceShortLabel(doc) {
  const labels = {
    web: 'WEB',
    word: 'DOC',
    pdf: 'PDF',
    markdown: 'MD',
    text: 'TXT',
    draft: 'DR',
    document: 'DOC',
  }
  return labels[sourceKind(doc)] || 'DOC'
}

function formatDate(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })
}

function documentSubtitle(doc) {
  return [sourceLabel(doc), formatDate(doc.updated_at || doc.created_at), doc.project]
    .filter(Boolean)
    .join(' · ')
}

function sourceHint(doc) {
  const titleRaw = cleanSourceText(titleSource(doc))
  const hintRaw = cleanSourceText(doc?.source_hint || '')
  if (hintRaw && hintRaw !== titleRaw) return hintRaw
  if (titleRaw && titleRaw !== displayTitle(doc)) return titleRaw
  return ''
}

function statusType(status) {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'parsing') return 'warning'
  if (status === 'draft') return 'info'
  return 'info'
}

function statusLabel(status) {
  if (status === 'completed') return '完成'
  if (status === 'parsing') return '解析中'
  if (status === 'uploaded') return '待解析'
  if (status === 'failed') return '失败'
  if (status === 'draft') return '草稿'
  return status || '未知'
}

function statusText(status) {
  if (status === 'completed') return '解析完成'
  if (status === 'parsing') return '文档正在解析'
  if (status === 'uploaded') return '文档已上传，等待解析'
  if (status === 'failed') return '解析失败'
  if (status === 'draft') return 'Agent 生成的知识草稿，建议审核后再作为正式知识使用'
  return status || '未知状态'
}

async function load() {
  loading.value = true
  try {
    documents.value = (await client.get('/api/knowledge/tree', {
      params: {
        project: project.value || undefined,
        q: documentQuery.value.trim() || undefined,
        status: statusFilter.value || undefined,
      }
    })).data
    const routeDocId = Number(route.query.doc || 0)
    if (routeDocId && selectedId.value !== routeDocId) {
      await openDocumentById(routeDocId)
    } else if (!detail.value && documents.value.length) {
      await openDocument(documents.value[0])
    } else if (selectedId.value && !documents.value.some((doc) => doc.id === selectedId.value)) {
      detail.value = null
      selectedId.value = null
    }
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取文档列表失败'))
  } finally {
    loading.value = false
  }
}

function queueLoad() {
  if (listTimer) window.clearTimeout(listTimer)
  listTimer = window.setTimeout(load, 260)
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
    ElMessage.error(getApiErrorMessage(error, '检索失败'))
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
    if (target) {
      const top = target.getBoundingClientRect().top - root.getBoundingClientRect().top + root.scrollTop - 12
      root.scrollTo({ top, behavior: 'smooth' })
    }
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

function openPullWeb() {
  pullForm.value.project = project.value || 'default'
  pullVisible.value = true
}

async function pullWeb() {
  const payload = {
    url: pullForm.value.url.trim(),
    project: pullForm.value.project || project.value || 'default',
    instruction: pullForm.value.instruction || '',
  }
  if (!payload.url) return
  pulling.value = true
  try {
    const { data } = await client.post('/api/knowledge/pull-url', payload)
    pullVisible.value = false
    selectedId.value = data.id
    detail.value = data
    ElMessage.success('已创建网页拉取任务')
    await load()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '网页拉取失败'))
  } finally {
    pulling.value = false
  }
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
    ElMessage.error(getApiErrorMessage(error, '保存失败'))
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
    ElMessage.error(getApiErrorMessage(error, '重新解析失败'))
  } finally {
    reprocessing.value = false
  }
}

function handleReaderCommand(command) {
  if (!detail.value) return
  if (command === 'tasks') openTasks(detail.value)
  if (command === 'revisions') openRevisions(detail.value)
  if (command === 'reprocess') reprocess(detail.value)
  if (command === 'delete') confirmRemoveDoc(detail.value)
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
    ElMessage.error(getApiErrorMessage(error, '恢复失败'))
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
    ElMessage.error(getApiErrorMessage(error, '优化失败'))
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
    ElMessage.error(getApiErrorMessage(error, '删除失败'))
  }
}

async function confirmRemoveDoc(row) {
  try {
    await ElMessageBox.confirm(
      `确定删除文档「${displayTitle(row)}」？删除后会移除文档内容和检索片段。`,
      '确认删除文档',
      {
        confirmButtonText: '删除文档',
        cancelButtonText: '取消',
        type: 'warning',
        closeOnClickModal: false,
        distinguishCancelAndClose: true,
      }
    )
    await removeDoc(row)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '删除失败'))
    }
  }
}

watch(() => route.query.doc, () => {
  const id = Number(route.query.doc || 0)
  if (id) openDocumentById(id)
})

onMounted(load)

watch([project, documentQuery, statusFilter], queueLoad)

onBeforeUnmount(() => {
  if (listTimer) window.clearTimeout(listTimer)
})
</script>

<style scoped>
.knowledge-page {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 16px;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.toolbar-actions {
  display: grid;
  grid-template-columns: 140px minmax(220px, 1fr) 126px auto auto;
  gap: 8px;
  align-items: center;
  justify-content: end;
  min-width: 0;
  max-width: 760px;
  flex-shrink: 0;
}

.toolbar-actions .el-input {
  width: 100%;
}

.toolbar-actions .status-filter {
  width: 128px;
}

.knowledge-shell {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr) 240px;
  align-items: stretch;
  gap: 12px;
  min-height: 0;
  height: 100%;
  transition: grid-template-columns 0.24s ease;
}

.knowledge-shell.toc-collapsed {
  grid-template-columns: 260px minmax(0, 1fr) 48px;
}

.kb-nav,
.reader,
.kb-aside {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.68), rgba(255, 255, 255, 0)),
    linear-gradient(90deg, rgba(12, 118, 111, 0.025), transparent 54%, rgba(168, 85, 30, 0.018)),
    var(--app-surface);
  box-shadow: var(--app-shadow);
  transition: background-color 0.3s, border-color 0.3s, box-shadow 0.3s;
}

:global(html.dark) .kb-nav,
:global(html.dark) .reader,
:global(html.dark) .kb-aside {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0)),
    linear-gradient(90deg, rgba(53, 199, 183, 0.024), transparent 54%, rgba(216, 146, 69, 0.018)),
    var(--app-surface);
}

.kb-nav {
  display: grid;
  grid-template-rows: auto auto minmax(0, 1fr);
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

.nav-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px;
  border-bottom: 1px solid var(--app-border-soft);
}

.nav-head p,
.aside-heading span {
  margin: 0 0 8px;
  color: var(--app-muted);
  font-size: 11px;
  font-weight: 760;
  letter-spacing: 0;
  text-transform: uppercase;
}

.nav-head h3,
.aside-heading strong {
  display: block;
  margin: 0;
  color: var(--app-text-heading);
  font-size: 15px;
  font-weight: 760;
}

.upload-box {
  padding: 10px 12px;
  border-bottom: 1px solid var(--app-border-soft);
}

.upload-box :deep(.el-upload-dragger) {
  padding: 12px;
  border-color: var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-surface-soft);
  transition: border-color 0.18s ease, background-color 0.18s ease, transform 0.18s ease;
}

.upload-box :deep(.el-upload-dragger:hover) {
  border-color: var(--app-primary-border);
  background: var(--app-primary-softer);
  transform: translateY(-1px);
}

.upload-content {
  display: flex;
  align-items: center;
  gap: 16px;
  text-align: left;
}

.upload-content .el-icon {
  margin: 0;
  color: var(--app-primary);
  font-size: 24px;
}

.upload-content strong,
.upload-content span {
  display: block;
}

.upload-content strong {
  color: var(--app-text-heading);
  font-size: 13px;
  font-weight: 760;
}

.upload-content span {
  margin-top: 2px;
  color: var(--app-muted);
  font-size: 12px;
}

.doc-list {
  overflow: auto;
  padding: 10px;
}

.doc-empty {
  padding: 16px;
  border: 1px dashed var(--app-border);
  border-radius: var(--app-radius-md);
  color: var(--app-muted);
  background: var(--app-surface-soft);
  font-size: 13px;
  line-height: 1.65;
}

.doc-item {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  grid-template-areas:
    "mark copy"
    "mark meta";
  column-gap: 12px;
  row-gap: 8px;
  align-items: start;
  position: relative;
  width: 100%;
  padding: 10px;
  border: 1px solid transparent;
  border-radius: var(--app-radius-md);
  color: var(--app-text-soft);
  background: transparent;
  text-align: left;
  cursor: pointer;
  transition: background-color 0.16s ease, border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
}

.doc-item + .doc-item {
  margin-top: 8px;
}

.doc-item:hover {
  border-color: var(--app-border-soft);
  background: var(--app-surface-hover);
  transform: translateX(2px);
}

.doc-item.active {
  color: var(--app-primary);
  background:
    linear-gradient(90deg, var(--app-primary-soft), var(--app-primary-softer) 74%, color-mix(in srgb, var(--app-accent-soft) 46%, transparent));
  box-shadow: inset 3px 0 0 var(--app-primary), var(--app-shadow-xs);
}

.doc-source-mark {
  grid-area: mark;
  display: inline-grid;
  place-items: center;
  width: 34px;
  height: 30px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius);
  color: var(--app-muted);
  background: color-mix(in srgb, var(--app-surface-raised) 72%, transparent);
  box-shadow: var(--app-shadow-xs);
  font-family: var(--app-font-mono);
  font-size: 10px;
  font-weight: 760;
  letter-spacing: 0;
  line-height: 1;
}

.doc-source-mark.source-web {
  color: var(--app-primary);
  background: var(--app-primary-softer);
  border-color: var(--app-primary-border);
}

.doc-source-mark.source-pdf,
.doc-source-mark.source-word {
  color: var(--app-accent);
  background: var(--app-accent-soft);
  border-color: color-mix(in srgb, var(--app-accent) 35%, var(--app-border));
}

.doc-source-mark.source-draft {
  color: var(--app-warning);
  background: var(--app-warning-soft);
  border-color: color-mix(in srgb, var(--app-warning) 35%, var(--app-border));
}

.doc-copy {
  grid-area: copy;
  min-width: 0;
}

.doc-title {
  overflow: hidden;
  display: -webkit-box;
  color: var(--app-text-heading);
  font-size: 14px;
  font-weight: 760;
  line-height: 1.34;
  overflow-wrap: anywhere;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.doc-subtitle {
  display: block;
  overflow: hidden;
  margin-top: 8px;
  color: var(--app-muted);
  font-size: 11px;
  font-weight: 620;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.doc-meta {
  grid-area: meta;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  color: var(--app-muted);
  font-size: 12px;
}

.reader {
  min-width: 0;
  min-height: 0;
  height: 100%;
  overflow: auto;
  padding: 0;
}

.reader-header {
  padding: 18px 32px 14px;
  border-bottom: 1px solid var(--app-border-soft);
  background:
    linear-gradient(90deg, rgba(12, 118, 111, 0.06), transparent 48%, rgba(168, 85, 30, 0.025)),
    var(--app-surface);
}

.reader-header h1 {
  max-width: 42ch;
  margin: 0;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 30px;
  font-weight: 860;
  line-height: 1.14;
  overflow-wrap: anywhere;
  text-wrap: balance;
}

.reader-title-block {
  min-width: 0;
}

.reader-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.reader-alert {
  margin: 14px 32px 0;
}

.article-body {
  width: 100%;
  margin: 0 auto;
  padding: 26px 32px 64px;
  color: var(--app-text);
  font-size: 16px;
  line-height: 1.9;
  overflow-wrap: anywhere;
  text-wrap: pretty;
}

.article-body :deep(h1),
.article-body :deep(h2),
.article-body :deep(h3),
.article-body :deep(h4) {
  margin: 2.1em 0 0.7em;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-weight: 780;
  line-height: 1.25;
  scroll-margin-top: 92px;
  text-wrap: balance;
}

.article-body :deep(h1) {
  font-size: 2rem;
}

.article-body :deep(h2) {
  padding-bottom: 0.55em;
  border-bottom: 1px solid var(--app-border-soft);
  font-size: 1.55rem;
}

.article-body :deep(h3) {
  font-size: 1.22rem;
}

.article-body :deep(h4) {
  color: var(--app-text-soft);
  font-size: 1.04rem;
}

.article-body :deep(p),
.article-body :deep(ul),
.article-body :deep(ol),
.article-body :deep(blockquote) {
  margin: 0.9em 0;
}

.article-body :deep(p) {
  max-width: 72ch;
}

.article-body :deep(ul),
.article-body :deep(ol) {
  max-width: 74ch;
  padding-left: 1.35em;
}

.article-body :deep(li) {
  margin: 0.38em 0;
  padding-left: 0.15em;
}

.article-body :deep(a) {
  color: var(--app-primary);
  font-weight: 650;
  text-decoration: underline;
  text-decoration-color: var(--app-primary-border);
  text-underline-offset: 3px;
}

.article-body :deep(blockquote) {
  max-width: 74ch;
  padding: 0.8em 1em;
  border-left: 3px solid var(--app-primary);
  border-radius: 0 var(--app-radius-md) var(--app-radius-md) 0;
  color: var(--app-text-soft);
  background: var(--app-primary-softer);
}

.article-body :deep(hr) {
  height: 1px;
  margin: 2.3em 0;
  border: 0;
  background: var(--app-border-soft);
}

.article-body :deep(img) {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 1.4em auto;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  box-shadow: var(--app-shadow);
}

.article-body :deep(pre) {
  overflow-x: auto;
  margin: 1.25em 0;
  padding: 16px 24px;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: var(--app-radius-lg);
  color: var(--app-terminal-text);
  background:
    linear-gradient(rgba(255, 255, 255, 0.035) 1px, transparent 1px),
    var(--app-terminal-bg);
  background-size: 100% 26px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
  font-size: 13px;
  line-height: 1.7;
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
  margin: 1.4em 0;
  border-collapse: collapse;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  display: block;
  overflow-x: auto;
  font-size: 14px;
  line-height: 1.55;
}

@media (max-width: 1500px) {
  .toolbar-actions {
    grid-template-columns: 112px minmax(180px, 1fr) 108px auto auto;
    max-width: 640px;
  }

  .knowledge-shell {
    grid-template-columns: 240px minmax(0, 1fr) 220px;
    gap: 10px;
  }

  .knowledge-shell.toc-collapsed {
    grid-template-columns: 240px minmax(0, 1fr) 48px;
  }

  .reader-header {
    padding-inline: 24px;
  }

  .article-body {
    padding-inline: 24px;
  }
}

.article-body :deep(th),
.article-body :deep(td) {
  border: 1px solid var(--app-border-soft);
  padding: 10px 12px;
  text-align: left;
  vertical-align: top;
}

.article-body :deep(th) {
  background: var(--app-surface-soft);
  color: var(--app-text-heading);
  font-weight: 760;
}

.article-body :deep(tr:nth-child(even) td) {
  background: color-mix(in srgb, var(--app-surface-soft) 58%, transparent);
}

.empty-reader {
  display: grid;
  height: 100%;
  min-height: 420px;
  place-items: center;
  padding: 32px;
}

.empty-copy {
  max-width: 420px;
  text-align: center;
}

.empty-copy h3 {
  margin: 0;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 24px;
}

.empty-copy p {
  margin: 16px 0 24px;
  color: var(--app-muted);
  line-height: 1.75;
}

.kb-aside {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: auto;
  padding: 10px;
}

.aside-collapse {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  min-height: 40px;
  margin-bottom: 12px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  color: var(--app-text-soft);
  background: var(--app-surface-soft);
  font: inherit;
  font-size: 12px;
  font-weight: 760;
  transition: color 0.18s ease, border-color 0.18s ease, background-color 0.18s ease, transform 0.18s ease;
}

.aside-collapse:hover {
  border-color: var(--app-primary-border);
  color: var(--app-primary);
  background: var(--app-primary-softer);
  transform: translateY(-1px);
}

.knowledge-shell.toc-collapsed .kb-aside {
  overflow: hidden;
  padding: 8px;
}

.knowledge-shell.toc-collapsed .aside-collapse {
  min-height: 40px;
  margin-bottom: 0;
}

.knowledge-shell.toc-collapsed .aside-collapse span,
.knowledge-shell.toc-collapsed .aside-section {
  display: none;
}

.aside-section {
  padding: 10px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background: color-mix(in srgb, var(--app-surface-raised) 66%, transparent);
}

.aside-section + .aside-section {
  margin-top: 12px;
}

.aside-section:last-child {
  border-bottom: 1px solid var(--app-border-soft);
}

.aside-heading {
  margin-bottom: 12px;
}

.document-tools .reader-actions {
  display: grid;
  grid-template-columns: 1fr;
  gap: 8px;
}

.document-tools .reader-actions :deep(.el-button) {
  width: 100%;
  justify-content: flex-start;
  min-height: 34px;
  margin-left: 0;
  padding: 0 12px;
}

.document-tools .reader-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.document-tools .reader-actions :deep(.el-icon) {
  width: 16px;
  margin-right: 6px;
}

.search-results {
  display: grid;
  gap: 8px;
  margin-top: 12px;
  max-height: 280px;
  overflow: auto;
}

.search-result {
  width: 100%;
  padding: 12px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface-soft);
  text-align: left;
  cursor: pointer;
  transition: border-color 0.15s, background-color 0.15s, transform 0.15s;
}

.search-result:hover {
  border-color: var(--app-primary-border);
  background: var(--app-primary-soft);
  transform: translateY(-1px);
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
  gap: 2px;
  max-height: 340px;
  overflow: auto;
}

.toc button {
  overflow: hidden;
  width: 100%;
  padding: 6px 8px;
  border: 0;
  border-radius: var(--app-radius-sm);
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
  background: var(--app-primary-softer);
}

.toc button:active,
.search-result:active,
.doc-item:active {
  transform: translateY(1px);
}

.toc-level-2 {
  padding-left: 18px !important;
}

.toc-level-3,
.toc-level-4 {
  padding-left: 30px !important;
  font-size: 12px;
}

.aside-empty {
  margin: 0;
  color: var(--app-muted-soft);
  font-size: 13px;
}

:global(.danger-dropdown-item) {
  color: var(--app-danger) !important;
}

.optimized-output {
  min-height: 260px;
  max-height: 60vh;
  overflow: auto;
  margin: 16px 0 0;
  padding: 16px;
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
  gap: 8px;
  margin: 16px 0;
}

.optimize-alert {
  margin-bottom: 16px;
}
</style>
