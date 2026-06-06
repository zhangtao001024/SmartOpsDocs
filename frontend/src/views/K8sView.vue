<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">Kubernetes</h2>
      <el-button type="primary" icon="Plus" @click="dialogVisible = true">接入集群</el-button>
    </div>
    <div class="panel k8s-grid">
      <div class="cluster-pane">
        <el-select v-model="clusterId" placeholder="选择集群" style="width: 100%" @change="loadNamespaces">
          <el-option v-for="cluster in clusters" :key="cluster.id" :label="cluster.name" :value="cluster.id" />
        </el-select>
        <div v-if="clusterId" style="margin-top: 8px; text-align: center">
          <el-popconfirm title="确定删除这个集群？" confirm-button-text="删除" @confirm="deleteCluster">
            <template #reference>
              <el-button size="small" type="danger" icon="Delete">删除当前集群</el-button>
            </template>
          </el-popconfirm>
        </div>
        <el-divider />
        <el-menu :default-active="namespace" @select="selectNamespace">
          <el-menu-item v-for="ns in namespaces" :key="ns" :index="ns">{{ ns }}</el-menu-item>
        </el-menu>
      </div>
      <div class="resource-pane">
        <div class="toolbar">
          <span class="muted">{{ resourceLabel }} {{ namespace ? '/ ' + namespace : '' }}</span>
          <el-select v-model="resource" placeholder="资源类型" style="width: 130px" @change="loadPods">
            <el-option label="Nodes" value="nodes" />
            <el-option label="Pods" value="pods" />
            <el-option label="Deployments" value="deployments" />
            <el-option label="StatefulSets" value="statefulsets" />
            <el-option label="DaemonSets" value="daemonsets" />
            <el-option label="Services" value="services" />
            <el-option label="Ingresses" value="ingresses" />
            <el-option label="Jobs" value="jobs" />
            <el-option label="Events" value="events" />
          </el-select>
          <el-button icon="Refresh" @click="loadPods">刷新</el-button>
        </div>

        <el-empty v-if="!clusterId" description="请先选择或接入一个 K8s 集群" />
        <template v-else>
        <SkeletonTable v-if="loading && pods.length === 0 && deployments.length === 0 && servicesList.length === 0 && events.length === 0" :rows="5" :cols="4" />
        <el-table v-if="resource === 'nodes'" :data="nodes" v-loading="loading">
          <el-table-column prop="name" label="节点" />
          <el-table-column prop="ready" label="Ready" width="90">
            <template #default="{ row }">
              <el-tag :type="row.ready ? 'success' : 'danger'" size="small">{{ row.ready ? 'Ready' : 'NotReady' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="roles" label="角色" width="140" />
          <el-table-column prop="internal_ip" label="内网 IP" width="140" />
          <el-table-column prop="version" label="版本" width="140" />
          <el-table-column prop="cpu" label="CPU" width="90" />
          <el-table-column prop="memory" label="内存" width="130" />
        </el-table>

        <el-table v-if="resource === 'pods'" :data="pods" v-loading="loading">
          <el-table-column prop="namespace" label="命名空间" width="150" />
          <el-table-column prop="name" label="Pod" />
          <el-table-column prop="status" label="状态" width="100">
            <template #default="{ row }">
              <el-tag :type="podStatusType(row.status)" size="small">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="node" label="节点" />
          <el-table-column prop="restarts" label="重启" width="80" />
          <el-table-column label="操作" width="230">
            <template #default="{ row }">
              <el-button size="small" @click="showDescribe(row)">Describe</el-button>
              <el-button size="small" @click="showLogs(row)">日志</el-button>
              <el-button size="small" @click="showJson(row)">JSON</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-table :data="deployments" v-loading="loading" v-if="resource === 'deployments'">
          <el-table-column prop="namespace" label="命名空间" width="150" />
          <el-table-column prop="name" label="Deployment" />
          <el-table-column prop="replicas" label="副本" width="100" />
          <el-table-column prop="created_at" label="创建时间" width="200" />
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button size="small" @click="restartDeployment(row)">重启</el-button>
              <el-button size="small" @click="scaleDeployment(row)">伸缩</el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-table :data="statefulsets" v-loading="loading" v-if="resource === 'statefulsets'">
          <el-table-column prop="namespace" label="命名空间" width="150" />
          <el-table-column prop="name" label="StatefulSet" />
          <el-table-column prop="replicas" label="副本" width="100" />
          <el-table-column prop="service_name" label="Service" />
          <el-table-column prop="created_at" label="创建时间" width="200" />
        </el-table>

        <el-table :data="daemonsets" v-loading="loading" v-if="resource === 'daemonsets'">
          <el-table-column prop="namespace" label="命名空间" width="150" />
          <el-table-column prop="name" label="DaemonSet" />
          <el-table-column prop="desired" label="期望" width="90" />
          <el-table-column prop="ready" label="Ready" width="90" />
          <el-table-column prop="available" label="Available" width="110" />
          <el-table-column prop="created_at" label="创建时间" width="200" />
        </el-table>

        <el-table :data="servicesList" v-loading="loading" v-if="resource === 'services'">
          <el-table-column prop="namespace" label="命名空间" width="150" />
          <el-table-column prop="name" label="Service" />
          <el-table-column prop="type" label="类型" width="100" />
          <el-table-column prop="cluster_ip" label="Cluster IP" width="150" />
          <el-table-column prop="ports" label="端口" />
        </el-table>

        <el-table :data="ingresses" v-loading="loading" v-if="resource === 'ingresses'">
          <el-table-column prop="namespace" label="命名空间" width="150" />
          <el-table-column prop="name" label="Ingress" />
          <el-table-column prop="class_name" label="Class" width="120" />
          <el-table-column prop="hosts" label="Hosts" />
          <el-table-column prop="address" label="Address" />
        </el-table>

        <el-table :data="jobs" v-loading="loading" v-if="resource === 'jobs'">
          <el-table-column prop="namespace" label="命名空间" width="150" />
          <el-table-column prop="name" label="Job" />
          <el-table-column prop="active" label="Active" width="90" />
          <el-table-column prop="succeeded" label="Succeeded" width="110" />
          <el-table-column prop="failed" label="Failed" width="90" />
          <el-table-column prop="created_at" label="创建时间" width="200" />
        </el-table>

        <el-table :data="events" v-loading="loading" v-if="resource === 'events'">
          <el-table-column prop="namespace" label="命名空间" width="140" />
          <el-table-column prop="type" label="类型" width="90">
            <template #default="{ row }">
              <el-tag :type="row.type === 'Warning' ? 'warning' : 'info'" size="small">{{ row.type }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="reason" label="原因" width="150" />
          <el-table-column prop="involved_object" label="对象" width="180" />
          <el-table-column prop="message" label="消息" />
          <el-table-column prop="count" label="次数" width="80" />
        </el-table>
        </template>
      </div>
    </div>

    <el-dialog v-model="dialogVisible" title="接入 K8s 集群" width="720px">
      <el-form :model="form" label-width="110px">
        <el-form-item label="集群名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="描述"><el-input v-model="form.description" /></el-form-item>
        <el-form-item label="KubeConfig"><el-input v-model="form.kubeconfig" type="textarea" :rows="12" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCluster">保存</el-button>
      </template>
    </el-dialog>
    <el-dialog v-model="logsVisible" title="Pod 日志" width="860px">
      <pre class="log-box">{{ logs }}</pre>
    </el-dialog>
    <el-dialog v-model="jsonVisible" title="Pod JSON" width="920px">
      <pre class="log-box">{{ resourceJson }}</pre>
    </el-dialog>
    <el-dialog v-model="describeVisible" title="Pod Describe" width="920px">
      <pre class="log-box">{{ describeText }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { computed } from 'vue'
import client from '../api/client'
import SkeletonTable from '../components/SkeletonTable.vue'

const clusters = ref([])
const clusterId = ref(null)
const namespaces = ref([])
const namespace = ref('')
const resource = ref('pods')
const pods = ref([])
const nodes = ref([])
const deployments = ref([])
const statefulsets = ref([])
const daemonsets = ref([])
const servicesList = ref([])
const ingresses = ref([])
const jobs = ref([])
const events = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const logsVisible = ref(false)
const jsonVisible = ref(false)
const describeVisible = ref(false)
const logs = ref('')
const resourceJson = ref('')
const describeText = ref('')
const form = reactive({ name: '', description: '', kubeconfig: '' })

async function loadClusters() {
  clusters.value = (await client.get('/api/k8s/clusters')).data
  if (!clusterId.value && clusters.value[0]) clusterId.value = clusters.value[0].id
}

async function loadNamespaces() {
  if (!clusterId.value) return
  try {
    namespaces.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/namespaces`)).data
    namespace.value = namespaces.value[0] || ''
    loadPods()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取命名空间失败')
  }
}

function selectNamespace(ns) {
  namespace.value = ns
  loadPods()
}

const resourceLabel = computed(() => {
  return {
    nodes: 'Node 列表',
    pods: 'Pod 列表',
    deployments: 'Deployment 列表',
    statefulsets: 'StatefulSet 列表',
    daemonsets: 'DaemonSet 列表',
    services: 'Service 列表',
    ingresses: 'Ingress 列表',
    jobs: 'Job 列表',
    events: 'Events',
  }[resource.value] || ''
})

function podStatusType(s) {
  if (s === 'Running') return 'success'
  if (s === 'Pending') return 'warning'
  if (s === 'Failed') return 'danger'
  return 'info'
}

async function loadPods() {
  if (!clusterId.value) return
  loading.value = true
  try {
    var params = { namespace: namespace.value }
    if (resource.value === 'nodes') {
      nodes.value = (await client.get('/api/k8s/clusters/' + clusterId.value + '/nodes')).data
    } else if (resource.value === 'pods') {
      pods.value = (await client.get('/api/k8s/clusters/' + clusterId.value + '/pods', { params: params })).data
    } else if (resource.value === 'deployments') {
      deployments.value = (await client.get('/api/k8s/clusters/' + clusterId.value + '/deployments', { params: params })).data
    } else if (resource.value === 'statefulsets') {
      statefulsets.value = (await client.get('/api/k8s/clusters/' + clusterId.value + '/statefulsets', { params: params })).data
    } else if (resource.value === 'daemonsets') {
      daemonsets.value = (await client.get('/api/k8s/clusters/' + clusterId.value + '/daemonsets', { params: params })).data
    } else if (resource.value === 'services') {
      servicesList.value = (await client.get('/api/k8s/clusters/' + clusterId.value + '/services', { params: params })).data
    } else if (resource.value === 'ingresses') {
      ingresses.value = (await client.get('/api/k8s/clusters/' + clusterId.value + '/ingresses', { params: params })).data
    } else if (resource.value === 'jobs') {
      jobs.value = (await client.get('/api/k8s/clusters/' + clusterId.value + '/jobs', { params: params })).data
    } else if (resource.value === 'events') {
      events.value = (await client.get('/api/k8s/clusters/' + clusterId.value + '/events', { params: params })).data
    }
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取失败')
  } finally {
    loading.value = false
  }
}

async function restartDeployment(row) {
  try {
    await ElMessageBox.confirm('确定重启 Deployment ' + row.namespace + '/' + row.name + '？', '确认重启', {
      type: 'warning',
      confirmButtonText: '重启',
      cancelButtonText: '取消',
    })
    await client.post(`/api/k8s/deployments/${row.name}/restart`, null, {
      params: { cluster_id: clusterId.value, namespace: row.namespace }
    })
    ElMessage.success('已触发滚动重启')
    await loadPods()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.response?.data?.detail || '重启失败')
    }
  }
}

async function scaleDeployment(row) {
  try {
    const result = await ElMessageBox.prompt('输入目标副本数（0-100）', '伸缩 Deployment', {
      inputValue: String((row.replicas || '1/1').split('/')[1] || 1),
      inputPattern: /^(100|[1-9]?\d)$/,
      inputErrorMessage: '请输入 0-100 的整数',
      confirmButtonText: '伸缩',
      cancelButtonText: '取消',
    })
    await client.post(`/api/k8s/deployments/${row.name}/scale`, { replicas: Number(result.value) }, {
      params: { cluster_id: clusterId.value, namespace: row.namespace }
    })
    ElMessage.success('副本数已更新')
    await loadPods()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.response?.data?.detail || '伸缩失败')
    }
  }
}

async function showJson(row) {
  try {
    const data = (await client.get(`/api/k8s/pods/${row.name}/json`, { params: { cluster_id: clusterId.value, namespace: row.namespace } })).data
    resourceJson.value = JSON.stringify(data, null, 2)
    jsonVisible.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取 Pod JSON 失败')
  }
}

async function showDescribe(row) {
  try {
    const data = (await client.get(`/api/k8s/pods/${row.name}/describe`, { params: { cluster_id: clusterId.value, namespace: row.namespace } })).data
    describeText.value = JSON.stringify(data, null, 2)
    describeVisible.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取 Pod Describe 失败')
  }
}

async function deleteCluster() {
  try {
    await client.delete(`/api/k8s/clusters/${clusterId.value}`)
    ElMessage.success('集群已删除')
    clusterId.value = null
    namespaces.value = []
    pods.value = []
    await loadClusters()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '删除集群失败')
  }
}

async function saveCluster() {
  try {
    await client.post('/api/k8s/clusters', form)
    Object.assign(form, { name: '', description: '', kubeconfig: '' })
    dialogVisible.value = false
    await loadClusters()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '保存集群失败')
  }
}

async function showLogs(row) {
  try {
    logs.value = (await client.get(`/api/k8s/pods/${row.name}/logs`, { params: { cluster_id: clusterId.value, namespace: row.namespace } })).data.logs
    logsVisible.value = true
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取 Pod 日志失败')
  }
}

onMounted(async () => {
  await loadClusters()
  await loadNamespaces()
})
</script>

<style scoped>
.k8s-grid {
  display: grid;
  grid-template-columns: 260px minmax(0, 1fr);
  gap: 18px;
}

.cluster-pane {
  min-width: 0;
  padding-right: 4px;
}

.cluster-pane :deep(.el-menu) {
  border-right: 0;
}

.cluster-pane :deep(.el-menu-item) {
  height: 36px;
  border-radius: var(--app-radius);
  font-weight: 600;
}

.cluster-pane :deep(.el-menu-item.is-active) {
  color: var(--app-primary);
  background: var(--app-primary-soft);
}

.resource-pane {
  min-width: 0;
}

@media (max-width: 900px) {
  .k8s-grid {
    grid-template-columns: 1fr;
  }
}
</style>
