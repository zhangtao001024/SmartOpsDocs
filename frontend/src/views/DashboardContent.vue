<template>
  <div>
    <div class="toolbar">
      <h2 class="page-title">运维概览</h2>
      <el-button icon="Refresh" :loading="loading" @click="load">刷新</el-button>
    </div>
    <div v-if="loading && !loaded" class="dash-grid">
      <SkeletonBox v-for="i in 4" :key="i" height="124px" />
    </div>
    <div v-else class="dash-grid">
      <div class="stat-card">
        <el-icon><Monitor /></el-icon>
        <div>
          <div class="stat-label">服务器</div>
          <div class="stat-num">{{ stats.servers }}</div>
          <div class="stat-sub">{{ stats.servers_online }} 台在线</div>
        </div>
      </div>
      <div class="stat-card">
        <el-icon><Connection /></el-icon>
        <div>
          <div class="stat-label">K8s 集群</div>
          <div class="stat-num">{{ stats.clusters }}</div>
          <div class="stat-sub">已接入集群</div>
        </div>
      </div>
      <div class="stat-card">
        <el-icon><Document /></el-icon>
        <div>
          <div class="stat-label">知识文档</div>
          <div class="stat-num">{{ stats.documents }}</div>
          <div class="stat-sub">{{ stats.chunks }} 个片段 / {{ stats.documents_parsing }} 个解析中</div>
        </div>
      </div>
      <div class="stat-card">
        <el-icon><Warning /></el-icon>
        <div>
          <div class="stat-label">离线 / 未知</div>
          <div class="stat-num">{{ stats.servers - stats.servers_online }}</div>
          <div class="stat-sub">待确认资产</div>
        </div>
      </div>
    </div>
    <div class="charts-row" v-if="loaded">
      <div class="panel chart-panel">
        <DonutChart
          label="台服务器"
          :segments="[
            { value: stats.servers_online, color: 'var(--app-success)', label: '在线' },
            { value: stats.servers - stats.servers_online, color: 'var(--app-muted-soft)', label: '离线/未知' },
          ]"
        />
        <div class="chart-legend">
          <div class="legend-item"><span class="legend-dot success"></span>在线 {{ stats.servers_online }}</div>
          <div class="legend-item"><span class="legend-dot muted"></span>离线/未知 {{ stats.servers - stats.servers_online }}</div>
        </div>
      </div>
      <div class="panel chart-panel">
        <BarChart
          title="知识库统计"
          :bars="[
            { label: '文档', value: stats.documents, color: 'var(--app-primary)' },
            { label: '片段', value: stats.chunks, color: 'var(--app-success)' },
            { label: '解析中', value: stats.documents_parsing, color: 'var(--app-warning)' },
            { label: '失败', value: stats.documents_failed, color: 'var(--app-danger)' },
          ]"
        />
      </div>
    </div>

    <div class="quick-panel panel">
      <div>
        <h3>快捷入口</h3>
        <p class="muted">常用运维工作流</p>
      </div>
      <div class="quick-actions">
        <el-button type="primary" icon="Plus" @click="$router.push('/servers')">新增服务器</el-button>
        <el-button icon="Upload" @click="$router.push('/documents')">上传文档</el-button>
        <el-button icon="ChatDotRound" @click="$router.push('/chat')">AI 助手</el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import client from '../api/client'
import SkeletonBox from '../components/SkeletonBox.vue'
import DonutChart from '../components/DonutChart.vue'
import BarChart from '../components/BarChart.vue'

const loading = ref(false)
const loaded = ref(false)

const stats = reactive({
  servers: 0,
  servers_online: 0,
  clusters: 0,
  documents: 0,
  documents_parsing: 0,
  documents_failed: 0,
  chunks: 0,
})

async function load() {
  loading.value = true
  try {
    const data = (await client.get('/api/dashboard')).data
    Object.assign(stats, data)
    loaded.value = true
  } catch (e) { /* ignore */ }
  finally { loading.value = false }
}

onMounted(load)
</script>

<style scoped>
.dash-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  display: flex;
  gap: 14px;
  align-items: center;
  min-height: 124px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  box-shadow: var(--app-shadow);
  padding: 20px;
  transition: background-color 0.3s, border-color 0.3s, box-shadow 0.3s, transform 0.2s;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--app-shadow-lg);
}

.stat-card .el-icon {
  width: 42px;
  height: 42px;
  border-radius: var(--app-radius-md);
  color: var(--app-stat-icon-color);
  background: var(--app-stat-icon-bg);
  font-size: 22px;
  flex-shrink: 0;
}

.stat-num {
  color: var(--app-text-heading);
  font-size: 34px;
  font-weight: 800;
  line-height: 1.1;
}

.stat-label {
  margin-bottom: 6px;
  color: var(--app-muted);
  font-size: 13px;
  font-weight: 700;
}

.stat-sub {
  margin-top: 6px;
  color: var(--app-muted-soft);
  font-size: 12px;
}

.quick-panel {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-top: 20px;
}

.charts-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.chart-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.chart-legend {
  display: flex;
  gap: 18px;
  flex-wrap: wrap;
  justify-content: center;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--app-muted);
  font-size: 13px;
  font-weight: 600;
}

.legend-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.legend-dot.success { background: var(--app-success); }
.legend-dot.muted   { background: var(--app-muted-soft); }

.quick-panel h3 {
  margin: 0;
  font-size: 17px;
  color: var(--app-text-heading);
}

.quick-panel p {
  margin: 5px 0 0;
  font-size: 13px;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

@media (max-width: 980px) {
  .dash-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .charts-row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .dash-grid {
    grid-template-columns: 1fr;
  }
  .quick-panel {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
