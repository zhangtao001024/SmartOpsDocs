<template>
  <el-container class="layout">
    <el-aside :width="sidebarCollapsed ? '0px' : '230px'" class="sidebar">
      <div class="brand">
        <div class="brand-mark">S</div>
        <div>
          <div class="brand-name">SmartOpsDocs</div>
          <div class="brand-sub">Ops Knowledge</div>
        </div>
      </div>
      <el-menu :default-active="$route.path" router>
        <el-menu-item index="/"><el-icon><DataAnalysis /></el-icon><span>概览</span></el-menu-item>
        <el-menu-item index="/servers"><el-icon><Monitor /></el-icon><span>服务器资产</span></el-menu-item>
        <el-menu-item index="/docker"><el-icon><Box /></el-icon><span>Docker 管理</span></el-menu-item>
        <el-menu-item index="/k8s"><el-icon><Connection /></el-icon><span>Kubernetes</span></el-menu-item>
        <el-menu-item index="/documents"><el-icon><Document /></el-icon><span>知识库文档</span></el-menu-item>
        <el-menu-item index="/chat"><el-icon><ChatDotRound /></el-icon><span>AI 助手</span></el-menu-item>
        <el-menu-item index="/settings"><el-icon><Setting /></el-icon><span>模型设置</span></el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header>
        <div class="header-title">
          <el-button class="sidebar-toggle" text :icon="sidebarCollapsed ? 'Expand' : 'Fold'" @click="sidebarCollapsed = !sidebarCollapsed" />
          <span>{{ currentTitle }}</span>
          <small>Local workspace</small>
        </div>
        <div class="header-actions">
          <el-button text :icon="theme === 'dark' ? 'Sunny' : 'Moon'" @click="toggleTheme" :title="theme === 'dark' ? '切换亮色' : '切换暗色'" />
          <el-tag size="small" type="success" effect="plain">本地运行</el-tag>
          <el-button text icon="SwitchButton" @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useRoute } from 'vue-router'
import useTheme from '../composables/useTheme'

const router = useRouter()
const route = useRoute()
const { theme, toggleTheme } = useTheme()
const sidebarCollapsed = ref(window.innerWidth < 900)

// Listen for resize to auto-collapse/expand sidebar
window.addEventListener('resize', () => {
  sidebarCollapsed.value = window.innerWidth < 900
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
function logout() {
  localStorage.removeItem('smartopsdocs_token')
  router.push('/login')
}
</script>

<style scoped>
.layout {
  min-height: 100vh;
}

.sidebar {
  border-right: 1px solid var(--app-sidebar-border);
  background: var(--app-sidebar-bg);
  transition: width 0.25s ease, background-color 0.3s;
  overflow: hidden;
}

.brand {
  display: flex;
  gap: 12px;
  align-items: center;
  height: 72px;
  padding: 0 18px;
  border-bottom: 1px solid var(--app-border-soft);
  white-space: nowrap;
}

.brand-mark {
  display: grid;
  width: 36px;
  height: 36px;
  border-radius: var(--app-radius-md);
  color: #fff;
  background: var(--app-primary);
  font-weight: 800;
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

:deep(.el-menu) {
  border-right: 0;
  padding: 10px;
}

:deep(.el-menu-item) {
  height: 42px;
  margin-bottom: 4px;
  border-radius: var(--app-radius);
  color: var(--app-text-soft);
  font-weight: 600;
  transition: background-color 0.15s, color 0.15s;
}

:deep(.el-menu-item:hover) {
  background: var(--app-sidebar-item-hover);
}

:deep(.el-menu-item.is-active) {
  color: var(--app-primary);
  background: var(--app-primary-soft);
}

.sidebar-toggle {
  display: none;
  font-size: 18px;
}

.el-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 64px;
  border-bottom: 1px solid var(--app-header-border);
  background: var(--app-header-bg);
  backdrop-filter: blur(10px);
  transition: background-color 0.3s, border-color 0.3s;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 700;
}

.header-title > span {
  font-size: 17px;
}

.header-title small {
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 500;
  display: block;
}

.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}

.el-main {
  padding: 22px;
}

/* ---- Responsive ---- */
@media (max-width: 900px) {
  .layout {
    display: block;
  }
  .sidebar {
    width: 100% !important;
    border-right: 0;
    border-bottom: 1px solid var(--app-sidebar-border);
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
  :deep(.el-menu-item) { flex: 0 0 auto; }
  .sidebar-toggle {
    display: inline-flex;
  }
}
</style>
