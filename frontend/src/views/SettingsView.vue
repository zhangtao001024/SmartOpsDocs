<template>
  <div class="console-page">
    <section class="console-hero">
      <div class="page-heading">
        <p class="page-kicker">Model runtime</p>
        <h2 class="page-title">模型设置</h2>
        <p class="page-subtitle">分别配置助手问答、知识库优化和网页拉取使用的模型入口，未填写 Key 时回退到环境变量。</p>
        <div class="console-status-strip">
          <span><strong>{{ apiKeyCount }}/3</strong> 已填 Key</span>
          <span><strong>{{ form.chat.model || '-' }}</strong> 助手模型</span>
          <span><strong>{{ agentRuntimeLabel }}</strong> Agent Runtime</span>
          <span><strong>{{ form.optimize.vision_model || '文本模型' }}</strong> 视觉解析</span>
        </div>
      </div>
      <el-button type="primary" icon="Check" :loading="saving" @click="save">保存配置</el-button>
    </section>

    <div class="settings-grid">
      <div class="panel settings-card">
        <div class="settings-card-head">
          <div>
            <span>Chat</span>
            <h3>AI 助手模型</h3>
          </div>
          <div class="settings-card-actions">
            <el-tag size="small" effect="plain" :type="form.chat.api_key ? 'success' : 'info'">{{ form.chat.api_key ? '独立 Key' : '环境变量' }}</el-tag>
            <el-button size="small" :loading="testing.chat" @click="testConfig('chat')">测试</el-button>
          </div>
        </div>
        <el-form :model="form.chat" label-width="100px">
          <el-form-item label="API Key">
            <el-input v-model="form.chat.api_key" type="password" show-password placeholder="sk-..." />
          </el-form-item>
          <el-form-item label="Base URL">
            <el-input v-model="form.chat.base_url" placeholder="https://api.openai.com/v1，留空用默认" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="form.chat.model" placeholder="gpt-4o-mini" />
          </el-form-item>
        </el-form>
        <div :class="['test-result', testResults.chat.status]">
          <strong>{{ testResultTitle('chat') }}</strong>
          <span>{{ testResultMessage('chat') }}</span>
        </div>
      </div>

      <div class="panel settings-card">
        <div class="settings-card-head">
          <div>
            <span>Optimize</span>
            <h3>知识库优化模型</h3>
          </div>
          <div class="settings-card-actions">
            <el-tag size="small" effect="plain" :type="form.optimize.api_key ? 'success' : 'info'">{{ form.optimize.api_key ? '独立 Key' : '环境变量' }}</el-tag>
            <el-button size="small" :loading="testing.optimize" @click="testConfig('optimize')">测试</el-button>
          </div>
        </div>
        <el-form :model="form.optimize" label-width="100px">
          <el-form-item label="API Key">
            <el-input v-model="form.optimize.api_key" type="password" show-password placeholder="sk-..." />
          </el-form-item>
          <el-form-item label="Base URL">
            <el-input v-model="form.optimize.base_url" placeholder="https://api.openai.com/v1，留空用默认" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="form.optimize.model" placeholder="gpt-4o-mini" />
          </el-form-item>
          <el-form-item label="视觉模型">
            <el-input v-model="form.optimize.vision_model" placeholder="用于解析 Word 文档内嵌图片，留空用文本模型" />
          </el-form-item>
        </el-form>
        <div :class="['test-result', testResults.optimize.status]">
          <strong>{{ testResultTitle('optimize') }}</strong>
          <span>{{ testResultMessage('optimize') }}</span>
        </div>
      </div>

      <div class="panel settings-card">
        <div class="settings-card-head">
          <div>
            <span>Web pull</span>
            <h3>网页知识拉取模型</h3>
          </div>
          <div class="settings-card-actions">
            <el-tag size="small" effect="plain" :type="form.pull.api_key ? 'success' : 'info'">{{ form.pull.api_key ? '独立 Key' : '环境变量' }}</el-tag>
            <el-button size="small" :loading="testing.pull" @click="testConfig('pull')">测试</el-button>
          </div>
        </div>
        <el-form :model="form.pull" label-width="100px">
          <el-form-item label="API Key">
            <el-input v-model="form.pull.api_key" type="password" show-password placeholder="sk-..." />
          </el-form-item>
          <el-form-item label="Base URL">
            <el-input v-model="form.pull.base_url" placeholder="https://api.openai.com/v1，留空用默认" />
          </el-form-item>
          <el-form-item label="模型">
            <el-input v-model="form.pull.model" placeholder="gpt-4o-mini" />
          </el-form-item>
        </el-form>
        <div :class="['test-result', testResults.pull.status]">
          <strong>{{ testResultTitle('pull') }}</strong>
          <span>{{ testResultMessage('pull') }}</span>
        </div>
      </div>

      <div class="panel settings-card agent-runtime-card">
        <div class="settings-card-head">
          <div>
            <span>Agent</span>
            <h3>OpenClaw Runtime</h3>
          </div>
          <div class="settings-card-actions">
            <el-tag size="small" effect="plain" :type="form.agent.runtime === 'openclaw' ? 'success' : 'info'">
              {{ agentRuntimeLabel }}
            </el-tag>
            <el-button size="small" :loading="testing.agent" @click="testConfig('agent')">测试</el-button>
          </div>
        </div>
        <el-form :model="form.agent" label-width="100px">
          <el-form-item label="Runtime">
            <el-select v-model="form.agent.runtime">
              <el-option label="本地 OpenClaw 兼容" value="local-openclaw" />
              <el-option label="OpenClaw 本机 Agent" value="openclaw" />
            </el-select>
          </el-form-item>
          <el-form-item label="Endpoint">
            <el-input v-model="form.agent.endpoint" placeholder="留空使用本机 openclaw agent；或填完整 HTTP URL" />
          </el-form-item>
          <el-form-item label="API Key">
            <el-input v-model="form.agent.api_key" type="password" show-password placeholder="HTTP Endpoint Bearer Token，可选" />
          </el-form-item>
          <el-form-item label="Agent">
            <el-input v-model="form.agent.agent" placeholder="main" />
          </el-form-item>
        </el-form>
        <div :class="['test-result', testResults.agent.status]">
          <strong>{{ testResultTitle('agent') }}</strong>
          <span>{{ testResultMessage('agent') }}</span>
        </div>
      </div>
    </div>

    <div class="settings-note">
      <strong>配置优先级</strong>
      <span>页面配置优先于环境变量；未配置 API Key 时自动使用环境变量 / .env 中的 OPENAI_API_KEY 等值。</span>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import client, { getApiErrorMessage } from '../api/client'

const saving = ref(false)
const form = reactive({
  chat: { api_key: '', base_url: '', model: 'gpt-4o-mini', vision_model: '' },
  optimize: { api_key: '', base_url: '', model: 'gpt-4o-mini', vision_model: '' },
  pull: { api_key: '', base_url: '', model: 'gpt-4o-mini', vision_model: '' },
  agent: { runtime: 'local-openclaw', endpoint: '', api_key: '', agent: 'main' },
})
const testing = reactive({ chat: false, optimize: false, pull: false, agent: false })
const testResults = reactive({
  chat: { status: 'idle', message: '尚未验证当前配置', latency_ms: null },
  optimize: { status: 'idle', message: '尚未验证当前配置', latency_ms: null },
  pull: { status: 'idle', message: '尚未验证当前配置', latency_ms: null },
  agent: { status: 'idle', message: '尚未验证当前配置', latency_ms: null },
})

const apiKeyCount = computed(() => {
  return [form.chat.api_key, form.optimize.api_key, form.pull.api_key]
    .filter((value) => value && value.trim())
    .length
})

const agentRuntimeLabel = computed(() => {
  return form.agent.runtime === 'openclaw' ? 'OpenClaw' : 'Local'
})

function testResultTitle(scope) {
  if (testing[scope]) return '验证中'
  const status = testResults[scope].status
  if (status === 'ok') return '配置可用'
  if (status === 'warning') return '需要确认'
  if (status === 'error') return '验证失败'
  return '未测试'
}

function testResultMessage(scope) {
  if (testing[scope]) return '正在请求模型服务，请稍候'
  const result = testResults[scope]
  if (['ok', 'warning'].includes(result.status) && result.latency_ms) return `${result.message}（${result.latency_ms}ms）`
  return result.message
}

async function load() {
  try {
    const resp = await client.get('/api/settings')
    Object.assign(form.chat, resp.data.chat)
    Object.assign(form.optimize, resp.data.optimize)
    Object.assign(form.pull, resp.data.pull)
    if (resp.data.agent) Object.assign(form.agent, resp.data.agent)
  } catch (e) { /* ignore */ }
}

async function save() {
  if (form.agent.runtime === 'openclaw') {
    const endpoint = form.agent.endpoint.trim()
    if (endpoint && !/^https?:\/\//.test(endpoint)) {
      ElMessage.error('OpenClaw Endpoint 必须是 http:// 或 https:// 开头的完整 URL')
      return
    }
  }
  saving.value = true
  try {
    await client.put('/api/settings', { chat: form.chat, optimize: form.optimize, pull: form.pull, agent: form.agent })
    ElMessage.success('模型配置已保存')
  } catch (e) {
    ElMessage.error(getApiErrorMessage(e, '保存失败'))
  } finally {
    saving.value = false
  }
}

async function testConfig(scope) {
  if (scope === 'agent') {
    const endpoint = form.agent.endpoint.trim()
    if (form.agent.runtime === 'openclaw' && endpoint && !/^https?:\/\//.test(endpoint)) {
      testResults.agent = { status: 'error', message: 'OpenClaw Endpoint 必须是 http:// 或 https:// 开头的完整 URL', latency_ms: null }
      ElMessage.error('OpenClaw Endpoint 必须是 http:// 或 https:// 开头的完整 URL')
      return
    }
  }
  testing[scope] = true
  testResults[scope] = { status: 'pending', message: '正在请求模型服务，请稍候', latency_ms: null }
  try {
    const { data } = await client.post('/api/settings/test', { scope, config: form[scope] })
    const status = data.level === 'warning' ? 'warning' : 'ok'
    const message = data.message || '配置可用'
    testResults[scope] = { status, message, latency_ms: data.latency_ms || null }
    const toast = data.latency_ms ? `${message}（${data.latency_ms}ms）` : message
    if (status === 'warning') ElMessage.warning(toast)
    else ElMessage.success(toast)
  } catch (e) {
    const message = getApiErrorMessage(e, '验证失败')
    testResults[scope] = { status: 'error', message, latency_ms: null }
    ElMessage.error(message)
  } finally {
    testing[scope] = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.settings-card {
  display: grid;
  align-content: start;
  gap: 16px;
}

.settings-card-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--app-border-soft);
}

.settings-card-head span {
  display: block;
  margin-bottom: 5px;
  color: var(--app-muted);
  font-size: 11px;
  font-weight: 760;
  text-transform: uppercase;
}

.settings-card h3 {
  margin: 0;
  color: var(--app-text-heading);
  font-size: 17px;
}

.settings-card-actions {
  display: inline-flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-wrap: wrap;
}

.settings-card-actions .el-button {
  min-height: 28px;
  padding: 0 10px;
}

.test-result {
  display: grid;
  gap: 4px;
  min-height: 58px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  padding: 10px 12px;
  color: var(--app-muted);
  background: var(--app-surface-soft);
  font-size: 12px;
}

.test-result strong {
  color: var(--app-text-heading);
  font-size: 13px;
}

.test-result span {
  line-height: 1.45;
  word-break: break-word;
}

.test-result.pending {
  border-color: color-mix(in srgb, var(--app-primary) 36%, var(--app-border-soft));
  background: color-mix(in srgb, var(--app-primary) 8%, var(--app-surface-soft));
}

.test-result.ok {
  border-color: color-mix(in srgb, var(--app-success) 42%, var(--app-border-soft));
  background: color-mix(in srgb, var(--app-success) 10%, var(--app-surface-soft));
}

.test-result.ok strong {
  color: var(--app-success);
}

.test-result.warning {
  border-color: color-mix(in srgb, var(--app-warning) 46%, var(--app-border-soft));
  background: color-mix(in srgb, var(--app-warning) 10%, var(--app-surface-soft));
}

.test-result.warning strong {
  color: var(--app-warning);
}

.test-result.error {
  border-color: color-mix(in srgb, var(--app-danger) 46%, var(--app-border-soft));
  background: color-mix(in srgb, var(--app-danger) 10%, var(--app-surface-soft));
}

.test-result.error strong {
  color: var(--app-danger);
}

.agent-runtime-card {
  background:
    linear-gradient(90deg, var(--app-surface), var(--app-primary-softer) 72%, color-mix(in srgb, var(--app-accent-soft) 44%, transparent));
}

.settings-note {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-top: 0;
  padding: 12px 14px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  color: var(--app-muted);
  background: var(--app-surface-soft);
  font-size: 13px;
}

.settings-note strong {
  color: var(--app-text-heading);
}

@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}

@media (min-width: 901px) and (max-width: 1280px) {
  .settings-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
