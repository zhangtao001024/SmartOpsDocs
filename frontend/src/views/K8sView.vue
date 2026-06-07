<template>
  <main class="k8s-console">
    <header class="console-hero">
      <div class="page-heading">
        <p class="page-kicker">Cluster operations</p>
        <h2 class="page-title">Kubernetes 控制台</h2>
        <p class="page-subtitle">查看集群健康、资源状态和事件风险，支持常用工作负载操作与资源详情追踪。</p>
        <div class="console-status-strip">
          <span><strong>{{ clusters.length }}</strong> 集群</span>
          <span><strong>{{ namespaceLabel }}</strong> 命名空间</span>
          <span><strong>{{ resourceMeta.label }}</strong> 当前资源</span>
          <span><strong>{{ autoRefresh ? '15s' : '手动' }}</strong> 刷新</span>
        </div>
      </div>
      <div class="header-actions">
        <el-select v-model="clusterId" class="cluster-select" placeholder="选择集群" @change="handleClusterChange">
          <el-option v-for="cluster in clusters" :key="cluster.id" :label="cluster.name" :value="cluster.id" />
        </el-select>
        <el-button icon="Plus" type="primary" @click="dialogVisible = true">接入集群</el-button>
      </div>
    </header>

    <section class="panel k8s-workbench">
      <aside class="k8s-sidebar" aria-label="Kubernetes navigation">
        <div class="cluster-card">
          <span class="eyebrow">当前集群</span>
          <strong>{{ activeCluster?.name || '未选择集群' }}</strong>
          <small>{{ activeCluster?.description || '选择一个集群后查看资源状态' }}</small>
          <el-popconfirm v-if="clusterId" title="确定删除这个集群？" confirm-button-text="删除" @confirm="deleteCluster">
            <template #reference>
              <el-button class="delete-cluster" size="small" type="danger" icon="Delete" text>删除集群</el-button>
            </template>
          </el-popconfirm>
        </div>

        <div class="nav-block">
          <div class="nav-heading">
            <span>Namespace</span>
            <el-tag size="small" type="info">{{ namespaces.length }}</el-tag>
          </div>
          <button class="nav-row" :class="{ active: namespace === '' }" type="button" @click="selectNamespace('')">
            <span>全部命名空间</span>
          </button>
          <div class="namespace-list">
            <button
              v-for="ns in namespaces"
              :key="ns"
              class="nav-row"
              :class="{ active: namespace === ns }"
              type="button"
              @click="selectNamespace(ns)"
            >
              <span>{{ ns }}</span>
            </button>
          </div>
        </div>

        <div class="nav-block">
          <div class="nav-heading">
            <span>Resources</span>
          </div>
          <button
            v-for="item in resourceCatalog"
            :key="item.key"
            class="resource-row"
            :class="{ active: resource === item.key }"
            type="button"
            @click="selectResourceType(item.key)"
          >
            <span class="resource-icon">
              <el-icon><component :is="item.icon" /></el-icon>
            </span>
            <span>{{ item.label }}</span>
            <strong>{{ resourceCount(item.key) }}</strong>
          </button>
        </div>
      </aside>

      <section class="k8s-content">
        <div class="ops-bar">
          <div>
            <h3>{{ resourceMeta.label }}</h3>
            <p>{{ namespaceLabel }} · {{ resourceMeta.description }}</p>
          </div>
          <div class="ops-actions">
            <el-input
              v-if="resource !== 'overview'"
              v-model="query"
              class="resource-search"
              clearable
              :prefix-icon="Search"
              placeholder="搜索名称、节点、消息"
            />
            <el-select
              v-if="resource !== 'overview' && statusOptions.length"
              v-model="statusFilter"
              class="status-filter"
              clearable
              placeholder="状态"
            >
              <el-option v-for="option in statusOptions" :key="option" :label="option" :value="option" />
            </el-select>
            <el-switch v-model="autoRefresh" active-text="自动刷新" />
            <el-button icon="Refresh" :loading="loading" @click="loadResources">刷新</el-button>
          </div>
        </div>

        <el-empty v-if="!clusterId" description="请先选择或接入一个 K8s 集群" />

        <template v-else>
          <section v-if="resource === 'overview'" class="overview-grid" v-loading="loading">
            <article v-for="item in overviewCards" :key="item.label" class="summary-card" :class="item.tone">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
              <small>{{ item.hint }}</small>
            </article>
          </section>

          <section v-if="resource === 'overview'" class="ops-focus">
            <div class="focus-row">
              <span>Warning events</span>
              <strong>{{ overview.warnings ?? '-' }}</strong>
              <small>优先处理 Warning 类型事件和重启次数异常的 Pod</small>
            </div>
            <div class="focus-row">
              <span>Pending / Failed pods</span>
              <strong>{{ pendingFailedPods }}</strong>
              <small>调度失败、镜像拉取失败、OOM 会集中体现在这里</small>
            </div>
            <div class="focus-row">
              <span>Node readiness</span>
              <strong>{{ nodeReadiness }}</strong>
              <small>节点不可用时先查 kubelet、网络和磁盘压力</small>
            </div>
          </section>

          <SkeletonTable v-if="showSkeleton" :rows="6" :cols="5" />

          <template v-if="resource === 'nodes' && !showSkeleton">
            <el-table :data="filteredRows" v-loading="loading" row-key="name" :row-class-name="tableRowClassName" @row-click="selectRow">
              <el-table-column prop="name" label="节点" min-width="220" show-overflow-tooltip />
              <el-table-column prop="ready" label="Ready" width="100">
                <template #default="{ row }">
                  <el-tag :type="row.ready ? 'success' : 'danger'" size="small">{{ row.ready ? 'Ready' : 'NotReady' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="roles" label="角色" width="150" show-overflow-tooltip />
              <el-table-column prop="internal_ip" label="内网 IP" width="150" />
              <el-table-column prop="version" label="版本" width="150" />
              <el-table-column prop="cpu" label="CPU" width="90" />
              <el-table-column prop="memory" label="内存" width="130" />
              <el-table-column label="操作" width="120" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click.stop="showRowJson(row, 'nodes')">JSON</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="resource === 'pods' && !showSkeleton">
            <el-table :data="filteredRows" v-loading="loading" :row-key="resourceRowKey" :row-class-name="tableRowClassName" @row-click="selectRow">
              <el-table-column prop="namespace" label="命名空间" width="150" show-overflow-tooltip />
              <el-table-column prop="name" label="Pod" min-width="260" show-overflow-tooltip />
              <el-table-column prop="status" label="状态" width="115">
                <template #default="{ row }">
                  <el-tag :type="podStatusType(row.status)" size="small">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="node" label="节点" min-width="180" show-overflow-tooltip />
              <el-table-column prop="restarts" label="重启" width="80" />
              <el-table-column prop="created_at" label="创建时间" width="200" />
              <el-table-column label="操作" width="270" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click.stop="showDescribe(row)">Describe</el-button>
                  <el-button size="small" @click.stop="showLogs(row)">日志</el-button>
                  <el-button size="small" @click.stop="showRowJson(row, 'pods')">JSON</el-button>
                  <el-button size="small" type="danger" text @click.stop="deletePod(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="resource === 'deployments' && !showSkeleton">
            <el-table :data="filteredRows" v-loading="loading" :row-key="resourceRowKey" :row-class-name="tableRowClassName" @row-click="selectRow">
              <el-table-column prop="namespace" label="命名空间" width="150" show-overflow-tooltip />
              <el-table-column prop="name" label="Deployment" min-width="240" show-overflow-tooltip />
              <el-table-column prop="replicas" label="副本" width="100" />
              <el-table-column prop="created_at" label="创建时间" width="200" />
              <el-table-column label="状态" width="110">
                <template #default="{ row }">
                  <el-tag :type="rowState(row, 'deployments') === 'Ready' ? 'success' : 'warning'" size="small">{{ rowState(row, 'deployments') }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="230" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click.stop="restartDeployment(row)">重启</el-button>
                  <el-button size="small" @click.stop="scaleDeployment(row)">伸缩</el-button>
                  <el-button size="small" @click.stop="showRowJson(row, 'deployments')">JSON</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="resource === 'statefulsets' && !showSkeleton">
            <el-table :data="filteredRows" v-loading="loading" :row-key="resourceRowKey" :row-class-name="tableRowClassName" @row-click="selectRow">
              <el-table-column prop="namespace" label="命名空间" width="150" show-overflow-tooltip />
              <el-table-column prop="name" label="StatefulSet" min-width="240" show-overflow-tooltip />
              <el-table-column prop="replicas" label="副本" width="100" />
              <el-table-column prop="service_name" label="Service" min-width="180" show-overflow-tooltip />
              <el-table-column prop="created_at" label="创建时间" width="200" />
              <el-table-column label="操作" width="230" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click.stop="restartWorkload(row, 'statefulset')">重启</el-button>
                  <el-button size="small" @click.stop="scaleWorkload(row, 'statefulset')">伸缩</el-button>
                  <el-button size="small" @click.stop="showRowJson(row, 'statefulsets')">JSON</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="resource === 'daemonsets' && !showSkeleton">
            <el-table :data="filteredRows" v-loading="loading" :row-key="resourceRowKey" :row-class-name="tableRowClassName" @row-click="selectRow">
              <el-table-column prop="namespace" label="命名空间" width="150" show-overflow-tooltip />
              <el-table-column prop="name" label="DaemonSet" min-width="240" show-overflow-tooltip />
              <el-table-column prop="desired" label="期望" width="90" />
              <el-table-column prop="ready" label="Ready" width="90" />
              <el-table-column prop="available" label="Available" width="110" />
              <el-table-column prop="created_at" label="创建时间" width="200" />
              <el-table-column label="操作" width="180" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click.stop="restartWorkload(row, 'daemonset')">重启</el-button>
                  <el-button size="small" @click.stop="showRowJson(row, 'daemonsets')">JSON</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="resource === 'services' && !showSkeleton">
            <el-table :data="filteredRows" v-loading="loading" :row-key="resourceRowKey" :row-class-name="tableRowClassName" @row-click="selectRow">
              <el-table-column prop="namespace" label="命名空间" width="150" show-overflow-tooltip />
              <el-table-column prop="name" label="Service" min-width="230" show-overflow-tooltip />
              <el-table-column prop="type" label="类型" width="120" />
              <el-table-column prop="cluster_ip" label="Cluster IP" width="150" />
              <el-table-column prop="ports" label="端口" min-width="220" show-overflow-tooltip />
              <el-table-column label="操作" width="120" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click.stop="showRowJson(row, 'services')">JSON</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="resource === 'ingresses' && !showSkeleton">
            <el-table :data="filteredRows" v-loading="loading" :row-key="resourceRowKey" :row-class-name="tableRowClassName" @row-click="selectRow">
              <el-table-column prop="namespace" label="命名空间" width="150" show-overflow-tooltip />
              <el-table-column prop="name" label="Ingress" min-width="230" show-overflow-tooltip />
              <el-table-column prop="class_name" label="Class" width="130" show-overflow-tooltip />
              <el-table-column prop="hosts" label="Hosts" min-width="220" show-overflow-tooltip />
              <el-table-column prop="address" label="Address" min-width="180" show-overflow-tooltip />
              <el-table-column label="操作" width="120" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click.stop="showRowJson(row, 'ingresses')">JSON</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="resource === 'jobs' && !showSkeleton">
            <el-table :data="filteredRows" v-loading="loading" :row-key="resourceRowKey" :row-class-name="tableRowClassName" @row-click="selectRow">
              <el-table-column prop="namespace" label="命名空间" width="150" show-overflow-tooltip />
              <el-table-column prop="name" label="Job" min-width="240" show-overflow-tooltip />
              <el-table-column prop="active" label="Active" width="90" />
              <el-table-column prop="succeeded" label="Succeeded" width="110" />
              <el-table-column prop="failed" label="Failed" width="90" />
              <el-table-column prop="created_at" label="创建时间" width="200" />
              <el-table-column label="操作" width="120" fixed="right">
                <template #default="{ row }">
                  <el-button size="small" @click.stop="showRowJson(row, 'jobs')">JSON</el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <template v-if="resource === 'events' && !showSkeleton">
            <el-table :data="filteredRows" v-loading="loading" :row-key="resourceRowKey" :row-class-name="tableRowClassName" @row-click="selectRow">
              <el-table-column prop="namespace" label="命名空间" width="140" show-overflow-tooltip />
              <el-table-column prop="type" label="类型" width="95">
                <template #default="{ row }">
                  <el-tag :type="row.type === 'Warning' ? 'warning' : 'info'" size="small">{{ row.type || 'Normal' }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="reason" label="原因" width="160" show-overflow-tooltip />
              <el-table-column prop="involved_object" label="对象" width="210" show-overflow-tooltip />
              <el-table-column prop="message" label="消息" min-width="360" show-overflow-tooltip />
              <el-table-column prop="count" label="次数" width="80" />
              <el-table-column prop="last_time" label="最后发生" width="200" />
            </el-table>
          </template>

          <el-empty v-if="showEmptyRows" description="没有匹配的资源" />
        </template>
      </section>

      <aside class="resource-detail" :class="{ empty: !selectedResource }" aria-label="Resource details">
        <template v-if="selectedResource">
          <div class="detail-heading">
            <div>
              <span class="eyebrow">{{ selectedKindLabel }}</span>
              <h3>{{ selectedResource.name || selectedResource.involved_object }}</h3>
              <p>{{ selectedResource.namespace || 'cluster scope' }}</p>
            </div>
            <el-button icon="Close" text @click="selectedResource = null" />
          </div>

          <div class="detail-status">
            <span>状态</span>
            <el-tag :type="selectedStatusType" size="small">{{ rowState(selectedResource, selectedKind) }}</el-tag>
          </div>

          <dl class="detail-list">
            <template v-for="field in detailFields" :key="field.label">
              <dt>{{ field.label }}</dt>
              <dd>{{ field.value || '-' }}</dd>
            </template>
          </dl>

          <div class="detail-actions">
            <el-button v-if="selectedKind === 'pods'" size="small" @click="showDescribe(selectedResource)">Describe</el-button>
            <el-button v-if="selectedKind === 'pods'" size="small" @click="showLogs(selectedResource)">日志</el-button>
            <el-button v-if="selectedCanLoadJson" size="small" @click="showRowJson(selectedResource, selectedKind)">JSON</el-button>
            <el-button v-if="selectedKind === 'deployments'" size="small" @click="restartDeployment(selectedResource)">重启</el-button>
            <el-button v-if="selectedKind === 'deployments'" size="small" @click="scaleDeployment(selectedResource)">伸缩</el-button>
            <el-button v-if="selectedKind === 'statefulsets'" size="small" @click="restartWorkload(selectedResource, 'statefulset')">重启</el-button>
            <el-button v-if="selectedKind === 'statefulsets'" size="small" @click="scaleWorkload(selectedResource, 'statefulset')">伸缩</el-button>
            <el-button v-if="selectedKind === 'daemonsets'" size="small" @click="restartWorkload(selectedResource, 'daemonset')">重启</el-button>
            <el-button v-if="selectedKind === 'pods'" size="small" type="danger" text @click="deletePod(selectedResource)">删除</el-button>
          </div>
        </template>

        <template v-else>
          <div class="empty-detail">
            <el-icon><View /></el-icon>
            <strong>选择一个资源</strong>
            <span>点击表格行后在这里查看摘要和常用操作</span>
          </div>
        </template>
      </aside>
    </section>

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

    <el-dialog v-model="logsVisible" :title="logsTitle" width="920px">
      <pre class="log-box">{{ logs }}</pre>
    </el-dialog>

    <el-dialog v-model="jsonVisible" :title="jsonTitle" width="960px">
      <pre class="log-box">{{ resourceJson }}</pre>
    </el-dialog>

    <el-dialog v-model="describeVisible" title="Pod Describe" width="960px">
      <pre class="log-box">{{ describeText }}</pre>
    </el-dialog>
  </main>
</template>

<script setup>
import { Close, Search, View } from '@element-plus/icons-vue'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import client, { getApiErrorMessage } from '../api/client'
import SkeletonTable from '../components/SkeletonTable.vue'

const resourceCatalog = [
  { key: 'overview', label: 'Overview', icon: 'DataBoard', description: '集群健康、规模和风险焦点' },
  { key: 'nodes', label: 'Nodes', icon: 'Cpu', description: '节点可用性、角色和容量' },
  { key: 'pods', label: 'Pods', icon: 'Box', description: '运行状态、节点分布和重启情况' },
  { key: 'deployments', label: 'Deployments', icon: 'Grid', description: '无状态工作负载和副本状态' },
  { key: 'statefulsets', label: 'StatefulSets', icon: 'Connection', description: '有状态工作负载和稳定标识' },
  { key: 'daemonsets', label: 'DaemonSets', icon: 'Share', description: '节点守护进程覆盖情况' },
  { key: 'services', label: 'Services', icon: 'Operation', description: '服务发现、类型和端口暴露' },
  { key: 'ingresses', label: 'Ingresses', icon: 'TrendCharts', description: '入口规则、域名和地址' },
  { key: 'jobs', label: 'Jobs', icon: 'Tickets', description: '一次性任务执行状态' },
  { key: 'events', label: 'Events', icon: 'WarningFilled', description: '按时间倒序查看集群事件' },
]

const resourceKindMap = {
  pods: 'pod',
  nodes: 'node',
  deployments: 'deployment',
  statefulsets: 'statefulset',
  daemonsets: 'daemonset',
  services: 'service',
  ingresses: 'ingress',
  jobs: 'job',
}

const clusters = ref([])
const clusterId = ref(null)
const namespaces = ref([])
const namespace = ref('')
const resource = ref('overview')
const query = ref('')
const statusFilter = ref('')
const autoRefresh = ref(false)

const overview = ref({})
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

const selectedResource = ref(null)
const selectedKind = ref('')
const dialogVisible = ref(false)
const logsVisible = ref(false)
const jsonVisible = ref(false)
const describeVisible = ref(false)
const logs = ref('')
const logsTitle = ref('Pod 日志')
const resourceJson = ref('')
const jsonTitle = ref('资源 JSON')
const describeText = ref('')
const form = reactive({ name: '', description: '', kubeconfig: '' })
let refreshTimer = null

const activeCluster = computed(() => clusters.value.find((cluster) => cluster.id === clusterId.value))
const resourceMeta = computed(() => resourceCatalog.find((item) => item.key === resource.value) || resourceCatalog[0])
const namespaceLabel = computed(() => namespace.value || '全部命名空间')
const selectedKindLabel = computed(() => resourceCatalog.find((item) => item.key === selectedKind.value)?.label || 'Resource')
const selectedCanLoadJson = computed(() => Boolean(resourceKindMap[selectedKind.value]))

const resourceRows = computed(() => {
  return {
    nodes: nodes.value,
    pods: pods.value,
    deployments: deployments.value,
    statefulsets: statefulsets.value,
    daemonsets: daemonsets.value,
    services: servicesList.value,
    ingresses: ingresses.value,
    jobs: jobs.value,
    events: events.value,
  }[resource.value] || []
})

const filteredRows = computed(() => {
  const text = query.value.trim().toLowerCase()
  return resourceRows.value.filter((row) => {
    const matchesText = !text || rowSearchText(row).includes(text)
    const matchesStatus = !statusFilter.value || rowState(row, resource.value) === statusFilter.value
    return matchesText && matchesStatus
  })
})

const statusOptions = computed(() => {
  const values = resourceRows.value.map((row) => rowState(row, resource.value)).filter(Boolean)
  return Array.from(new Set(values))
})

const showSkeleton = computed(() => loading.value && resource.value !== 'overview' && resourceRows.value.length === 0)
const showEmptyRows = computed(() => clusterId.value && resource.value !== 'overview' && !loading.value && filteredRows.value.length === 0)

const pendingFailedPods = computed(() => {
  const pending = overview.value.pods?.pending ?? '-'
  const failed = overview.value.pods?.failed ?? '-'
  return `${pending} / ${failed}`
})

const nodeReadiness = computed(() => {
  const ready = overview.value.nodes?.ready ?? '-'
  const total = overview.value.nodes?.total ?? '-'
  return `${ready} / ${total}`
})

const overviewCards = computed(() => [
  {
    label: '节点',
    value: nodeReadiness.value,
    hint: 'Ready / Total',
    tone: overview.value.nodes?.ready === overview.value.nodes?.total ? 'good' : 'warn',
  },
  {
    label: 'Pod',
    value: `${overview.value.pods?.running ?? '-'}/${overview.value.pods?.total ?? '-'}`,
    hint: 'Running / Total',
    tone: (overview.value.pods?.failed || 0) > 0 ? 'danger' : 'good',
  },
  { label: 'Deployments', value: overview.value.deployments ?? '-', hint: '无状态工作负载', tone: '' },
  { label: 'Services', value: overview.value.services ?? '-', hint: '服务发现入口', tone: '' },
  { label: 'Ingresses', value: overview.value.ingresses ?? '-', hint: '外部访问规则', tone: '' },
  { label: 'Jobs', value: overview.value.jobs ?? '-', hint: '批处理任务', tone: '' },
  { label: 'Namespaces', value: overview.value.namespaces ?? '-', hint: '隔离域数量', tone: '' },
  {
    label: 'Warning events',
    value: overview.value.warnings ?? '-',
    hint: '最近 Warning 事件',
    tone: (overview.value.warnings || 0) > 0 ? 'warn' : 'good',
  },
])

const detailFields = computed(() => {
  if (!selectedResource.value) return []
  const row = selectedResource.value
  const common = [
    { label: 'Namespace', value: row.namespace || 'cluster scope' },
    { label: 'Name', value: row.name || row.involved_object },
  ]
  const fields = {
    nodes: [
      { label: 'Internal IP', value: row.internal_ip },
      { label: 'Roles', value: row.roles },
      { label: 'Version', value: row.version },
      { label: 'CPU', value: row.cpu },
      { label: 'Memory', value: row.memory },
      { label: 'Created', value: row.created_at },
    ],
    pods: [
      { label: 'Node', value: row.node },
      { label: 'Restarts', value: row.restarts },
      { label: 'Created', value: row.created_at },
    ],
    deployments: [
      { label: 'Replicas', value: row.replicas },
      { label: 'Available', value: row.available },
      { label: 'Created', value: row.created_at },
    ],
    statefulsets: [
      { label: 'Replicas', value: row.replicas },
      { label: 'Service', value: row.service_name },
      { label: 'Created', value: row.created_at },
    ],
    daemonsets: [
      { label: 'Desired', value: row.desired },
      { label: 'Ready', value: row.ready },
      { label: 'Available', value: row.available },
      { label: 'Created', value: row.created_at },
    ],
    services: [
      { label: 'Type', value: row.type },
      { label: 'Cluster IP', value: row.cluster_ip },
      { label: 'Ports', value: row.ports },
    ],
    ingresses: [
      { label: 'Class', value: row.class_name },
      { label: 'Hosts', value: row.hosts },
      { label: 'Address', value: row.address },
      { label: 'Created', value: row.created_at },
    ],
    jobs: [
      { label: 'Active', value: row.active },
      { label: 'Succeeded', value: row.succeeded },
      { label: 'Failed', value: row.failed },
      { label: 'Created', value: row.created_at },
    ],
    events: [
      { label: 'Type', value: row.type },
      { label: 'Reason', value: row.reason },
      { label: 'Object', value: row.involved_object },
      { label: 'Message', value: row.message },
      { label: 'Count', value: row.count },
      { label: 'Last time', value: row.last_time },
    ],
  }
  return [...common, ...(fields[selectedKind.value] || [])]
})

const selectedStatusType = computed(() => {
  if (!selectedResource.value) return 'info'
  const state = rowState(selectedResource.value, selectedKind.value)
  if (['Ready', 'Running', 'Succeeded', 'ClusterIP', 'LoadBalancer', 'Routed'].includes(state)) return 'success'
  if (['Failed', 'NotReady'].includes(state)) return 'danger'
  if (['Warning', 'Pending', 'Degraded', 'Active'].includes(state)) return 'warning'
  return 'info'
})

async function loadClusters() {
  clusters.value = (await client.get('/api/k8s/clusters')).data
  if (!clusterId.value && clusters.value[0]) clusterId.value = clusters.value[0].id
}

async function handleClusterChange() {
  selectedResource.value = null
  namespace.value = ''
  await loadNamespaces()
  setupAutoRefresh()
}

async function loadNamespaces() {
  if (!clusterId.value) return
  try {
    namespaces.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/namespaces`)).data
    if (namespace.value && !namespaces.value.includes(namespace.value)) namespace.value = ''
    await loadResources()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取命名空间失败'))
  }
}

function selectNamespace(ns) {
  if (namespace.value === ns) return
  namespace.value = ns
  selectedResource.value = null
  loadResources()
}

function selectResourceType(key) {
  if (resource.value === key) return
  resource.value = key
}

watch(resource, () => {
  query.value = ''
  statusFilter.value = ''
  selectedResource.value = null
  loadResources()
})

watch(autoRefresh, setupAutoRefresh)

function requestParams() {
  const params = {}
  if (namespace.value) params.namespace = namespace.value
  return params
}

async function loadResources() {
  if (!clusterId.value) return
  loading.value = true
  try {
    const params = requestParams()
    if (resource.value === 'overview') {
      overview.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/overview`)).data
    } else if (resource.value === 'nodes') {
      nodes.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/nodes`)).data
    } else if (resource.value === 'pods') {
      pods.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/pods`, { params })).data
    } else if (resource.value === 'deployments') {
      deployments.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/deployments`, { params })).data
    } else if (resource.value === 'statefulsets') {
      statefulsets.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/statefulsets`, { params })).data
    } else if (resource.value === 'daemonsets') {
      daemonsets.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/daemonsets`, { params })).data
    } else if (resource.value === 'services') {
      servicesList.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/services`, { params })).data
    } else if (resource.value === 'ingresses') {
      ingresses.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/ingresses`, { params })).data
    } else if (resource.value === 'jobs') {
      jobs.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/jobs`, { params })).data
    } else if (resource.value === 'events') {
      events.value = (await client.get(`/api/k8s/clusters/${clusterId.value}/events`, { params })).data
    }
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取失败'))
  } finally {
    loading.value = false
  }
}

function resourceCount(key) {
  const counts = {
    overview: overview.value.namespaces ? 'ok' : '-',
    nodes: overview.value.nodes?.total ?? nodes.value.length,
    pods: overview.value.pods?.total ?? pods.value.length,
    deployments: overview.value.deployments ?? deployments.value.length,
    statefulsets: statefulsets.value.length || '-',
    daemonsets: daemonsets.value.length || '-',
    services: overview.value.services ?? servicesList.value.length,
    ingresses: overview.value.ingresses ?? ingresses.value.length,
    jobs: overview.value.jobs ?? jobs.value.length,
    events: overview.value.warnings ?? events.value.length,
  }
  return counts[key] ?? '-'
}

function rowSearchText(row) {
  return Object.values(row).join(' ').toLowerCase()
}

function rowState(row, kind = resource.value) {
  if (!row) return ''
  if (kind === 'events') return row.type || 'Normal'
  if (kind === 'nodes') return row.ready ? 'Ready' : 'NotReady'
  if (kind === 'pods') return row.status || 'Unknown'
  if (kind === 'deployments' || kind === 'statefulsets') {
    return replicasReady(row.replicas) ? 'Ready' : 'Degraded'
  }
  if (kind === 'daemonsets') {
    return Number(row.ready || 0) >= Number(row.desired || 0) ? 'Ready' : 'Degraded'
  }
  if (kind === 'jobs') {
    if (Number(row.failed || 0) > 0) return 'Failed'
    if (Number(row.active || 0) > 0) return 'Active'
    if (Number(row.succeeded || 0) > 0) return 'Succeeded'
    return 'Idle'
  }
  if (kind === 'ingresses') return row.address ? 'Routed' : 'Pending'
  if (kind === 'services') return row.type || 'Service'
  return 'Resource'
}

function replicasReady(value) {
  const [ready, desired] = String(value || '0/0').split('/').map((item) => Number(item))
  return Number.isFinite(ready) && Number.isFinite(desired) && ready >= desired
}

function podStatusType(status) {
  if (status === 'Running') return 'success'
  if (status === 'Pending') return 'warning'
  if (status === 'Failed') return 'danger'
  return 'info'
}

function resourceRowKey(row) {
  return `${row.namespace || 'cluster'}/${row.name || row.involved_object || row.reason || row.last_time}`
}

function isSelectedRow(row) {
  if (!selectedResource.value || selectedKind.value !== resource.value) return false
  return resourceRowKey(row) === resourceRowKey(selectedResource.value)
}

function tableRowClassName({ row }) {
  return isSelectedRow(row) ? 'is-selected-row' : ''
}

function selectRow(row) {
  selectedKind.value = resource.value
  selectedResource.value = { ...row }
}

async function restartDeployment(row) {
  try {
    await ElMessageBox.confirm(`确定重启 Deployment ${row.namespace}/${row.name}？`, '确认重启', {
      type: 'warning',
      confirmButtonText: '重启',
      cancelButtonText: '取消',
    })
    await client.post(`/api/k8s/deployments/${row.name}/restart`, null, {
      params: { cluster_id: clusterId.value, namespace: row.namespace },
    })
    ElMessage.success('已触发滚动重启')
    await loadResources()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '重启失败'))
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
      params: { cluster_id: clusterId.value, namespace: row.namespace },
    })
    ElMessage.success('副本数已更新')
    await loadResources()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '伸缩失败'))
    }
  }
}

async function restartWorkload(row, kind) {
  try {
    await ElMessageBox.confirm(`确定重启 ${kind} ${row.namespace}/${row.name}？`, '确认重启', {
      type: 'warning',
      confirmButtonText: '重启',
      cancelButtonText: '取消',
    })
    await client.post(`/api/k8s/workloads/${row.name}/restart`, { kind }, {
      params: { cluster_id: clusterId.value, namespace: row.namespace },
    })
    ElMessage.success('已触发滚动重启')
    await loadResources()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '重启失败'))
    }
  }
}

async function scaleWorkload(row, kind) {
  try {
    const result = await ElMessageBox.prompt('输入目标副本数（0-100）', `伸缩 ${kind}`, {
      inputValue: String((row.replicas || '1/1').split('/')[1] || 1),
      inputPattern: /^(100|[1-9]?\d)$/,
      inputErrorMessage: '请输入 0-100 的整数',
      confirmButtonText: '伸缩',
      cancelButtonText: '取消',
    })
    await client.post(`/api/k8s/workloads/${row.name}/scale`, { replicas: Number(result.value), kind }, {
      params: { cluster_id: clusterId.value, namespace: row.namespace },
    })
    ElMessage.success('副本数已更新')
    await loadResources()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '伸缩失败'))
    }
  }
}

async function showRowJson(row, sourceKind = resource.value) {
  const kind = resourceKindMap[sourceKind]
  if (!kind) return
  try {
    const params = { cluster_id: clusterId.value }
    if (kind !== 'node') params.namespace = row.namespace
    const data = (await client.get(`/api/k8s/resources/${kind}/${row.name}/json`, { params })).data
    jsonTitle.value = `${kind} JSON`
    resourceJson.value = JSON.stringify(data, null, 2)
    jsonVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取资源 JSON 失败'))
  }
}

async function showDescribe(row) {
  try {
    const data = (await client.get(`/api/k8s/pods/${row.name}/describe`, {
      params: { cluster_id: clusterId.value, namespace: row.namespace },
    })).data
    describeText.value = JSON.stringify(data, null, 2)
    describeVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取 Pod Describe 失败'))
  }
}

async function showLogs(row) {
  try {
    logs.value = (await client.get(`/api/k8s/pods/${row.name}/logs`, {
      params: { cluster_id: clusterId.value, namespace: row.namespace },
    })).data.logs
    logsTitle.value = `Pod 日志 · ${row.namespace}/${row.name}`
    logsVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取 Pod 日志失败'))
  }
}

async function deletePod(row) {
  try {
    await ElMessageBox.confirm(`确定删除 Pod ${row.namespace}/${row.name}？控制器可能会自动重建。`, '确认删除 Pod', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await client.delete(`/api/k8s/pods/${row.name}`, {
      params: { cluster_id: clusterId.value, namespace: row.namespace },
    })
    ElMessage.success('Pod 已删除')
    selectedResource.value = null
    await loadResources()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '删除 Pod 失败'))
    }
  }
}

async function deleteCluster() {
  try {
    await client.delete(`/api/k8s/clusters/${clusterId.value}`)
    ElMessage.success('集群已删除')
    clusterId.value = null
    namespaces.value = []
    selectedResource.value = null
    clearResourceData()
    await loadClusters()
    await loadNamespaces()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '删除集群失败'))
  }
}

async function saveCluster() {
  try {
    await client.post('/api/k8s/clusters', form)
    Object.assign(form, { name: '', description: '', kubeconfig: '' })
    dialogVisible.value = false
    await loadClusters()
    await loadNamespaces()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '保存集群失败'))
  }
}

function clearResourceData() {
  overview.value = {}
  pods.value = []
  nodes.value = []
  deployments.value = []
  statefulsets.value = []
  daemonsets.value = []
  servicesList.value = []
  ingresses.value = []
  jobs.value = []
  events.value = []
}

function setupAutoRefresh() {
  if (refreshTimer) clearInterval(refreshTimer)
  refreshTimer = null
  if (autoRefresh.value && clusterId.value) {
    refreshTimer = setInterval(() => {
      loadResources()
    }, 15000)
  }
}

onMounted(async () => {
  await loadClusters()
  await loadNamespaces()
})

onBeforeUnmount(() => {
  if (refreshTimer) clearInterval(refreshTimer)
})
</script>

<style scoped>
.k8s-console {
  display: grid;
  gap: 20px;
}

.eyebrow {
  margin: 0 0 5px;
  color: var(--app-accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.header-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 10px;
  max-width: 520px;
}

.cluster-select {
  width: 320px;
}

.k8s-workbench {
  display: grid;
  grid-template-columns: 272px minmax(0, 1fr) 330px;
  gap: 18px;
  min-height: 680px;
  padding: 16px;
}

.k8s-sidebar,
.resource-detail {
  min-width: 0;
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--app-surface-raised) 64%, transparent), transparent),
    linear-gradient(90deg, rgba(12, 118, 111, 0.026), transparent 58%, rgba(168, 85, 30, 0.018)),
    var(--app-surface-soft);
  box-shadow: var(--app-shadow-xs);
}

.k8s-sidebar {
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 14px;
  max-height: calc(100dvh - 188px);
  overflow: auto;
}

.cluster-card {
  display: grid;
  gap: 6px;
  padding: 14px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--app-surface-raised) 78%, transparent), transparent),
    var(--app-surface);
  box-shadow: var(--app-shadow-xs);
}

.cluster-card strong {
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 16px;
  font-weight: 760;
  overflow-wrap: anywhere;
}

.cluster-card small {
  color: var(--app-muted);
  line-height: 1.5;
}

.delete-cluster {
  justify-self: start;
  padding-left: 0;
}

.nav-block {
  display: grid;
  gap: 6px;
}

.nav-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 4px;
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 760;
}

.namespace-list {
  display: grid;
  gap: 5px;
  max-height: 170px;
  overflow: auto;
  padding-right: 2px;
}

.nav-row,
.resource-row {
  width: 100%;
  border: 0;
  border-radius: var(--app-radius);
  color: var(--app-text);
  background: transparent;
  text-align: left;
  transition: background-color 0.18s ease, color 0.18s ease, transform 0.18s ease;
}

.nav-row {
  padding: 9px 10px;
  font-weight: 700;
}

.resource-row {
  display: grid;
  grid-template-columns: 26px minmax(0, 1fr) auto;
  align-items: center;
  gap: 9px;
  padding: 9px;
  font-weight: 700;
}

.nav-row:hover,
.resource-row:hover {
  background: var(--app-surface-hover);
  transform: translateX(2px);
}

.nav-row.active,
.resource-row.active {
  color: var(--app-primary);
  background:
    linear-gradient(90deg, var(--app-primary-soft), var(--app-primary-softer) 74%, color-mix(in srgb, var(--app-accent-soft) 46%, transparent));
  box-shadow: inset 3px 0 0 var(--app-primary);
}

.resource-icon {
  display: grid;
  width: 26px;
  height: 26px;
  place-items: center;
  border-radius: var(--app-radius-sm);
  color: var(--app-primary);
  background: var(--app-primary-softer);
}

.resource-row strong {
  color: var(--app-muted);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.k8s-content {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 14px;
}

.ops-bar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0 4px;
}

.ops-bar h3 {
  margin: 0;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 18px;
  font-weight: 820;
}

.ops-bar p {
  margin: 5px 0 0;
  color: var(--app-muted);
  line-height: 1.45;
}

.ops-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 9px;
}

.resource-search {
  width: min(280px, 28vw);
}

.status-filter {
  width: 132px;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.summary-card {
  position: relative;
  overflow: hidden;
  min-height: 112px;
  padding: 15px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--app-surface-raised) 76%, transparent), transparent),
    var(--app-surface-soft);
  display: grid;
  align-content: space-between;
  box-shadow: var(--app-shadow-xs);
}

.summary-card::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: color-mix(in srgb, var(--app-border-strong) 58%, transparent);
  content: '';
}

.summary-card span,
.summary-card small {
  color: var(--app-muted);
}

.summary-card strong {
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 27px;
  font-weight: 840;
  font-variant-numeric: tabular-nums;
}

.summary-card.good {
  border-color: rgba(18, 129, 95, 0.24);
  background: var(--app-success-soft);
}

.summary-card.warn {
  border-color: rgba(183, 106, 21, 0.28);
  background: var(--app-warning-soft);
}

.summary-card.danger {
  border-color: rgba(194, 65, 60, 0.28);
  background: var(--app-danger-soft);
}

.ops-focus {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.focus-row {
  display: grid;
  gap: 5px;
  padding: 13px;
  border-left: 3px solid var(--app-primary);
  border-radius: var(--app-radius);
  background:
    linear-gradient(90deg, var(--app-primary-softer), transparent),
    var(--app-surface-soft);
}

.focus-row span {
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 760;
}

.focus-row strong {
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 19px;
}

.focus-row small {
  color: var(--app-muted);
  line-height: 1.45;
}

.resource-detail {
  display: grid;
  align-content: start;
  gap: 14px;
  padding: 14px;
  border: 1px solid var(--app-border-soft);
}

.resource-detail.empty {
  place-items: center;
}

.detail-heading {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--app-border-soft);
}

.detail-heading h3 {
  margin: 0;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 18px;
  font-weight: 760;
  line-height: 1.35;
  overflow-wrap: anywhere;
}

.detail-heading p {
  margin: 6px 0 0;
  color: var(--app-muted);
  font-family: var(--app-font-mono);
  font-size: 12px;
}

.detail-status {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border-radius: var(--app-radius);
  border: 1px solid var(--app-border-soft);
  background: var(--app-surface);
}

.detail-status span {
  color: var(--app-muted);
  font-weight: 700;
}

.detail-list {
  display: grid;
  grid-template-columns: 96px minmax(0, 1fr);
  gap: 9px 12px;
  margin: 0;
}

.detail-list dt {
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 760;
}

.detail-list dd {
  min-width: 0;
  margin: 0;
  color: var(--app-text);
  font-family: var(--app-font-mono);
  font-size: 12px;
  line-height: 1.45;
  overflow-wrap: anywhere;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  padding-top: 4px;
}

.empty-detail {
  display: grid;
  justify-items: center;
  gap: 8px;
  color: var(--app-muted);
  text-align: center;
  line-height: 1.45;
}

.empty-detail .el-icon {
  color: var(--app-primary);
  font-size: 26px;
}

.empty-detail strong {
  color: var(--app-text-heading);
}

:deep(.el-table__row) {
  cursor: pointer;
}

:deep(.el-table__row.is-selected-row > td.el-table__cell) {
  background: color-mix(in srgb, var(--app-primary-softer) 82%, var(--app-accent-soft));
}

@media (max-width: 1320px) {
  .k8s-workbench {
    grid-template-columns: 248px minmax(0, 1fr);
  }

  .resource-detail {
    grid-column: 1 / -1;
  }

  .resource-detail.empty {
    display: none;
  }
}

@media (max-width: 1100px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .ops-focus {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 900px) {
  .console-hero,
  .header-actions,
  .ops-bar {
    align-items: stretch;
    flex-direction: column;
  }

  .cluster-select,
  .resource-search,
  .status-filter {
    width: 100%;
  }

  .k8s-workbench {
    grid-template-columns: 1fr;
  }

  .k8s-sidebar {
    order: 0;
  }

  .namespace-list {
    max-height: 140px;
  }
}

@media (max-width: 640px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }

  .k8s-workbench {
    padding: 10px;
  }
}
</style>
