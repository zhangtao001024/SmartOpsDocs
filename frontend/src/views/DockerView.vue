<template>
  <div class="console-page">
    <section class="console-hero">
      <div class="page-heading">
        <p class="page-kicker">Container operations</p>
        <h2 class="page-title">Docker 管理</h2>
        <p class="page-subtitle">集中查看容器、镜像、网络、卷和 Compose 项目，保留日志、Shell 与文件操作入口。</p>
        <div class="console-status-strip">
          <span><strong>{{ selectedServerLabel }}</strong> 当前服务器</span>
          <span><strong>{{ dashboard.info?.Containers ?? containers.length }}</strong> 容器</span>
          <span><strong>{{ dashboard.info?.Images ?? images.length }}</strong> 镜像</span>
          <span><strong>{{ logTail }}</strong> 日志行数</span>
        </div>
      </div>
      <div class="toolbar-actions docker-actions">
        <el-select v-model="serverId" class="docker-server-select" placeholder="选择服务器" @change="loadAll">
          <el-option v-for="server in servers" :key="server.id" :label="server.ip + ' ' + server.hostname" :value="server.id" />
        </el-select>
        <el-input-number v-model="logTail" class="docker-tail-input" :min="50" :max="5000" :step="50" controls-position="right" />
        <el-button icon="Download" @click="openPullImage" :disabled="!serverId">拉取镜像</el-button>
        <el-dropdown :disabled="!serverId" @command="pruneDocker">
          <el-button icon="Delete">清理</el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="containers">停止容器</el-dropdown-item>
              <el-dropdown-item command="images">悬空镜像</el-dropdown-item>
              <el-dropdown-item command="volumes">未使用卷</el-dropdown-item>
              <el-dropdown-item command="networks">未使用网络</el-dropdown-item>
              <el-dropdown-item command="system">系统清理</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button icon="Refresh" @click="loadAll">刷新</el-button>
      </div>
    </section>
    <div class="panel docker-panel">
      <el-empty v-if="!serverId" description="请先选择一个服务器" />
      <el-tabs v-else v-model="tab" @tab-change="loadAll">
        <el-tab-pane label="概览" name="overview">
          <div class="docker-summary" v-loading="loading">
            <div class="summary-card">
              <span>容器</span>
              <strong>{{ dashboard.info?.Containers ?? '-' }}</strong>
              <small>运行 {{ dashboard.info?.ContainersRunning ?? '-' }} / 停止 {{ dashboard.info?.ContainersStopped ?? '-' }}</small>
            </div>
            <div class="summary-card">
              <span>镜像</span>
              <strong>{{ dashboard.info?.Images ?? '-' }}</strong>
              <small>{{ dashboard.info?.Driver || 'Storage driver' }}</small>
            </div>
            <div class="summary-card">
              <span>Docker</span>
              <strong>{{ dockerVersion }}</strong>
              <small>{{ dashboard.info?.OperatingSystem || '-' }}</small>
            </div>
            <div class="summary-card warning">
              <span>资源清理</span>
              <strong>{{ dashboard.disk?.length || 0 }}</strong>
              <small>docker system df 项</small>
            </div>
          </div>
          <el-table :data="dashboard.disk || []" v-loading="loading">
            <el-table-column prop="Type" label="类型" />
            <el-table-column prop="TotalCount" label="总数" width="100" />
            <el-table-column prop="ActiveCount" label="活跃" width="100" />
            <el-table-column prop="Size" label="大小" width="140" />
            <el-table-column prop="Reclaimable" label="可回收" width="180" />
          </el-table>
        </el-tab-pane>
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
            <el-table-column label="操作" width="430" fixed="right">
              <template #default="{ row }">
                <div class="row-actions docker-row-actions">
                  <el-button size="small" :loading="acting === row.id + '-start'" @click="action(row, 'start')">启动</el-button>
                  <el-button size="small" :loading="acting === row.id + '-stop'" @click="action(row, 'stop')">停止</el-button>
                  <el-button size="small" type="warning" :loading="acting === row.id + '-restart'" @click="action(row, 'restart')">重启</el-button>
                  <el-button size="small" icon="Monitor" @click="openContainerShell(row)">Shell</el-button>
                  <el-button size="small" icon="FolderOpened" @click="openContainerFiles(row)">文件</el-button>
                  <el-button size="small" icon="Tickets" @click="openCompose(row)">Compose</el-button>
                  <el-popover
                    placement="bottom-end"
                    trigger="click"
                    :width="168"
                    popper-class="docker-more-popper"
                    :visible="activeContainerMoreId === row.id"
                    @update:visible="(visible) => setContainerMoreVisible(row, visible)"
                  >
                    <template #reference>
                      <el-button size="small" icon="MoreFilled">更多</el-button>
                    </template>
                    <div class="docker-more-menu">
                      <button type="button" @click="handleContainerMore(row, 'logs')">日志</button>
                      <button type="button" @click="handleContainerMore(row, 'top')">Top</button>
                      <button type="button" @click="handleContainerMore(row, 'inspect')">Inspect</button>
                      <button type="button" @click="handleContainerMore(row, 'pause')">暂停</button>
                      <button type="button" @click="handleContainerMore(row, 'unpause')">恢复</button>
                      <button type="button" class="danger" @click="handleContainerMore(row, 'kill')">Kill</button>
                    </div>
                  </el-popover>
                </div>
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
            <el-table-column label="操作" width="120" fixed="right">
              <template #default="{ row }">
                <el-button size="small" type="danger" text @click="removeImage(row)">删除</el-button>
              </template>
            </el-table-column>
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
            <el-table-column label="操作" width="110" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="inspectNetwork(row)">Inspect</el-button>
              </template>
            </el-table-column>
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
            <el-table-column label="操作" width="110" fixed="right">
              <template #default="{ row }">
                <el-button size="small" @click="inspectVolume(row)">Inspect</el-button>
              </template>
            </el-table-column>
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
    <el-dialog v-model="detailVisible" :title="detailTitle" width="920px">
      <pre class="log-box">{{ detailText }}</pre>
    </el-dialog>
    <el-dialog
      v-model="shellVisible"
      :title="'容器 Shell - ' + (shellContainer?.name || '')"
      width="920px"
      :close-on-click-modal="false"
      @closed="closeContainerShell"
    >
      <div class="container-shell-toolbar">
        <el-select v-model="shellType" class="shell-select">
          <el-option label="Auto" value="auto" />
          <el-option label="/bin/sh" value="/bin/sh" />
          <el-option label="/bin/bash" value="/bin/bash" />
          <el-option label="/bin/ash" value="/bin/ash" />
        </el-select>
        <el-button icon="Refresh" @click="reconnectContainerShell">重连</el-button>
        <el-tag v-if="shellContainer" size="small" type="info">{{ shellContainer.id }}</el-tag>
      </div>
      <div ref="shellBox" class="container-shell-box"></div>
    </el-dialog>
    <el-drawer v-model="fileDrawerVisible" :title="'容器文件 - ' + (fileContainer?.name || '')" size="70%" @closed="resetContainerFileManager">
      <div class="file-toolbar">
        <el-input v-model="containerFilePath" placeholder="容器路径" @keyup.enter="loadContainerFiles" />
        <el-button icon="Back" @click="goContainerParent">上级</el-button>
        <el-button icon="FolderAdd" @click="createContainerDirectory">新建目录</el-button>
        <el-button icon="DocumentAdd" @click="createContainerFile">新建文件</el-button>
        <el-button icon="Refresh" @click="loadContainerFiles">刷新</el-button>
      </div>
      <el-table :data="containerFiles" v-loading="containerFileLoading" height="calc(100vh - 230px)">
        <el-table-column label="名称">
          <template #default="{ row }">
            <el-button text :icon="row.type === 'directory' ? 'FolderOpened' : 'Document'" @click="openContainerFileItem(row)">
              {{ row.name }}
            </el-button>
          </template>
        </el-table-column>
        <el-table-column prop="type" label="类型" width="110" />
        <el-table-column label="大小" width="120">
          <template #default="{ row }">{{ row.type === 'directory' ? '-' : formatBytes(row.size) }}</template>
        </el-table-column>
        <el-table-column prop="permissions" label="权限" width="130" />
        <el-table-column label="修改时间" width="180">
          <template #default="{ row }">{{ formatTime(row.mtime) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button v-if="row.type !== 'directory'" size="small" @click="readContainerFile(row)">编辑</el-button>
            <el-button size="small" type="danger" text @click="deleteContainerFile(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
    <el-dialog v-model="fileEditorVisible" :title="'编辑容器文件 - ' + editingContainerFile" width="900px">
      <el-input v-model="containerFileContent" type="textarea" :rows="20" spellcheck="false" class="file-editor" />
      <template #footer>
        <el-button @click="fileEditorVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingContainerFile" @click="saveContainerFile">保存</el-button>
      </template>
    </el-dialog>
    <el-dialog
      v-model="composeVisible"
      :title="'Docker Compose - ' + (composeInfo.project || composeContainer?.name || '')"
      width="1040px"
      :close-on-click-modal="false"
    >
      <div v-loading="composeLoading">
        <el-empty v-if="!composeLoading && !composeInfo.detected" description="未从容器 Inspect 中发现 Compose 项目" />
        <template v-else>
          <div class="compose-meta">
            <div class="compose-meta-item">
              <span>项目</span>
              <strong>{{ composeInfo.project || '-' }}</strong>
            </div>
            <div class="compose-meta-item">
              <span>服务</span>
              <strong>{{ composeInfo.service || '-' }}</strong>
            </div>
            <div class="compose-meta-item">
              <span>工作目录</span>
              <strong>{{ composeInfo.working_dir || '-' }}</strong>
            </div>
          </div>
          <el-alert
            v-if="composeInfo.detected && !composeConfigFiles.length"
            title="已识别 Compose 项目，但未在服务器上找到可编辑的 YAML 文件"
            type="warning"
            :closable="false"
            show-icon
            class="compose-alert"
          />
          <div class="compose-toolbar">
            <el-select v-model="composeSelectedFile" placeholder="选择 Compose YAML" :disabled="!composeConfigFiles.length" @change="loadComposeFile">
              <el-option v-for="file in composeConfigFiles" :key="file" :label="file" :value="file" />
            </el-select>
            <el-button icon="Refresh" :disabled="!composeSelectedFile" @click="loadComposeFile">重载 YAML</el-button>
            <el-button icon="DocumentChecked" type="primary" :loading="composeSaving" :disabled="!composeSelectedFile" @click="saveComposeFile">保存 YAML</el-button>
          </div>
          <el-input
            v-model="composeContent"
            type="textarea"
            :rows="18"
            spellcheck="false"
            class="compose-editor"
            :disabled="!composeSelectedFile"
          />
          <div class="compose-actions">
            <el-button
              v-for="item in composeActions"
              :key="item.action"
              size="small"
              :type="item.type || 'default'"
              :loading="composeRunning === item.action"
              :disabled="!composeConfigFiles.length"
              @click="runComposeAction(item.action)"
            >
              {{ item.label }}
            </el-button>
          </div>
          <el-table :data="composeInfo.containers || []" size="small" class="compose-containers">
            <el-table-column prop="name" label="容器" />
            <el-table-column prop="image" label="镜像" />
            <el-table-column prop="status" label="状态" width="220" />
            <el-table-column prop="ports" label="端口" />
          </el-table>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import client, { getApiErrorMessage } from '../api/client'
import SkeletonTable from '../components/SkeletonTable.vue'
import '@xterm/xterm/css/xterm.css'

const servers = ref([])
const serverId = ref(null)
const containers = ref([])
const stats = ref([])
const tab = ref('overview')
const acting = ref('')
const dashboard = ref({})
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
const detailVisible = ref(false)
const detailTitle = ref('')
const detailText = ref('')
const shellVisible = ref(false)
const shellContainer = ref(null)
const shellBox = ref(null)
const shellType = ref('auto')
const fileDrawerVisible = ref(false)
const fileContainer = ref(null)
const containerFilePath = ref('/')
const containerFiles = ref([])
const containerFileLoading = ref(false)
const fileEditorVisible = ref(false)
const editingContainerFile = ref('')
const containerFileContent = ref('')
const savingContainerFile = ref(false)
const composeVisible = ref(false)
const composeLoading = ref(false)
const composeContainer = ref(null)
const composeInfo = ref({})
const composeSelectedFile = ref('')
const composeContent = ref('')
const composeSaving = ref(false)
const composeRunning = ref('')
const activeContainerMoreId = ref(null)
let shellTerminal = null
let shellFit = null
let shellWs = null

const composeActions = [
  { action: 'ps', label: 'ps' },
  { action: 'config', label: 'config' },
  { action: 'logs', label: 'logs' },
  { action: 'restart', label: 'restart', type: 'warning' },
  { action: 'up', label: 'up -d', type: 'primary' },
  { action: 'down', label: 'down', type: 'danger' },
  { action: 'pull', label: 'pull' },
  { action: 'stop', label: 'stop' },
  { action: 'start', label: 'start' },
]

const dockerVersion = computed(() => {
  return dashboard.value.version?.Server?.Version || dashboard.value.info?.ServerVersion || '-'
})

const selectedServerLabel = computed(() => {
  const server = servers.value.find((item) => item.id === serverId.value)
  if (!server) return '未选择'
  return server.hostname || server.ip
})

const composeConfigFiles = computed(() => {
  return composeInfo.value.config_files || []
})

async function loadServers() {
  servers.value = (await client.get('/api/servers')).data
  if (!serverId.value && servers.value[0]) serverId.value = servers.value[0].id
}

function containerStatusType(s) {
  if (!s) return 'info'
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
    if (tab.value === 'overview') {
      dashboard.value = (await client.get('/api/docker/' + serverId.value + '/dashboard')).data
    } else if (tab.value === 'containers') {
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
    ElMessage.error(getApiErrorMessage(error, '获取失败'))
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
    ElMessage.error(getApiErrorMessage(error, '获取容器失败'))
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
    if (['stop', 'kill'].includes(type)) {
      await ElMessageBox.confirm('确定对容器 ' + row.name + ' 执行 ' + type + '？', '确认操作', {
        type: 'warning',
        confirmButtonText: type,
        cancelButtonText: '取消',
      })
    }
    await client.post('/api/docker/' + serverId.value + '/containers/' + row.id + '/' + type)
    ElMessage.success(type + ' 已执行')
    loadContainers()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '操作失败'))
    }
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
    ElMessage.error(getApiErrorMessage(error, '获取日志失败'))
  }
}

async function showInspect(row) {
  try {
    const data = (await client.get(`/api/docker/${serverId.value}/containers/${row.id}/inspect`)).data
    inspectText.value = JSON.stringify(data, null, 2)
    inspectVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取 Inspect 失败'))
  }
}

async function showTop(row) {
  try {
    const data = (await client.get(`/api/docker/${serverId.value}/containers/${row.id}/top`)).data
    topText.value = data.raw || [data.header].concat(data.rows || []).join('\n')
    topVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取容器进程失败'))
  }
}

async function openPullImage() {
  if (!serverId.value) return
  try {
    const result = await ElMessageBox.prompt('输入镜像名，例如 nginx:1.27-alpine', '拉取镜像', {
      inputPattern: /\S+:\S+|\S+/,
      inputErrorMessage: '请输入镜像名',
      confirmButtonText: '拉取',
      cancelButtonText: '取消',
    })
    const data = (await client.post(`/api/docker/${serverId.value}/images/pull`, { image: result.value.trim() })).data
    detailTitle.value = '镜像拉取结果'
    detailText.value = [data.stdout, data.stderr].filter(Boolean).join('\n') || '无输出'
    detailVisible.value = true
    tab.value = 'images'
    await loadAll()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '拉取镜像失败'))
    }
  }
}

async function removeImage(row) {
  const image = row.repository === '<none>' || row.tag === '<none>' ? row.image_id : row.repository + ':' + row.tag
  try {
    await ElMessageBox.confirm('确定删除镜像 ' + image + '？', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    const data = (await client.delete(`/api/docker/${serverId.value}/images`, { params: { image } })).data
    detailTitle.value = '镜像删除结果'
    detailText.value = [data.stdout, data.stderr].filter(Boolean).join('\n') || '无输出'
    detailVisible.value = true
    await loadAll()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '删除镜像失败'))
    }
  }
}

async function pruneDocker(target) {
  try {
    await ElMessageBox.confirm('确定执行 Docker ' + target + ' 清理？', '确认清理', {
      type: 'warning',
      confirmButtonText: '清理',
      cancelButtonText: '取消',
    })
    const data = (await client.post(`/api/docker/${serverId.value}/prune/${target}`)).data
    detailTitle.value = '清理结果'
    detailText.value = [data.stdout, data.stderr].filter(Boolean).join('\n') || '无输出'
    detailVisible.value = true
    await loadAll()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '清理失败'))
    }
  }
}

async function inspectNetwork(row) {
  try {
    const data = (await client.get(`/api/docker/${serverId.value}/networks/${row.name}/inspect`)).data
    detailTitle.value = '网络 Inspect - ' + row.name
    detailText.value = JSON.stringify(data, null, 2)
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取网络详情失败'))
  }
}

async function inspectVolume(row) {
  try {
    const data = (await client.get(`/api/docker/${serverId.value}/volumes/${row.name}/inspect`)).data
    detailTitle.value = '卷 Inspect - ' + row.name
    detailText.value = JSON.stringify(data, null, 2)
    detailVisible.value = true
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '获取卷详情失败'))
  }
}

function handleContainerMore(row, command) {
  activeContainerMoreId.value = null
  if (command === 'logs') {
    showLogs(row)
  } else if (command === 'top') {
    showTop(row)
  } else if (command === 'inspect') {
    showInspect(row)
  } else {
    action(row, command)
  }
}

function setContainerMoreVisible(row, visible) {
  activeContainerMoreId.value = visible ? row.id : null
}

function openContainerShell(row) {
  shellContainer.value = row
  shellVisible.value = true
  nextTick(connectContainerShell)
}

function reconnectContainerShell() {
  if (!shellContainer.value) return
  disposeContainerShell()
  nextTick(connectContainerShell)
}

function connectContainerShell() {
  const box = shellBox.value
  const row = shellContainer.value
  if (!box || !row || !serverId.value) return

  box.innerHTML = ''
  const term = new Terminal({ cursorBlink: true, fontSize: 14 })
  const fit = new FitAddon()
  term.loadAddon(fit)
  term.open(box)
  fit.fit()
  shellTerminal = term
  shellFit = fit

  const token = localStorage.getItem('smartopsdocs_token')
  const protocol = location.protocol === 'https:' ? 'wss' : 'ws'
  const url = protocol + '://' + location.host +
    `/api/docker/${serverId.value}/containers/${row.id}/shell?shell=${encodeURIComponent(shellType.value)}`
  shellWs = new WebSocket(url)
  shellWs.binaryType = 'arraybuffer'

  shellWs.onopen = function() {
    shellWs.send('auth:' + token)
    term.focus()
    term.write('\r\n\x1b[32m正在进入容器 Shell...\x1b[0m\r\n')
  }

  shellWs.onmessage = function(e) {
    if (typeof e.data === 'string' && e.data === 'shell:ready') {
      term.write('\x1b[32mShell 已就绪\x1b[0m\r\n')
      return
    }
    if (typeof e.data === 'string') {
      if (e.data.indexOf('shell:error:') === 0) {
        term.write('\r\n\x1b[31m' + e.data.slice(12) + '\x1b[0m\r\n')
      } else if (e.data.indexOf('shell:exit:') === 0) {
        term.write('\r\n\x1b[33mShell 已退出，退出码 ' + e.data.slice(11) + '\x1b[0m\r\n')
      } else {
        term.write(e.data)
      }
      return
    }
    term.write(new Uint8Array(e.data))
  }

  shellWs.onclose = function(ev) {
    term.write('\r\n\x1b[31m容器 Shell 已断开 (code: ' + ev.code + ')\x1b[0m\r\n')
  }

  shellWs.onerror = function() {
    term.write('\r\n\x1b[31m容器 Shell 连接失败\x1b[0m\r\n')
  }

  term.onData(function(data) {
    if (shellWs && shellWs.readyState === WebSocket.OPEN) {
      shellWs.send(new TextEncoder().encode(data))
    }
  })
}

function disposeContainerShell() {
  if (shellWs) {
    shellWs.close()
    shellWs = null
  }
  if (shellTerminal) {
    shellTerminal.dispose()
    shellTerminal = null
  }
  shellFit = null
}

function closeContainerShell() {
  disposeContainerShell()
  shellContainer.value = null
}

function openContainerFiles(row) {
  fileContainer.value = row
  containerFilePath.value = '/'
  containerFiles.value = []
  fileDrawerVisible.value = true
  loadContainerFiles()
}

function resetContainerFileManager() {
  fileContainer.value = null
  containerFiles.value = []
  containerFilePath.value = '/'
  editingContainerFile.value = ''
  containerFileContent.value = ''
}

function containerPathJoin(base, name) {
  if (name.startsWith('/')) return name
  if (!base || base === '/') return '/' + name
  return base.replace(/\/$/, '') + '/' + name
}

async function loadContainerFiles() {
  if (!serverId.value || !fileContainer.value) return
  containerFileLoading.value = true
  try {
    const data = (await client.get(`/api/docker/${serverId.value}/containers/${fileContainer.value.id}/files`, {
      params: { path: containerFilePath.value || '/' }
    })).data
    containerFilePath.value = data.path
    containerFiles.value = data.files || []
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '读取容器目录失败'))
  } finally {
    containerFileLoading.value = false
  }
}

function openContainerFileItem(row) {
  if (row.type === 'directory') {
    containerFilePath.value = row.path
    loadContainerFiles()
  } else {
    readContainerFile(row)
  }
}

async function readContainerFile(row) {
  if (!serverId.value || !fileContainer.value) return
  try {
    const data = (await client.post(`/api/docker/${serverId.value}/containers/${fileContainer.value.id}/files/read`, {
      path: row.path,
      max_bytes: 1024 * 1024,
    })).data
    editingContainerFile.value = data.path
    containerFileContent.value = data.content || ''
    fileEditorVisible.value = true
    if (data.truncated) ElMessage.warning('文件较大，仅加载前 1MB 内容')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '读取容器文件失败'))
  }
}

async function saveContainerFile() {
  if (!serverId.value || !fileContainer.value || !editingContainerFile.value) return
  savingContainerFile.value = true
  try {
    await client.put(`/api/docker/${serverId.value}/containers/${fileContainer.value.id}/files`, {
      path: editingContainerFile.value,
      content: containerFileContent.value,
    })
    ElMessage.success('容器文件已保存')
    fileEditorVisible.value = false
    await loadContainerFiles()
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '保存容器文件失败'))
  } finally {
    savingContainerFile.value = false
  }
}

async function createContainerDirectory() {
  if (!serverId.value || !fileContainer.value) return
  try {
    const result = await ElMessageBox.prompt('输入新目录名称或完整路径', '新建容器目录', {
      inputValue: '',
      inputPattern: /\S+/,
      inputErrorMessage: '目录不能为空',
      confirmButtonText: '创建',
      cancelButtonText: '取消',
    })
    const path = containerPathJoin(containerFilePath.value, result.value.trim())
    await client.post(`/api/docker/${serverId.value}/containers/${fileContainer.value.id}/directories`, { path })
    ElMessage.success('目录已创建')
    await loadContainerFiles()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '创建目录失败'))
    }
  }
}

async function createContainerFile() {
  if (!fileContainer.value) return
  try {
    const result = await ElMessageBox.prompt('输入新文件名称或完整路径', '新建容器文件', {
      inputValue: '',
      inputPattern: /\S+/,
      inputErrorMessage: '文件名不能为空',
      confirmButtonText: '创建',
      cancelButtonText: '取消',
    })
    editingContainerFile.value = containerPathJoin(containerFilePath.value, result.value.trim())
    containerFileContent.value = ''
    fileEditorVisible.value = true
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '创建文件失败'))
    }
  }
}

async function deleteContainerFile(row) {
  if (!serverId.value || !fileContainer.value) return
  try {
    await ElMessageBox.confirm('确定删除 ' + row.path + '？目录必须为空。', '确认删除', {
      type: 'warning',
      confirmButtonText: '删除',
      cancelButtonText: '取消',
    })
    await client.delete(`/api/docker/${serverId.value}/containers/${fileContainer.value.id}/files`, {
      params: { path: row.path }
    })
    ElMessage.success('已删除')
    await loadContainerFiles()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, '删除失败'))
    }
  }
}

function goContainerParent() {
  const value = containerFilePath.value || '/'
  if (value === '/') return
  const trimmed = value.replace(/\/$/, '')
  const index = trimmed.lastIndexOf('/')
  containerFilePath.value = index <= 0 ? '/' : trimmed.slice(0, index)
  loadContainerFiles()
}

async function openCompose(row) {
  composeContainer.value = row
  composeInfo.value = {}
  composeSelectedFile.value = ''
  composeContent.value = ''
  composeVisible.value = true
  await refreshComposeInfo(true)
}

async function refreshComposeInfo(loadFirstFile) {
  if (!serverId.value || !composeContainer.value) return
  composeLoading.value = true
  try {
    const data = (await client.get(`/api/docker/${serverId.value}/containers/${composeContainer.value.id}/compose`)).data
    composeInfo.value = data
    const files = data.config_files || []
    if (!files.includes(composeSelectedFile.value)) {
      composeSelectedFile.value = files[0] || ''
    }
    if (loadFirstFile && composeSelectedFile.value) {
      await loadComposeFile()
    }
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '发现 Compose 项目失败'))
  } finally {
    composeLoading.value = false
  }
}

async function loadComposeFile() {
  if (!serverId.value || !composeSelectedFile.value) return
  try {
    const data = (await client.get(`/api/docker/${serverId.value}/compose/file`, {
      params: { path: composeSelectedFile.value }
    })).data
    composeContent.value = data.content || ''
    if (data.truncated) ElMessage.warning('Compose 文件较大，仅加载前 5MB 内容')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '读取 Compose YAML 失败'))
  }
}

async function saveComposeFile() {
  if (!serverId.value || !composeSelectedFile.value) return
  composeSaving.value = true
  try {
    await client.put(`/api/docker/${serverId.value}/compose/file`, {
      path: composeSelectedFile.value,
      content: composeContent.value,
    })
    ElMessage.success('Compose YAML 已保存')
  } catch (error) {
    ElMessage.error(getApiErrorMessage(error, '保存 Compose YAML 失败'))
  } finally {
    composeSaving.value = false
  }
}

async function runComposeAction(actionName) {
  if (!serverId.value || !composeConfigFiles.value.length) return
  try {
    if (['down', 'restart', 'stop'].includes(actionName)) {
      await ElMessageBox.confirm('确定执行 docker compose ' + actionName + '？', '确认 Compose 操作', {
        type: 'warning',
        confirmButtonText: actionName,
        cancelButtonText: '取消',
      })
    }
    composeRunning.value = actionName
    const data = (await client.post(`/api/docker/${serverId.value}/compose/action`, {
      working_dir: composeInfo.value.working_dir || '',
      config_files: composeConfigFiles.value,
      action: actionName,
      tail: logTail.value,
    })).data
    detailTitle.value = 'Compose ' + actionName + ' 结果'
    detailText.value = [
      'exit ' + data.exit_code,
      data.stdout,
      data.stderr,
    ].filter(Boolean).join('\n')
    detailVisible.value = true
    if (['up', 'down', 'restart', 'stop', 'start'].includes(actionName)) {
      await refreshComposeInfo(false)
      await loadContainers()
    }
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(getApiErrorMessage(error, 'Compose 操作失败'))
    }
  } finally {
    composeRunning.value = ''
  }
}

function formatBytes(value) {
  const size = Number(value || 0)
  if (size < 1024) return size + ' B'
  if (size < 1024 * 1024) return (size / 1024).toFixed(1) + ' KB'
  if (size < 1024 * 1024 * 1024) return (size / 1024 / 1024).toFixed(1) + ' MB'
  return (size / 1024 / 1024 / 1024).toFixed(1) + ' GB'
}

function formatTime(value) {
  const seconds = Number(value || 0)
  if (!seconds) return '-'
  return new Date(seconds * 1000).toLocaleString()
}

onMounted(async () => {
  await loadServers()
  if (serverId.value) {
    await loadAll()
  }
})

onBeforeUnmount(disposeContainerShell)
</script>

<style scoped>
.docker-actions {
  min-width: 0;
  max-width: 760px;
}

.docker-server-select {
  width: 300px;
}

.docker-tail-input {
  width: 130px;
}

.docker-panel {
  padding: 16px;
}

.docker-row-actions {
  justify-content: flex-end;
}

.docker-summary {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin: 12px 0 16px;
}

.container-shell-toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}

.shell-select {
  width: 150px;
}

.container-shell-box {
  height: 520px;
  background: var(--app-terminal-bg);
  border-radius: var(--app-radius);
  overflow: hidden;
}

.compose-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 14px;
}

.compose-meta-item {
  min-width: 0;
  padding: 12px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius-md);
  background: var(--app-surface-soft);
}

.compose-meta-item span,
.compose-meta-item strong {
  display: block;
}

.compose-meta-item span {
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 700;
}

.compose-meta-item strong {
  overflow: hidden;
  margin-top: 6px;
  color: var(--app-text-heading);
  font-family: var(--app-font-mono);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.compose-toolbar,
.compose-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin: 12px 0;
}

.compose-toolbar .el-select {
  flex: 1 1 360px;
}

:global(.docker-more-popper) {
  padding: 6px;
}

.docker-more-menu {
  display: grid;
  gap: 2px;
}

.docker-more-menu button {
  width: 100%;
  border: 0;
  border-radius: var(--app-radius-sm);
  padding: 8px 10px;
  color: var(--app-text);
  background: transparent;
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  text-align: left;
  cursor: pointer;
}

.docker-more-menu button:hover {
  color: var(--app-primary);
  background: var(--app-primary-softer);
}

.docker-more-menu button.danger:hover {
  color: var(--app-danger);
  background: var(--app-danger-soft);
}

.compose-editor :deep(.el-textarea__inner),
.file-editor :deep(.el-textarea__inner) {
  font-family: var(--app-font-mono);
  font-size: 13px;
  line-height: 1.65;
}

.compose-containers {
  margin-top: 12px;
}

@media (max-width: 1000px) {
  .docker-summary {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .docker-server-select,
  .docker-tail-input,
  .shell-select {
    width: 100%;
  }

  .docker-summary {
    grid-template-columns: 1fr;
  }
}
</style>
