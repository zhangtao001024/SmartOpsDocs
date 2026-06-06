<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">服务器资产</h2>
      <div style="display: flex; gap: 8px; align-items: center">
        <el-input v-model="search" placeholder="搜索 IP / 主机名 / 标签" prefix-icon="Search" clearable style="width: 240px" />
        <el-select v-model="filterEnv" placeholder="环境" clearable style="width: 110px">
          <el-option label="开发" value="dev" />
          <el-option label="测试" value="test" />
          <el-option label="生产" value="prod" />
        </el-select>
        <el-select v-model="filterProject" placeholder="项目" clearable style="width: 130px">
          <el-option v-for="p in projects" :key="p" :label="p" :value="p" />
        </el-select>
        <el-button icon="Refresh" @click="load">刷新</el-button>
        <el-button icon="Connection" :disabled="selectedRows.length === 0" :loading="batchTesting" @click="batchTest">批量测试</el-button>
        <el-button type="primary" icon="Plus" @click="openCreate">新增服务器</el-button>
      </div>
    </div>
    <div class="panel">
      <SkeletonTable v-if="loading && servers.length === 0" :rows="6" :cols="7" />
      <el-empty v-else-if="!loading && servers.length === 0" description="暂无服务器资产，点击「新增服务器」开始添加" />
      <el-empty v-else-if="!loading && filteredServers.length === 0" description="没有匹配的服务器" />
      <el-table v-else :data="filteredServers" v-loading="loading" @selection-change="onSelectionChange">
        <el-table-column type="selection" width="44" />
        <el-table-column prop="ip" label="IP" width="150" />
        <el-table-column prop="hostname" label="主机名" />
        <el-table-column prop="ssh_port" label="SSH" width="80" />
        <el-table-column prop="ssh_username" label="用户" width="110" />
        <el-table-column prop="project" label="项目" width="120" />
        <el-table-column prop="environment" label="环境" width="100">
          <template #default="{ row }">
            <el-tag :type="envTagType(row.environment)" size="small">{{ envLabel(row.environment) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="tags" label="标签" />
        <el-table-column label="操作" width="400" fixed="right">
          <template #default="{ row }">
            <el-button size="small" :loading="testing === row.id" @click="test(row)">测试</el-button>
            <el-button size="small" @click="openOverview(row)">概览</el-button>
            <el-button size="small" @click="openCommand(row)">命令</el-button>
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" icon="Monitor" @click="openTerminal(row)">终端</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑服务器' : '新增服务器'" width="680px">
      <el-form :model="form" :rules="formRules" ref="formRef" label-width="110px">
        <el-row :gutter="12">
          <el-col :span="12">
            <el-form-item label="IP" prop="ip"><el-input v-model="form.ip" placeholder="如 192.168.1.100" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="主机名"><el-input v-model="form.hostname" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="SSH 端口" prop="ssh_port">
              <el-input-number v-model="form.ssh_port" :min="1" :max="65535" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="SSH 用户"><el-input v-model="form.ssh_username" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="项目"><el-input v-model="form.project" /></el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="环境">
              <el-select v-model="form.environment">
                <el-option label="开发" value="dev" />
                <el-option label="测试" value="test" />
                <el-option label="生产" value="prod" />
              </el-select>
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="标签"><el-input v-model="form.tags" placeholder="逗号分隔" /></el-form-item>
          </el-col>
        </el-row>
        <el-form-item label="SSH 密码">
          <el-input
            v-model="form.ssh_password"
            type="password"
            show-password
            :placeholder="editingId ? '留空则不修改已保存密码' : '密码登录时填写'"
          />
        </el-form-item>
        <el-form-item label="SSH 私钥">
          <el-input
            v-model="form.ssh_private_key"
            type="textarea"
            :rows="5"
            :placeholder="editingId ? '留空则不修改已保存私钥' : '私钥登录时填写'"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="terminalVisible" :title="'SSH 终端 — ' + (terminalServer?.ip || '')" width="860px" :close-on-click-modal="false" @closed="closeTerminal">
      <div ref="terminalBox" class="terminal-box"></div>
    </el-dialog>

    <el-dialog v-model="overviewVisible" :title="'服务器概览 — ' + (activeServer?.ip || '')" width="920px">
      <div v-loading="overviewLoading" class="overview-grid">
        <div v-for="section in overviewSections" :key="section.key" class="overview-section">
          <h4>{{ section.label }}</h4>
          <pre class="log-box">{{ formatOverview(section.key) }}</pre>
        </div>
      </div>
    </el-dialog>

    <el-dialog v-model="commandVisible" :title="'执行命令 — ' + (activeServer?.ip || '')" width="920px">
      <el-form label-width="80px">
        <el-form-item label="命令">
          <el-input v-model="commandForm.command" type="textarea" :rows="3" placeholder="例如：systemctl status nginx --no-pager" />
        </el-form-item>
        <el-form-item label="超时">
          <el-input-number v-model="commandForm.timeout" :min="1" :max="120" />
        </el-form-item>
      </el-form>
      <div class="command-actions">
        <el-button type="primary" icon="CaretRight" :loading="commandLoading" :disabled="!commandForm.command.trim()" @click="runServerCommand">执行</el-button>
        <el-tag v-if="commandResult" :type="commandResult.exit_code === 0 ? 'success' : 'danger'">exit {{ commandResult.exit_code }}</el-tag>
      </div>
      <pre class="log-box command-output">{{ commandOutput }}</pre>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import client from '../api/client'
import SkeletonTable from '../components/SkeletonTable.vue'
import '@xterm/xterm/css/xterm.css'

const loading = ref(false)
const servers = ref([])
const dialogVisible = ref(false)
const editingId = ref(null)
const formRef = ref(null)
const search = ref('')
const filterEnv = ref('')
const filterProject = ref('')
const testing = ref(null)
const selectedRows = ref([])
const batchTesting = ref(false)
const terminalVisible = ref(false)
const terminalServer = ref(null)
const terminalBox = ref(null)
const activeServer = ref(null)
const overviewVisible = ref(false)
const overviewLoading = ref(false)
const overview = ref({})
const commandVisible = ref(false)
const commandLoading = ref(false)
const commandResult = ref(null)
const commandForm = reactive({ command: '', timeout: 30 })
let terminalInstance = null
let terminalFit = null
let ws = null

const emptyForm = () => ({
  ip: '', hostname: '', ssh_port: 22, ssh_username: 'root',
  ssh_password: '', ssh_private_key: '', project: 'default',
  environment: 'dev', tags: ''
})
const form = reactive(emptyForm())

const formRules = {
  ip: [
    { required: true, message: '请输入 IP', trigger: 'blur' },
    { pattern: /^(\d{1,3}\.){3}\d{1,3}$/, message: 'IP 格式不正确', trigger: 'blur' },
  ],
  ssh_port: [
    { type: 'number', min: 1, max: 65535, message: '端口范围 1-65535', trigger: 'blur' },
  ],
}

const projects = computed(() => {
  return [...new Set(servers.value.map(function(s) { return s.project }).filter(Boolean))]
})

const overviewSections = [
  { key: 'hostname', label: '主机名' },
  { key: 'system', label: '系统' },
  { key: 'uptime', label: '运行时间' },
  { key: 'load', label: '负载' },
  { key: 'memory', label: '内存' },
  { key: 'disks', label: '磁盘' },
  { key: 'processes', label: '进程 Top' },
  { key: 'docker', label: 'Docker 容器' },
]

const commandOutput = computed(() => {
  if (!commandResult.value) return '执行后显示输出'
  return [
    commandResult.value.stdout ? `STDOUT\n${commandResult.value.stdout}` : '',
    commandResult.value.stderr ? `STDERR\n${commandResult.value.stderr}` : '',
  ].filter(Boolean).join('\n\n') || '无输出'
})

const filteredServers = computed(() => {
  var list = servers.value
  var q = search.value.toLowerCase().trim()
  if (q) {
    list = list.filter(function(s) {
      return s.ip.toLowerCase().indexOf(q) >= 0 ||
        s.hostname.toLowerCase().indexOf(q) >= 0 ||
        s.tags.toLowerCase().indexOf(q) >= 0
    })
  }
  if (filterEnv.value) list = list.filter(function(s) { return s.environment === filterEnv.value })
  if (filterProject.value) list = list.filter(function(s) { return s.project === filterProject.value })
  return list
})

function envLabel(v) {
  return { dev: '开发', test: '测试', prod: '生产' }[v] || v
}

function envTagType(v) {
  return { dev: 'success', test: 'warning', prod: 'danger' }[v] || 'info'
}

function statusTagType(v) {
  if (v === 'running' || v === 'online') return 'success'
  if (v === 'offline' || v === 'unknown') return 'info'
  if (v === 'error') return 'danger'
  return 'info'
}

function assignForm(data) {
  Object.assign(form, emptyForm(), data)
}

async function load() {
  loading.value = true
  try {
    servers.value = (await client.get('/api/servers')).data
  } finally {
    loading.value = false
  }
}

function openCreate() {
  editingId.value = null
  assignForm({})
  dialogVisible.value = true
}

function openEdit(row) {
  editingId.value = row.id
  assignForm({ ...row, ssh_password: '', ssh_private_key: '' })
  dialogVisible.value = true
}

function onSelectionChange(rows) {
  selectedRows.value = rows
}

async function save() {
  var valid = formRef.value ? await formRef.value.validate().catch(function() { return false }) : true
  if (!valid) return
  if (editingId.value) await client.put('/api/servers/' + editingId.value, form)
  else await client.post('/api/servers', form)
  ElMessage.success('已保存')
  dialogVisible.value = false
  load()
}

async function test(row, quiet) {
  testing.value = row.id
  try {
    var payload = {
      server_id: row.id,
      ip: row.ip, hostname: row.hostname, ssh_port: row.ssh_port,
      ssh_username: row.ssh_username,
    }
    var resp = await client.post('/api/servers/test-connection', payload)
    var data = resp.data
    if (data.ok) {
      if (!quiet) ElMessage.success(row.ip + ' SSH 连接成功')
      row.status = 'online'
    } else {
      if (!quiet) ElMessage.warning(row.ip + ': ' + (data.error || '连接失败'))
      row.status = 'offline'
    }
  } catch (e) {
    if (!quiet) ElMessage.error(e.response?.data?.detail || e.message || '请求失败')
  } finally {
    testing.value = null
  }
}

async function batchTest() {
  batchTesting.value = true
  try {
    for (const row of selectedRows.value) {
      await test(row, true)
    }
    ElMessage.success('批量测试完成')
  } finally {
    batchTesting.value = false
  }
}

async function remove(row) {
  try {
    await ElMessageBox.confirm('确定删除服务器 ' + row.ip + '（' + (row.hostname || '未命名') + '）？', '确认删除', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
      center: true,
    })
    await client.delete('/api/servers/' + row.id)
    ElMessage.success('已删除')
    load()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

function formatOverview(key) {
  var item = overview.value[key]
  if (!item) return ''
  return item.stdout || item.stderr || '无输出'
}

async function openOverview(row) {
  activeServer.value = row
  overviewVisible.value = true
  overviewLoading.value = true
  overview.value = {}
  try {
    overview.value = (await client.get('/api/servers/' + row.id + '/overview')).data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '获取服务器概览失败')
  } finally {
    overviewLoading.value = false
  }
}

function openCommand(row) {
  activeServer.value = row
  commandResult.value = null
  Object.assign(commandForm, { command: '', timeout: 30 })
  commandVisible.value = true
}

async function runServerCommand() {
  if (!activeServer.value || !commandForm.command.trim()) return
  commandLoading.value = true
  try {
    commandResult.value = (await client.post('/api/servers/' + activeServer.value.id + '/command', commandForm)).data
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '命令执行失败')
  } finally {
    commandLoading.value = false
  }
}

function openTerminal(row) {
  terminalServer.value = row
  terminalVisible.value = true
  nextTick(function() {
    var box = terminalBox.value
    if (!box) return
    box.innerHTML = ''
    var term = new Terminal({ cursorBlink: true, fontSize: 14 })
    var fit = new FitAddon()
    term.loadAddon(fit)
    term.open(box)
    fit.fit()
    terminalInstance = term
    terminalFit = fit

    var token = localStorage.getItem('smartopsdocs_token')
    var protocol = location.protocol === 'https:' ? 'wss' : 'ws'
    var url = protocol + '://' + location.host + '/api/servers/' + row.id + '/ssh'
    ws = new WebSocket(url)
    ws.binaryType = 'arraybuffer'

    ws.onopen = function() {
      ws.send('auth:' + token)
      term.focus()
      term.write('\r\n\x1b[32m✓ 认证中...\x1b[0m\r\n')
    }

    var firstData = true
    ws.onmessage = function(e) {
      if (typeof e.data === 'string' && e.data === 'shell:ready') {
        term.write('\x1b[32m✓ Shell 已就绪\x1b[0m\r\n')
        return
      }
      if (typeof e.data === 'string') return
      if (firstData) {
        term.write('\x1b[32m✓ Shell 已就绪\x1b[0m\r\n')
        firstData = false
      }
      term.write(new Uint8Array(e.data))
    }

    ws.onclose = function(ev) {
      term.write('\r\n\x1b[31m连接已断开 (code: ' + ev.code + ')\x1b[0m\r\n')
    }

    ws.onerror = function() {
      term.write('\r\n\x1b[31m连接失败\x1b[0m\r\n')
    }

    term.onData(function(data) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(new TextEncoder().encode(data))
      }
    })
  })
}

function closeTerminal() {
  if (ws) { ws.close(); ws = null }
  if (terminalInstance) { terminalInstance.dispose(); terminalInstance = null }
  terminalFit = null
  terminalServer.value = null
}

onMounted(load)
</script>

<style scoped>
.terminal-box {
  height: 520px;
  background: var(--app-terminal-bg);
  border-radius: var(--app-radius);
  overflow: hidden;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.overview-section h4 {
  margin: 0 0 8px;
  color: var(--app-text-heading);
}

.command-actions {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 12px;
}

.command-output {
  min-height: 260px;
}

@media (max-width: 800px) {
  .overview-grid {
    grid-template-columns: 1fr;
  }
}
</style>
