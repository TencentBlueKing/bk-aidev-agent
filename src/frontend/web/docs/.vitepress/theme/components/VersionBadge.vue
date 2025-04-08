<template>
  <div class="version-badge">
    <span>v{{ version }}</span>
  </div>
</template>

<script>
import { version } from '../../../../package.json'

export default {
  data() {
    return {
      version
    }
  }
}
</script>

<style scoped>
.version-badge {
  display: inline-block;
  background: var(--vp-c-brand);
  color: white;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: var(--vp-border-radius);
  font-weight: 600;
  transition: all 0.3s ease;
}

.version-badge:hover {
  background: var(--vp-c-brand-dark);
  transform: scale(1.05);
}
</style> 