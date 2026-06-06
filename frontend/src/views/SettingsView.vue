<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">模型设置</h2>
      <el-button type="primary" icon="Check" :loading="saving" @click="save">保存配置</el-button>
    </div>

    <div class="settings-grid">
      <div class="panel">
        <h3>AI 助手模型</h3>
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

      <div class="panel">
        <h3>知识库优化模型</h3>
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

      <div class="panel">
        <h3>网页知识拉取模型</h3>
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

    <div class="muted" style="margin-top: 12px; font-size: 13px">
      未配置时自动使用环境变量 / .env 中的 OPENAI_API_KEY 等值。
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const saving = ref(false)
const form = reactive({
  chat: { api_key: '', base_url: '', model: 'gpt-4o-mini', vision_model: '' },
  optimize: { api_key: '', base_url: '', model: 'gpt-4o-mini', vision_model: '' },
  pull: { api_key: '', base_url: '', model: 'gpt-4o-mini', vision_model: '' },
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
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.panel h3 {
  margin: 0 0 16px;
  color: var(--app-text-heading);
  font-size: 17px;
}

@media (max-width: 900px) {
  .settings-grid {
    grid-template-columns: 1fr;
  }
}
</style>
