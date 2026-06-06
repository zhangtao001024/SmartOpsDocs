<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">Docker 管理</h2>
      <div style="display: flex; gap: 8px; align-items: center">
        <el-select v-model="serverId" placeholder="选择服务器" style="width: 260px" @change="loadAll">
          <el-option v-for="server in servers" :key="server.id" :label="server.ip + ' ' + server.hostname" :value="server.id" />
        </el-select>
        <el-input-number v-model="logTail" :min="50" :max="5000" :step="50" controls-position="right" style="width: 130px" />
        <el-button icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
    </div>
    <div class="panel">
      <el-empty v-if="!serverId" description="请先选择一个服务器" />
      <el-tabs v-else v-model="tab" @tab-change="loadAll">
        <el-tab-pane label="容器" name="containers">
          <SkeletonTable v-if="loading && containers.length === 0" :rows="5" :cols="5" />
          <el-empty v-else-if="!loading && containers.length === 0" description="该服务器暂无运行中的容器" />
          <el-table v-else :data="containers" v-loading="loading">
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="image" label="镜像" />
            <el-table-column label="CPU" width="100">
              <template #default="{ row }">{{ containerStats(row).cpu || '-' }}</template>
            </el-table-column>
            <el-table-column label="内存" width="180">
              <template #default="{ row }">{{ containerStats(row).memory || '-' }}</template>
            </el-table-column>
            <el-table-column label="网络 IO" width="160">
              <template #default="{ row }">{{ containerStats(row).net_io || '-' }}</template>
            </el-table-column>
            <el-table-column prop="status" label="状态">
              <template #default="{ row }">
                <el-tag :type="containerStatusType(row.status)" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="ports" label="端口" />
            <el-table-column label="操作" width="280" fixed="right">
              <template #default="{ row }">
                <el-button size="small" :loading="acting === row.id + '-start'" @click="action(row, 'start')">启动</el-button>
                <el-button size="small" :loading="acting === row.id + '-stop'" @click="action(row, 'stop')">停止</el-button>
                <el-button size="small" type="warning" :loading="acting === row.id + '-restart'" @click="action(row, 'restart')">重启</el-button>
                <el-button size="small" @click="showLogs(row)">日志</el-button>
                <el-button size="small" @click="showTop(row)">Top</el-button>
                <el-button size="small" @click="showInspect(row)">Inspect</el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="镜像" name="images">
          <SkeletonTable v-if="loading && images.length === 0" :rows="5" :cols="5" />
          <el-empty v-else-if="!loading && images.length === 0" description="该服务器暂无 Docker 镜像" />
          <el-table v-else :data="images" v-loading="loading">
            <el-table-column prop="repository" label="仓库" />
            <el-table-column prop="tag" label="标签" width="150" />
            <el-table-column prop="image_id" label="ID" />
            <el-table-column prop="size" label="大小" width="120" />
            <el-table-column prop="created" label="创建时间" width="180" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="网络" name="networks">
          <SkeletonTable v-if="loading && networks.length === 0" :rows="5" :cols="4" />
          <el-empty v-else-if="!loading && networks.length === 0" description="该服务器暂无 Docker 网络" />
          <el-table v-else :data="networks" v-loading="loading">
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="driver" label="驱动" width="120" />
            <el-table-column prop="scope" label="范围" width="120" />
            <el-table-column prop="id" label="ID" />
          </el-table>
        </el-tab-pane>
        <el-tab-pane label="卷" name="volumes">
          <SkeletonTable v-if="loading && volumes.length === 0" :rows="5" :cols="4" />
          <el-empty v-else-if="!loading && volumes.length === 0" description="该服务器暂无 Docker 卷" />
          <el-table v-else :data="volumes" v-loading="loading">
            <el-table-column prop="name" label="名称" />
            <el-table-column prop="driver" label="驱动" width="120" />
            <el-table-column prop="scope" label="范围" width="120" />
            <el-table-column prop="mountpoint" label="挂载点" />
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>
    <el-dialog v-model="logsVisible" title="容器日志" width="860px">
      <pre class="log-box">{{ logs }}</pre>
    </el-dialog>
    <el-dialog v-model="inspectVisible" title="容器 Inspect" width="920px">
      <pre class="log-box">{{ inspectText }}</pre>
    </el-dialog>
    <el-dialog v-model="topVisible" title="容器进程" width="860px">
      <pre class="log-box">{{ topText }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import client from '../api/client'
import SkeletonTable from '../components/SkeletonTable.vue'

const servers = ref([])
const serverId = ref(null)
const containers = ref([])
const stats = ref([])
const tab = ref('containers')
const acting = ref('')
const images = ref([])
const networks = ref([])
const volumes = ref([])
const loading = ref(false)
const logsVisible = ref(false)
const logs = ref('')
const logTail = ref(300)
const inspectVisible = ref(false)
const inspectText = ref('')
const topVisible = ref(false)
const topText = ref('')

async function loadServers() {
  servers.value = (await client.get('/api/servers')).data
  if (!serverId.value && servers.value[0]) serverId.value = servers.value[0].id
}

function containerStatusType(s) {
  var st = s.toLowerCase()
  if (st.indexOf('up') === 0 || st.indexOf('healthy') >= 0) return 'success'
  if (st.indexOf('exited') >= 0) return 'info'
  if (st.indexOf('paused') >= 0) return 'warning'
  return 'info'
}

async function loadAll() {
  if (!serverId.value) return
  loading.value = true
  try {
    if (tab.value === 'containers') {
      containers.value = (await client.get('/api/docker/' + serverId.value + '/containers')).data
      await loadStats()
    } else if (tab.value === 'images') {
      images.value = (await client.get('/api/docker/' + serverId.value + '/images')).data
    } else if (tab.value === 'networks') {
      networks.value = (await client.get('/api/docker/' + serverId.value + '/networks')).data
    } else if (tab.value === 'volumes') {
      volumes.value = (await client.get('/api/docker/' + serverId.value + '/volumes')).data
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取失败')
  } finally {
    loading.value = false
  }
}

async function loadContainers() {
  if (!serverId.value) return
  loading.value = true
  try {
    containers.value = (await client.get('/api/docker/' + serverId.value + '/containers')).data
    await loadStats()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取容器失败')
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  if (!serverId.value) return
  try {
    stats.value = (await client.get('/api/docker/' + serverId.value + '/containers/stats')).data
  } catch {
    stats.value = []
  }
}

function containerStats(row) {
  return stats.value.find(function(item) {
    return item.id === row.id || item.name === row.name
  }) || {}
}

async function action(row, type) {
  acting.value = row.id + '-' + type
  try {
    await client.post('/api/docker/' + serverId.value + '/containers/' + row.id + '/' + type)
    ElMessage.success(type + ' 已执行')
    loadContainers()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '操作失败')
  } finally {
    acting.value = ''
  }
}

async function showLogs(row) {
  try {
    logs.value = (await client.get(`/api/docker/${serverId.value}/containers/${row.id}/logs`, {
      params: { tail: logTail.value }
    })).data.logs
    logsVisible.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取日志失败')
  }
}

async function showInspect(row) {
  try {
    const data = (await client.get(`/api/docker/${serverId.value}/containers/${row.id}/inspect`)).data
    inspectText.value = JSON.stringify(data, null, 2)
    inspectVisible.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取 Inspect 失败')
  }
}

async function showTop(row) {
  try {
    const data = (await client.get(`/api/docker/${serverId.value}/containers/${row.id}/top`)).data
    topText.value = data.raw || [data.header].concat(data.rows || []).join('\n')
    topVisible.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取容器进程失败')
  }
}

onMounted(async () => {
  await loadServers()
  if (serverId.value) {
    containers.value = (await client.get('/api/docker/' + serverId.value + '/containers')).data
    await loadStats()
  }
})
</script>
