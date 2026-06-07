<template>
  <div class="skeleton-table">
    <div class="skeleton-header">
      <div v-for="i in cols" :key="'h-' + i" class="skeleton-cell h" :style="{ width: colWidth(i) }" />
    </div>
    <div v-for="r in rows" :key="'r-' + r" class="skeleton-row">
      <div v-for="i in cols" :key="'c-' + i" class="skeleton-cell" :style="{ width: colWidth(i) }" />
    </div>
  </div>
</template>

<script setup>
defineProps({
  rows: { type: Number, default: 5 },
  cols: { type: Number, default: 4 }
})

function colWidth(i) {
  // First column wider, others proportional
  return i === 1 ? '180px' : (90 + (i * 10)) + 'px'
}
</script>

<style scoped>
.skeleton-table {
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  overflow: hidden;
}

.skeleton-header {
  display: flex;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid var(--app-border-soft);
  background: var(--app-surface-soft);
}

.skeleton-row {
  display: flex;
  gap: 16px;
  padding: 8px 16px;
  border-bottom: 1px solid var(--app-border-soft);
}

.skeleton-row:last-child {
  border-bottom: 0;
}

.skeleton-cell {
  height: 14px;
  border-radius: 4px;
  background: linear-gradient(
    90deg,
    var(--app-border-soft) 25%,
    var(--app-border) 50%,
    var(--app-border-soft) 75%
  );
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

.skeleton-cell.h {
  height: 16px;
}

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
