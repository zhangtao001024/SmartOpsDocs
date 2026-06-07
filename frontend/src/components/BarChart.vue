<template>
  <div class="bar-chart">
    <div class="bar-chart-title">{{ title }}</div>
    <div class="bars">
      <div v-for="(bar, i) in bars" :key="i" class="bar-row">
        <span class="bar-label">{{ bar.label }}</span>
        <div class="bar-track">
          <div
            class="bar-fill"
            :style="{
              width: barPct(bar) + '%',
              background: bar.color || 'var(--app-primary)',
              transition: 'width 0.6s ease'
            }"
          />
        </div>
        <span class="bar-value">{{ bar.value }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  bars: { type: Array, default: () => [] }
})

const maxVal = computed(() => {
  const m = Math.max(...props.bars.map(b => b.value), 1)
  return m
})

function barPct(bar) {
  return Math.round((bar.value / maxVal.value) * 100)
}
</script>

<style scoped>
.bar-chart {
  padding: 0 4px;
}

.bar-chart-title {
  margin-bottom: 12px;
  color: var(--app-text-heading);
  font-family: var(--app-font-display);
  font-size: 15px;
  font-weight: 820;
}

.bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bar-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.bar-label {
  width: 80px;
  overflow: hidden;
  color: var(--app-muted);
  font-size: 13px;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex-shrink: 0;
}

.bar-track {
  flex: 1;
  height: 22px;
  border: 1px solid var(--app-border-soft);
  border-radius: var(--app-radius);
  background: var(--app-surface-soft);
  overflow: hidden;
}

.bar-fill {
  height: 100%;
  border-radius: var(--app-radius);
  min-width: 4px;
}

.bar-value {
  width: 40px;
  text-align: right;
  color: var(--app-text-heading);
  font-family: var(--app-font-mono);
  font-size: 14px;
  font-weight: 700;
  flex-shrink: 0;
}
</style>
