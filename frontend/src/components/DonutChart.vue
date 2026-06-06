<template>
  <div class="donut-chart" :style="{ width: size + 'px', height: size + 'px' }">
    <svg :viewBox="'0 0 ' + viewBox + ' ' + viewBox" class="donut-svg">
      <!-- Background ring -->
      <circle
        :cx="center" :cy="center" :r="radius"
        fill="none"
        :stroke="trackColor"
        :stroke-width="strokeWidth"
      />
      <!-- Data arcs -->
      <circle
        v-for="(seg, i) in segments"
        :key="i"
        :cx="center" :cy="center" :r="radius"
        fill="none"
        :stroke="seg.color"
        :stroke-width="strokeWidth"
        :stroke-dasharray="arcDash(seg) + ' ' + circumference"
        :stroke-dashoffset="arcOffset(i)"
        :transform="'rotate(-90 ' + center + ' ' + center + ')'"
        class="donut-arc"
        :style="{ transition: 'stroke-dashoffset 0.7s ease, stroke-dasharray 0.7s ease' }"
      />
    </svg>
    <div class="donut-center">
      <span class="donut-total">{{ total }}</span>
      <span class="donut-label">{{ label }}</span>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  segments: { type: Array, default: () => [] },
  label: { type: String, default: '总计' },
  size: { type: Number, default: 160 }
})

const viewBox = 100
const center = 50
const radius = 40
const strokeWidth = 14

const trackColor = 'var(--app-border-soft)'

const circumference = 2 * Math.PI * radius

const total = computed(() => props.segments.reduce((s, seg) => s + seg.value, 0))

function arcDash(seg) {
  if (total.value === 0) return '0 ' + circumference
  const frac = seg.value / total.value
  const len = frac * circumference
  // Ensure minimum visible arc for small values (>0)
  const minArc = seg.value > 0 ? Math.max(len, 1.5) : 0
  return minArc + ' ' + (circumference - minArc)
}

function arcOffset(i) {
  let preceding = 0
  for (let j = 0; j < i; j++) {
    preceding += props.segments[j].value
  }
  if (total.value === 0) return 0
  return -(preceding / total.value) * circumference
}
</script>

<style scoped>
.donut-chart {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.donut-svg {
  width: 100%;
  height: 100%;
}

.donut-arc {
  will-change: stroke-dashoffset, stroke-dasharray;
}

.donut-center {
  position: absolute;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  line-height: 1.2;
}

.donut-total {
  font-size: 26px;
  font-weight: 800;
  color: var(--app-text-heading);
}

.donut-label {
  font-size: 12px;
  color: var(--app-muted);
}
</style>
