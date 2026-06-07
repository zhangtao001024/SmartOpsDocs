<template>
  <el-container class="layout">
    <el-aside width="232px" class="sidebar">
      <div class="brand">
        <div class="brand-mark">SD</div>
        <div>
          <div class="brand-name">SmartOpsDocs</div>
          <div class="brand-sub">Ops Knowledge</div>
        </div>
      </div>
      <div class="nav-scroll">
      <el-menu :default-active="$route.path" router>
        <div class="nav-section-label">工作台</div>
        <el-menu-item index="/"><el-icon><TrendCharts /></el-icon><span>概览</span></el-menu-item>
        <el-menu-item index="/servers"><el-icon><Management /></el-icon><span>服务器资产</span></el-menu-item>
        <el-menu-item index="/docker"><el-icon><Platform /></el-icon><span>Docker 管理</span></el-menu-item>
        <el-menu-item index="/k8s"><el-icon><Guide /></el-icon><span>Kubernetes</span></el-menu-item>
        <div class="nav-section-label">知识与 AI</div>
        <el-menu-item index="/documents"><el-icon><Reading /></el-icon><span>知识库文档</span></el-menu-item>
        <el-menu-item index="/chat"><el-icon><MessageBox /></el-icon><span>AI 助手</span></el-menu-item>
        <el-menu-item index="/settings"><el-icon><SetUp /></el-icon><span>模型设置</span></el-menu-item>
      </el-menu>
      </div>
      <div class="sidebar-status" :class="'status-' + runtimeStatus">
        <span class="status-pulse"></span>
        <div>
          <strong>{{ runtimeLabel }}</strong>
          <small>{{ runtimeDetail }}</small>
        </div>
      </div>
      <div class="sidebar-actions">
        <el-button text :icon="theme === 'dark' ? 'Sunny' : 'Moon'" @click="toggleTheme">
          {{ theme === 'dark' ? '亮色' : '暗色' }}
        </el-button>
        <el-button text icon="SwitchButton" @click="logout">退出</el-button>
      </div>
    </el-aside>
    <el-container class="content-shell">
      <el-main id="main-content" class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import useTheme from '../composables/useTheme'
import client from '../api/client'

const router = useRouter()
const { theme, toggleTheme } = useTheme()
const runtimeStatus = ref('checking')
const runtimeCounts = ref(null)
const runtimeIssues = ref([])
let statusTimer = null

async function loadRuntimeStatus() {
  try {
    const { data } = await client.get('/api/system/status')
    runtimeStatus.value = data.status === 'ok' ? 'ok' : 'degraded'
    runtimeCounts.value = data.counts || null
    runtimeIssues.value = data.issues || []
  } catch {
    runtimeStatus.value = 'offline'
    runtimeCounts.value = null
    runtimeIssues.value = []
  }
}

onMounted(() => {
  loadRuntimeStatus()
  statusTimer = window.setInterval(loadRuntimeStatus, 30000)
})

onBeforeUnmount(() => {
  if (statusTimer) window.clearInterval(statusTimer)
})

const runtimeLabel = computed(() => {
  if (runtimeStatus.value === 'ok') return '后端正常'
  if (runtimeStatus.value === 'degraded') return '后端降级'
  if (runtimeStatus.value === 'offline') return '后端离线'
  return '检查中'
})
const runtimeDetail = computed(() => {
  if (runtimeStatus.value === 'offline') return 'API :8000 无响应'
  if (runtimeStatus.value === 'degraded' && runtimeIssueText.value) return runtimeIssueText.value
  const counts = runtimeCounts.value
  if (!counts) return 'API :8000'
  return `${counts.servers ?? 0} 台资产 / ${counts.documents ?? 0} 篇文档`
})
const runtimeIssueText = computed(() => {
  const issue = runtimeIssues.value[0]
  if (!issue) return ''
  const name = issue.name ? `${issue.scope || 'runtime'}:${issue.name}` : issue.scope || 'runtime'
  return `${name} ${issue.error || '异常'}`
})
function logout() {
  localStorage.removeItem('smartopsdocs_token')
  router.push('/login')
}
</script>

<style scoped>
.layout {
  height: 100dvh;
  min-height: 100dvh;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.34), transparent 280px),
    transparent;
}

.sidebar {
  position: sticky;
  top: 0;
  z-index: 3;
  height: 100dvh;
  border-right: 1px solid var(--app-sidebar-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.74), transparent 34%),
    repeating-linear-gradient(0deg, rgba(16, 23, 19, 0.025) 0 1px, transparent 1px 30px),
    var(--app-sidebar-bg);
  transition: width 0.25s ease, background-color 0.3s;
  overflow: hidden;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto auto;
  box-shadow: 10px 0 30px rgba(24, 45, 35, 0.055);
}

:global(html.dark) .sidebar {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 28%),
    repeating-linear-gradient(0deg, rgba(220, 230, 221, 0.022) 0 1px, transparent 1px 30px),
    var(--app-sidebar-bg);
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  height: 64px;
  padding: 0 16px;
  border-bottom: 1px solid var(--app-border-soft);
  white-space: nowrap;
}

.brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  border-radius: var(--app-radius);
  color: #fff;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.18), transparent 38%),
    linear-gradient(160deg, var(--app-primary), var(--app-primary-strong) 62%, var(--app-accent)),
    var(--app-primary);
  font-family: var(--app-font-display);
  font-size: 13px;
  font-weight: 860;
  box-shadow: 0 12px 26px rgba(12, 118, 111, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.24);
  place-items: center;
  flex-shrink: 0;
}

.brand-name {
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 17px;
  font-weight: 840;
  line-height: 1.2;
}

.brand-sub {
  margin-top: 2px;
  color: var(--app-muted);
  font-size: 12px;
}

.nav-scroll {
  display: flex;
  min-width: 0;
  min-height: 0;
  overflow: auto;
  padding: 10px 0;
}

:deep(.el-menu) {
  display: grid;
  height: 100%;
  align-content: space-evenly;
  border-right: 0;
  width: 100%;
  min-width: 0;
  padding: 0;
}

.nav-section-label {
  margin: 0 20px;
  color: var(--app-muted-soft);
  font-size: 11px;
  font-weight: 760;
  letter-spacing: 0;
  text-transform: uppercase;
}

:deep(.el-menu-item) {
  width: 100%;
  height: 42px;
  margin-bottom: 0;
  padding: 0 18px !important;
  border-radius: 0;
  color: var(--app-text-soft);
  line-height: 42px;
  font-weight: 720;
  transition: background-color 0.16s ease, color 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease;
}

:deep(.el-menu-item .el-icon) {
  width: 28px;
  height: 28px;
  margin-right: 12px;
  border-radius: var(--app-radius-sm);
  color: var(--app-primary);
  background: color-mix(in srgb, var(--app-primary-softer) 72%, transparent);
  transition: color 0.16s ease, background-color 0.16s ease, transform 0.16s ease;
}

:deep(.el-menu-item:hover) {
  background: var(--app-sidebar-item-hover);
  transform: none;
  box-shadow: inset 3px 0 0 color-mix(in srgb, var(--app-primary) 36%, transparent);
}

:deep(.el-menu-item:hover .el-icon) {
  transform: scale(1.04);
  background: var(--app-primary-soft);
}

:deep(.el-menu-item.is-active) {
  color: var(--app-primary);
  background:
    linear-gradient(90deg, var(--app-primary-soft), var(--app-primary-softer) 74%, color-mix(in srgb, var(--app-accent-soft) 46%, transparent));
  box-shadow: inset 4px 0 0 var(--app-primary), inset 0 -1px 0 var(--app-border-soft), inset 0 1px 0 rgba(255, 255, 255, 0.58);
}

:deep(.el-menu-item.is-active .el-icon) {
  color: #fff;
  background:
    linear-gradient(150deg, var(--app-primary), var(--app-primary-strong) 68%, var(--app-accent));
  box-shadow: 0 8px 16px color-mix(in srgb, var(--app-primary) 18%, transparent);
}

.sidebar-status {
  display: flex;
  gap: 12px;
  align-items: center;
  margin: 8px 12px;
  padding: 8px 12px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.45), transparent),
    var(--app-surface-soft);
  box-shadow: var(--app-shadow-sm);
}

.sidebar-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  padding: 0 12px 12px;
}

.sidebar-actions :deep(.el-button) {
  min-height: 34px;
  justify-content: center;
  margin-left: 0 !important;
  border: 1px solid var(--app-border-soft);
  background: color-mix(in srgb, var(--app-surface-raised) 62%, transparent);
}

.sidebar-status strong,
.sidebar-status small {
  display: block;
}

.sidebar-status strong {
  color: var(--app-text-heading);
  font-size: 13px;
  line-height: 1.25;
}

.sidebar-status small {
  margin-top: 2px;
  color: var(--app-muted);
  font-family: var(--app-font-mono);
  font-size: 11px;
}

.status-pulse {
  position: relative;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--app-success);
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--app-success) 14%, transparent);
}

.sidebar-status.status-degraded .status-pulse {
  background: var(--app-warning);
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--app-warning) 16%, transparent);
}

.sidebar-status.status-offline .status-pulse {
  background: var(--app-danger);
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--app-danger) 14%, transparent);
}

.sidebar-status.status-checking .status-pulse {
  background: var(--app-muted-soft);
  box-shadow: 0 0 0 5px color-mix(in srgb, var(--app-muted-soft) 14%, transparent);
}

.content-shell {
  min-width: 0;
  height: 100dvh;
  min-height: 0;
}

.main-content {
  width: 100%;
  height: 100dvh;
  margin: 0 auto;
  padding: 12px;
  min-height: 0;
  overflow: hidden;
}
</style>
