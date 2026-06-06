<template>
  <div class="login-page">
    <div class="login-panel">
      <div class="login-brand">
        <div class="brand-mark">S</div>
        <div>
          <h1>SmartOpsDocs</h1>
          <p>Ops Knowledge Workspace</p>
        </div>
      </div>
      <el-form :model="form" @submit.prevent="login">
        <el-form-item>
          <el-input v-model="form.username" prefix-icon="User" placeholder="用户名" />
        </el-form-item>
        <el-form-item>
          <el-input v-model="form.password" prefix-icon="Lock" placeholder="密码" type="password" show-password />
        </el-form-item>
        <el-button type="primary" :loading="loading" @click="login">登录</el-button>
      </el-form>
      <p class="muted">默认账号：admin / admin123</p>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import client from '../api/client'

const router = useRouter()
const loading = ref(false)
const form = reactive({ username: 'admin', password: 'admin123' })

async function login() {
  loading.value = true
  try {
    const { data } = await client.post('/api/auth/login', form)
    localStorage.setItem('smartopsdocs_token', data.access_token)
    router.push('/servers')
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: var(--app-bg);
  transition: background-color 0.3s;
}

.login-panel {
  width: min(380px, calc(100vw - 32px));
  padding: 30px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  box-shadow: var(--app-shadow-lg);
  transition: background-color 0.3s, border-color 0.3s, box-shadow 0.3s;
}

.login-brand {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 24px;
}

.brand-mark {
  display: grid;
  width: 42px;
  height: 42px;
  border-radius: var(--app-radius-md);
  color: #fff;
  background: var(--app-primary);
  font-weight: 800;
  place-items: center;
}

h1 {
  margin: 0;
  font-size: 24px;
  line-height: 1.2;
  color: var(--app-text-heading);
}

.login-brand p {
  margin: 4px 0 0;
  color: var(--app-muted);
  font-size: 13px;
}

.el-button {
  width: 100%;
}
</style>
