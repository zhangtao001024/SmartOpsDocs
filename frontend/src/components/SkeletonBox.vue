<template>
  <div class="skeleton-box" :style="{ height: height || '120px' }">
    <div class="skeleton-line w-60"></div>
    <div class="skeleton-line w-100"></div>
    <div class="skeleton-line w-100"></div>
    <div class="skeleton-line w-40"></div>
  </div>
</template>

<script setup>
defineProps({
  height: { type: String, default: '120px' }
})
</script>

<style scoped>
.skeleton-box {
  padding: 16px;
  border: 1px solid var(--app-border);
  border-radius: var(--app-radius-md);
  background: var(--app-surface);
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.skeleton-line {
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

.skeleton-line.w-60  { width: 60%; }
.skeleton-line.w-40  { width: 40%; }
.skeleton-line.w-100 { width: 100%; }

@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}
</style>
