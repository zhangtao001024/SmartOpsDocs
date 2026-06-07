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
          <el-tag size="small" effect="plain" :type="form.chat.api_key ? 'success' : 'info'">{{ form.chat.api_key ? '独立 Key' : '环境变量' }}</el-tag>
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
      </div>

      <div class="panel settings-card">
        <div class="settings-card-head">
          <div>
            <span>Optimize</span>
            <h3>知识库优化模型</h3>
          </div>
          <el-tag size="small" effect="plain" :type="form.optimize.api_key ? 'success' : 'info'">{{ form.optimize.api_key ? '独立 Key' : '环境变量' }}</el-tag>
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
      </div>

      <div class="panel settings-card">
        <div class="settings-card-head">
          <div>
            <span>Web pull</span>
            <h3>网页知识拉取模型</h3>
          </div>
          <el-tag size="small" effect="plain" :type="form.pull.api_key ? 'success' : 'info'">{{ form.pull.api_key ? '独立 Key' : '环境变量' }}</el-tag>
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
})

const apiKeyCount = computed(() => {
  return [form.chat.api_key, form.optimize.api_key, form.pull.api_key]
    .filter((value) => value && value.trim())
    .length
})

async function load() {
  try {
    const resp = await client.get('/api/settings')
    Object.assign(form.chat, resp.data.chat)
    Object.assign(form.optimize, resp.data.optimize)
    Object.assign(form.pull, resp.data.pull)
  } catch (e) { /* ignore */ }
}

async function save() {
  saving.value = true
  try {
    await client.put('/api/settings', { chat: form.chat, optimize: form.optimize, pull: form.pull })
    ElMessage.success('模型配置已保存')
  } catch (e) {
    ElMessage.error(getApiErrorMessage(e, '保存失败'))
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
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
</style>
