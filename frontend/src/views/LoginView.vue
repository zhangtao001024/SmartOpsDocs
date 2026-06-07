<template>
  <main class="login-page">
    <section class="login-copy" aria-label="SmartOpsDocs">
      <div class="brand-lockup">
        <div class="brand-mark">SD</div>
        <div>
          <div class="brand-name">SmartOpsDocs</div>
          <div class="brand-sub">Ops Knowledge Workspace</div>
        </div>
      </div>
      <p class="eyebrow">Local ops workspace</p>
      <h1>把运维资产、知识库和 AI 问答放进同一个工作台。</h1>
      <p class="intro">面向本地部署场景，减少分散入口，让服务器、容器、K8s 与文档检索保持在一条操作链路里。</p>
      <div class="signal-grid">
        <div>
          <span>Assets</span>
          <strong>SSH / Docker / K8s</strong>
        </div>
        <div>
          <span>Knowledge</span>
          <strong>Docs + RAG</strong>
        </div>
        <div>
          <span>Agent</span>
          <strong>Dry-run first</strong>
        </div>
      </div>
      <div class="login-diagram" aria-hidden="true">
        <span class="diagram-node primary">Assets</span>
        <span class="diagram-line"></span>
        <span class="diagram-node">Docs</span>
        <span class="diagram-line accent"></span>
        <span class="diagram-node">Agent</span>
      </div>
    </section>

    <section class="login-panel" aria-label="登录">
      <div class="panel-header">
        <p>登录工作台</p>
        <h2>继续进入本地环境</h2>
        <div class="login-status">
          <span></span>
          API proxy :8000
        </div>
      </div>
      <el-form :model="form" @submit.prevent="login" label-position="top">
        <el-form-item>
          <el-input v-model="form.username" prefix-icon="User" placeholder="用户名" autocomplete="username" />
        </el-form-item>
        <el-form-item>
          <el-input
            v-model="form.password"
            prefix-icon="Lock"
            placeholder="密码"
            type="password"
            autocomplete="current-password"
            show-password
          />
        </el-form-item>
        <el-button type="primary" :loading="loading" :disabled="!canSubmit" @click="login">登录</el-button>
      </el-form>
      <p class="muted">默认账号：admin / admin123</p>
    </section>
  </main>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import client, { getApiErrorMessage } from '../api/client'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin123' })
const canSubmit = computed(() => Boolean(form.username.trim() && form.password.trim()))

async function login() {
  if (!canSubmit.value || loading.value) return
  loading.value = true
  try {
    const { data } = await client.post('/api/auth/login', form)
    localStorage.setItem('smartopsdocs_token', data.access_token)
    router.push('/servers')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '登录失败'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100dvh;
  display: grid;
  grid-template-columns: minmax(0, 1fr) 456px;
  align-items: center;
  gap: 96px;
  padding: 64px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.7), transparent 340px),
    linear-gradient(90deg, rgba(12, 118, 111, 0.12), transparent 44%, rgba(168, 85, 30, 0.06)),
    repeating-linear-gradient(0deg, rgba(16, 23, 19, 0.03) 0 1px, transparent 1px 30px),
    repeating-linear-gradient(90deg, rgba(16, 23, 19, 0.026) 0 1px, transparent 1px 30px),
    var(--app-bg);
  transition: background-color 0.3s;
}

.login-copy {
  max-width: 760px;
}

.brand-lockup {
  display: flex;
  gap: 16px;
  align-items: center;
  margin-bottom: 96px;
}

.brand-mark {
  display: grid;
  width: 48px;
  height: 48px;
  border-radius: var(--app-radius);
  color: #fff;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.2), transparent 40%),
    linear-gradient(160deg, var(--app-primary), var(--app-primary-strong) 62%, var(--app-accent)),
    var(--app-primary);
  box-shadow: 0 16px 34px rgba(12, 118, 111, 0.24);
  font-family: var(--app-font-display);
  font-size: 14px;
  font-weight: 860;
  place-items: center;
}

.brand-name {
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 18px;
  font-weight: 840;
  line-height: 1.15;
}

.brand-sub {
  margin-top: 3px;
  color: var(--app-muted);
  font-size: 12px;
}

.eyebrow {
  margin: 0 0 16px;
  color: var(--app-accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

h1 {
  max-width: 13ch;
  margin: 0;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 74px;
  font-weight: 860;
  line-height: 0.96;
  text-wrap: balance;
}

.intro {
  max-width: 58ch;
  margin: 24px 0 0;
  color: var(--app-muted);
  font-size: 16px;
  line-height: 1.8;
}

.signal-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 190px));
  gap: 16px;
  margin-top: 40px;
}

.signal-grid div {
  min-height: 96px;
  padding: 16px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.7), transparent),
    linear-gradient(135deg, rgba(12, 118, 111, 0.055), transparent 58%),
    rgba(251, 252, 253, 0.78);
  box-shadow: var(--app-shadow);
}

:global(html.dark) .signal-grid div {
  background: rgba(24, 35, 40, 0.72);
}

.signal-grid span {
  display: block;
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 680;
}

.signal-grid strong {
  display: block;
  margin-top: 16px;
  color: var(--app-text-heading);
  font-size: 15px;
  font-weight: 760;
}

.login-diagram {
  display: grid;
  grid-template-columns: auto minmax(36px, 120px) auto minmax(36px, 120px) auto;
  align-items: center;
  gap: 16px;
  width: 620px;
  margin-top: 32px;
  padding: 16px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background: color-mix(in srgb, var(--app-surface-raised) 74%, transparent);
  box-shadow: var(--app-shadow-xs);
}

.diagram-node {
  min-width: 86px;
  padding: 8px 16px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius);
  color: var(--app-text-heading);
  background: var(--app-surface-soft);
  font-family: var(--app-font-mono);
  font-size: 12px;
  font-weight: 760;
  text-align: center;
}

.diagram-node.primary {
  border-color: var(--app-primary-border);
  color: var(--app-primary);
  background: var(--app-primary-softer);
}

.diagram-line {
  height: 1px;
  background: linear-gradient(90deg, var(--app-primary-border), var(--app-border-strong));
}

.diagram-line.accent {
  background: linear-gradient(90deg, var(--app-border-strong), var(--app-accent));
}

.login-panel {
  position: relative;
  overflow: hidden;
  width: 100%;
  padding: 32px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(255, 255, 255, 0)),
    repeating-linear-gradient(135deg, rgba(16, 23, 19, 0.025) 0 1px, transparent 1px 18px),
    var(--app-surface);
  box-shadow: var(--app-shadow-lg);
  transition: background-color 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.login-panel::before {
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: linear-gradient(90deg, var(--app-primary), var(--app-primary-border), var(--app-accent), transparent);
  content: '';
}

:global(html.dark) .login-panel {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.04), rgba(255, 255, 255, 0)),
    var(--app-surface);
}

.panel-header {
  margin-bottom: 24px;
}

.panel-header p {
  margin: 0 0 8px;
  color: var(--app-accent);
  font-size: 12px;
  font-weight: 800;
}

.panel-header h2 {
  margin: 0;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 26px;
  line-height: 1.25;
}

.login-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
  padding: 7px 10px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius);
  color: var(--app-muted);
  background: var(--app-surface-soft);
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.login-status span {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--app-success);
  box-shadow: 0 0 0 4px var(--app-success-soft);
}

.el-form {
  display: grid;
  gap: 8px;
}

.el-button {
  width: 100%;
  min-height: 48px;
}

.muted {
  margin: 16px 0 0;
  font-size: 12px;
}
</style>
