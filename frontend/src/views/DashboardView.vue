<template>
  <el-container class="layout" :class="{ 'sidebar-collapsed': sidebarCollapsed }">
    <el-aside :width="sidebarCollapsed ? '0px' : '230px'" class="sidebar">
      <div class="brand">
        <div class="brand-mark">S</div>
        <div>
          <div class="brand-name">SmartOpsDocs</div>
          <div class="brand-sub">Ops Knowledge</div>
        </div>
      </div>
      <div class="nav-scroll">
      <el-menu :default-active="$route.path" router>
        <div class="nav-section-label">工作台</div>
        <el-menu-item index="/"><el-icon><DataAnalysis /></el-icon><span>概览</span></el-menu-item>
        <el-menu-item index="/servers"><el-icon><Monitor /></el-icon><span>服务器资产</span></el-menu-item>
        <el-menu-item index="/docker"><el-icon><Box /></el-icon><span>Docker 管理</span></el-menu-item>
        <el-menu-item index="/k8s"><el-icon><Connection /></el-icon><span>Kubernetes</span></el-menu-item>
        <div class="nav-section-label">知识与 AI</div>
        <el-menu-item index="/documents"><el-icon><Document /></el-icon><span>知识库文档</span></el-menu-item>
        <el-menu-item index="/chat"><el-icon><ChatDotRound /></el-icon><span>AI 助手</span></el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting /></el-icon><span>模型设置</span></el-menu-item>
      </el-menu>
      </div>
      <div class="sidebar-status" :class="'status-' + runtimeStatus">
        <span class="status-pulse"></span>
        <div>
          <strong>{{ runtimeLabel }}</strong>
          <small>{{ runtimeDetail }}</small>
        </div>
      </div>
    </el-aside>
    <el-container class="content-shell">
      <el-header>
        <div class="header-title">
          <el-button class="sidebar-toggle" text :icon="sidebarCollapsed ? 'Expand' : 'Fold'" @click="sidebarCollapsed = !sidebarCollapsed" />
          <div>
            <span>{{ currentTitle }}</span>
            <small>Local workspace</small>
          </div>
        </div>
        <div class="header-actions">
          <el-button text :icon="theme === 'dark' ? 'Sunny' : 'Moon'" @click="toggleTheme" :title="theme === 'dark' ? '切换亮色' : '切换暗色'" />
          <el-tag size="small" :type="runtimeTagType" effect="plain" :title="runtimeIssueText || runtimeDetail">{{ runtimeTagText }}</el-tag>
          <el-button text icon="SwitchButton" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main id="main-content" class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRoute } from 'vue-router'
import useTheme from '../composables/useTheme'
import client from '../api/client'

const router = useRouter()
const route = useRoute()
const { theme, toggleTheme } = useTheme()
const sidebarCollapsed = ref(window.innerWidth < 900)
const runtimeStatus = ref('checking')
const runtimeCounts = ref(null)
const runtimeIssues = ref([])
let statusTimer = null

function syncSidebar() {
  sidebarCollapsed.value = window.innerWidth < 900
}

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
  window.addEventListener('resize', syncSidebar)
  loadRuntimeStatus()
  statusTimer = window.setInterval(loadRuntimeStatus, 30000)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', syncSidebar)
  if (statusTimer) window.clearInterval(statusTimer)
})

const titleMap = {
  '/': '运维概览',
  '/servers': '服务器资产',
  '/docker': 'Docker 管理',
  '/k8s': 'Kubernetes',
  '/documents': '知识库',
  '/chat': 'AI 助手',
  '/settings': '模型设置',
}
const currentTitle = computed(() => titleMap[route.path] || 'SmartOpsDocs')
const runtimeLabel = computed(() => {
  if (runtimeStatus.value === 'ok') return '后端正常'
  if (runtimeStatus.value === 'degraded') return '后端降级'
  if (runtimeStatus.value === 'offline') return '后端离线'
  return '检查中'
})
const runtimeDetail = computed(() => {
  if (runtimeStatus.value === 'offline') return 'API :8000 无响应'
  if (runtimeStatus.value === 'degraded' && runtimeIssueText.value) return runtimeIssueText.value
  if (!runtimeCounts.value) return 'API :8000'
  return `${runtimeCounts.servers} 台资产 / ${runtimeCounts.documents} 篇文档`
})
const runtimeIssueText = computed(() => {
  const issue = runtimeIssues.value[0]
  if (!issue) return ''
  const name = issue.name ? `${issue.scope || 'runtime'}:${issue.name}` : issue.scope || 'runtime'
  return `${name} ${issue.error || '异常'}`
})
const runtimeTagType = computed(() => {
  if (runtimeStatus.value === 'ok') return 'success'
  if (runtimeStatus.value === 'degraded') return 'warning'
  if (runtimeStatus.value === 'offline') return 'danger'
  return 'info'
})
const runtimeTagText = computed(() => {
  if (runtimeStatus.value === 'ok') return '后端正常'
  if (runtimeStatus.value === 'degraded') return '后端降级'
  if (runtimeStatus.value === 'offline') return '后端离线'
  return '检查中'
})
function logout() {
  localStorage.removeItem('smartopsdocs_token')
  router.push('/login')
}
</script>

<style scoped>
.layout {
  min-height: 100dvh;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.36), transparent 280px),
    transparent;
}

.sidebar {
  position: sticky;
  top: 0;
  z-index: 3;
  height: 100dvh;
  border-right: 1px solid var(--app-sidebar-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.78), transparent 34%),
    var(--app-sidebar-bg);
  transition: width 0.25s ease, background-color 0.3s;
  overflow: hidden;
  display: grid;
  grid-template-rows: auto minmax(0, 1fr) auto;
  box-shadow: 8px 0 28px rgba(23, 49, 56, 0.04);
}

:global(html.dark) .sidebar {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), transparent 28%),
    var(--app-sidebar-bg);
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  height: 76px;
  padding: 0 20px;
  border-bottom: 1px solid var(--app-border-soft);
  white-space: nowrap;
}

.brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  border-radius: var(--app-radius-md);
  color: #fff;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.18), transparent 38%),
    var(--app-primary);
  font-weight: 800;
  box-shadow: 0 10px 24px rgba(15, 118, 110, 0.22), inset 0 1px 0 rgba(255, 255, 255, 0.22);
  place-items: center;
  flex-shrink: 0;
}

.brand-name {
  color: var(--app-text-heading);
  font-size: 17px;
  font-weight: 800;
  line-height: 1.2;
}

.brand-sub {
  margin-top: 2px;
  color: var(--app-muted);
  font-size: 12px;
}

.nav-scroll {
  min-height: 0;
  overflow: auto;
}

:deep(.el-menu) {
  border-right: 0;
  padding: 14px 10px;
}

.nav-section-label {
  margin: 14px 10px 8px;
  color: var(--app-muted-soft);
  font-size: 11px;
  font-weight: 760;
  letter-spacing: 0;
  text-transform: uppercase;
}

:deep(.el-menu-item) {
  height: 42px;
  margin-bottom: 5px;
  border-radius: var(--app-radius);
  color: var(--app-text-soft);
  font-weight: 650;
  transition: background-color 0.16s ease, color 0.16s ease, transform 0.16s ease, box-shadow 0.16s ease;
}

:deep(.el-menu-item .el-icon) {
  color: var(--app-muted);
  transition: color 0.16s ease;
}

:deep(.el-menu-item:hover) {
  background: var(--app-sidebar-item-hover);
  transform: translateX(2px);
  box-shadow: inset 0 0 0 1px var(--app-border-soft);
}

:deep(.el-menu-item.is-active) {
  color: var(--app-primary);
  background:
    linear-gradient(90deg, var(--app-primary-soft), var(--app-primary-softer));
  box-shadow: inset 3px 0 0 var(--app-primary), 0 1px 0 rgba(255, 255, 255, 0.58) inset;
}

:deep(.el-menu-item.is-active .el-icon) {
  color: var(--app-primary);
}

.sidebar-status {
  display: flex;
  gap: 10px;
  align-items: center;
  margin: 10px;
  padding: 13px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.45), transparent),
    var(--app-surface-soft);
  box-shadow: var(--app-shadow-sm);
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

.sidebar-toggle {
  display: none;
  font-size: 18px;
}

.el-header {
  position: sticky;
  top: 0;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 68px;
  border-bottom: 1px solid var(--app-header-border);
  background: var(--app-header-bg);
  backdrop-filter: blur(16px);
  transition: background-color 0.3s, border-color 0.3s;
  box-shadow: 0 1px 0 rgba(255, 255, 255, 0.42) inset;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: 700;
}

.header-title span {
  display: block;
  color: var(--app-text-heading);
  font-size: 17px;
  line-height: 1.2;
}

.header-title small {
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 500;
  display: block;
}

.header-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.content-shell {
  min-width: 0;
}

.main-content {
  width: min(100%, 1480px);
  margin: 0 auto;
  padding: 28px;
}

/* ---- Responsive ---- */
@media (max-width: 900px) {
  .layout {
    display: block;
  }
  .sidebar {
    position: relative;
    width: 100% !important;
    height: auto;
    border-right: 0;
    border-bottom: 1px solid var(--app-sidebar-border);
  }
  .layout.sidebar-collapsed .sidebar {
    height: 0;
    border-bottom: 0;
  }
  .sidebar:not([width="0px"]) {
    width: 100% !important;
  }
  .brand {
    height: 56px;
  }
  :deep(.el-menu) {
    display: flex;
    overflow-x: auto;
    border-right: 0;
  }
  .nav-scroll {
    overflow: visible;
  }
  .nav-section-label,
  .sidebar-status {
    display: none;
  }
  :deep(.el-menu-item) { flex: 0 0 auto; }
  :deep(.el-menu-item:hover) {
    transform: none;
  }
  .sidebar-toggle {
    display: inline-flex;
  }
  .el-header {
    height: 62px;
    padding: 0 14px;
  }
  .header-actions {
    gap: 4px;
  }
  .main-content {
    padding: 18px 14px 24px;
  }
}

@media (max-width: 560px) {
  .header-title small,
  .header-actions .el-tag {
    display: none;
  }
}
</style>
