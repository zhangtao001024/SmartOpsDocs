<template>
  <div class="dashboard-page">
    <div class="overview-hero">
      <div>
        <p class="eyebrow">Operations overview</p>
        <h2 class="page-title">运维概览</h2>
        <p class="hero-copy">集中查看资产在线情况、知识库解析状态和常用入口。</p>
        <div class="hero-metrics" aria-label="运维关键指标">
          <span><strong>{{ stats.servers_online }}</strong> 在线资产</span>
          <span><strong>{{ stats.documents_parsing }}</strong> 解析任务</span>
          <span><strong>{{ stats.documents_failed }}</strong> 失败文档</span>
        </div>
      </div>
      <div class="hero-actions">
        <div class="sync-status">
          <span class="status-dot"></span>
          本地运行
        </div>
        <el-button icon="Refresh" :loading="loading" @click="load">刷新</el-button>
      </div>
    </div>
    <div v-if="loading && !loaded" class="dash-grid">
      <SkeletonBox v-for="i in 4" :key="i" height="124px" />
    </div>
    <div v-else class="dash-grid">
      <div class="stat-card primary">
        <div class="stat-head">
          <div class="stat-label">服务器</div>
          <el-icon><Monitor /></el-icon>
        </div>
        <div>
          <div class="stat-num">{{ stats.servers }}</div>
          <div class="stat-sub">{{ stats.servers_online }} 台在线，{{ stats.servers - stats.servers_online }} 台待确认</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-head">
          <div class="stat-label">K8s 集群</div>
          <el-icon><Connection /></el-icon>
        </div>
        <div>
          <div class="stat-num">{{ stats.clusters }}</div>
          <div class="stat-sub">已接入集群</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-head">
          <div class="stat-label">知识文档</div>
          <el-icon><Document /></el-icon>
        </div>
        <div>
          <div class="stat-num">{{ stats.documents }}</div>
          <div class="stat-sub">{{ stats.chunks }} 个片段 / {{ stats.documents_parsing }} 个解析中</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-head">
          <div class="stat-label">离线 / 未知</div>
          <el-icon><Warning /></el-icon>
        </div>
        <div>
          <div class="stat-num">{{ stats.servers - stats.servers_online }}</div>
          <div class="stat-sub">待确认资产</div>
        </div>
      </div>
    </div>

    <div class="workspace-grid" v-if="loaded">
      <div class="panel chart-panel server-panel">
        <div class="panel-copy">
          <p class="panel-kicker">Server health</p>
          <h3>资产在线状态</h3>
          <p class="muted">优先处理离线和未知资产，保证 AI 问答引用的环境上下文保持有效。</p>
        </div>
        <DonutChart
          label="台资产"
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
      <div class="panel chart-panel knowledge-panel">
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

      <div class="quick-panel panel">
        <div>
          <p class="panel-kicker">Common flows</p>
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
.dashboard-page {
  display: grid;
  gap: 20px;
}

.overview-hero {
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  min-height: 180px;
  padding: 26px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background:
    linear-gradient(90deg, rgba(12, 118, 111, 0.13), transparent 38%, rgba(168, 85, 30, 0.065)),
    repeating-linear-gradient(135deg, rgba(16, 23, 19, 0.035) 0 1px, transparent 1px 16px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.18)),
    var(--app-surface);
  box-shadow: var(--app-shadow);
}

.overview-hero::after {
  position: absolute;
  right: 22px;
  bottom: 18px;
  width: min(38%, 440px);
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--app-primary-border), var(--app-accent));
  content: '';
  opacity: 0.72;
  pointer-events: none;
}

:global(html.dark) .overview-hero {
  background:
    linear-gradient(90deg, rgba(53, 199, 183, 0.12), transparent 42%, rgba(216, 146, 69, 0.05)),
    repeating-linear-gradient(135deg, rgba(220, 230, 221, 0.032) 0 1px, transparent 1px 16px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.015)),
    var(--app-surface);
}

.eyebrow,
.panel-kicker {
  margin: 0 0 8px;
  color: var(--app-accent);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0;
  text-transform: uppercase;
}

.hero-copy {
  max-width: 56ch;
  margin: 10px 0 0;
  color: var(--app-muted);
  line-height: 1.7;
}

.hero-metrics {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 18px;
}

.hero-metrics span {
  display: inline-flex;
  align-items: baseline;
  gap: 6px;
  min-height: 32px;
  padding: 6px 10px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius);
  color: var(--app-muted);
  background: color-mix(in srgb, var(--app-surface-raised) 80%, transparent);
  box-shadow: var(--app-shadow-xs);
  font-size: 12px;
  font-weight: 650;
}

.hero-metrics strong {
  color: var(--app-text-heading);
  font-size: 16px;
  font-variant-numeric: tabular-nums;
}

.hero-actions {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.sync-status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  height: 32px;
  padding: 0 10px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius);
  color: var(--app-muted);
  background: color-mix(in srgb, var(--app-surface-soft) 80%, transparent);
  font-size: 12px;
  font-weight: 680;
}

.status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--app-success);
  box-shadow: 0 0 0 4px var(--app-success-soft);
}

.dash-grid {
  display: grid;
  grid-template-columns: 1.35fr repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  position: relative;
  overflow: hidden;
  display: grid;
  align-content: space-between;
  gap: 18px;
  min-height: 134px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-lg);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.62), rgba(255, 255, 255, 0)),
    var(--app-surface);
  box-shadow: var(--app-shadow);
  padding: 20px;
  transition: background-color 0.3s, border-color 0.3s, box-shadow 0.3s, transform 0.2s;
}

.stat-card::before {
  position: absolute;
  inset: 0 auto 0 0;
  width: 3px;
  background: color-mix(in srgb, var(--app-border-strong) 56%, transparent);
  content: '';
}

:global(html.dark) .stat-card {
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.035), rgba(255, 255, 255, 0)),
    var(--app-surface);
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--app-shadow-hover);
}

.stat-card.primary {
  background:
    linear-gradient(135deg, rgba(12, 118, 111, 0.15), transparent 62%),
    linear-gradient(160deg, transparent 56%, color-mix(in srgb, var(--app-accent-soft) 55%, transparent)),
    var(--app-primary-softer);
}

.stat-card.primary::before {
  background: var(--app-primary);
}

.stat-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.stat-head .el-icon {
  width: 38px;
  height: 38px;
  border-radius: var(--app-radius-md);
  color: var(--app-stat-icon-color);
  background: var(--app-stat-icon-bg);
  font-size: 20px;
  flex-shrink: 0;
}

.stat-num {
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 36px;
  font-weight: 860;
  line-height: 1.1;
  font-variant-numeric: tabular-nums;
}

.stat-label {
  color: var(--app-muted);
  font-size: 13px;
  font-weight: 760;
}

.stat-sub {
  margin-top: 6px;
  color: var(--app-muted-soft);
  font-size: 12px;
  line-height: 1.45;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(300px, 0.95fr) minmax(420px, 1.25fr);
  gap: 16px;
}

.chart-panel {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.server-panel {
  align-items: stretch;
}

.server-panel .donut-chart {
  align-self: center;
}

.knowledge-panel {
  justify-content: center;
}

.panel-copy h3,
.quick-panel h3 {
  margin: 0;
  font-family: var(--app-font-display);
  font-size: 18px;
  color: var(--app-text-heading);
}

.panel-copy p:last-child {
  max-width: 42ch;
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.65;
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

.quick-panel {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  grid-column: 1 / -1;
  gap: 18px;
  background:
    linear-gradient(90deg, var(--app-surface), var(--app-primary-softer) 70%, color-mix(in srgb, var(--app-accent-soft) 48%, transparent));
}

.quick-panel p {
  margin: 5px 0 0;
  font-size: 13px;
}

.quick-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: flex-end;
  justify-content: flex-end;
}

@media (max-width: 980px) {
  .dash-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
  .workspace-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 700px) {
  .overview-hero {
    align-items: stretch;
    flex-direction: column;
    padding: 20px;
  }

  .hero-actions {
    justify-content: flex-start;
  }

  .dash-grid {
    grid-template-columns: 1fr;
  }
  .quick-panel {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
