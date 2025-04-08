<template>
  <div class="demo-container">
    <div class="demo-header">
      <span class="demo-title">{{ description }}</span>
      <div class="demo-actions">
        <button class="action-button" @click="toggleCode">
          {{ showCode ? '隐藏代码' : '查看代码' }}
        </button>
      </div>
    </div>
    
    <div class="demo-content">
      <slot></slot>
    </div>
    
    <div v-show="showCode" class="demo-footer">
      <slot name="code"></slot>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    description: {
      type: String,
      default: ''
    }
  },
  
  data() {
    return {
      showCode: false
    }
  },
  
  methods: {
    toggleCode() {
      this.showCode = !this.showCode
    }
  }
}
</script>

<style scoped>
.demo-container {
  margin: 24px 0;
  border: 1px solid var(--vp-c-divider);
  border-radius: var(--vp-border-radius);
  overflow: hidden;
}

.demo-header {
  padding: 12px 16px;
  background: var(--vp-c-bg-soft);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.demo-title {
  font-weight: 500;
}

.action-button {
  background: transparent;
  border: 1px solid var(--vp-c-divider);
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 0.85em;
  cursor: pointer;
  transition: all 0.3s ease;
}

.action-button:hover {
  border-color: var(--vp-c-brand);
  color: var(--vp-c-brand);
}

.demo-content {
  padding: 20px;
  background: var(--vp-c-white);
}

.demo-footer {
  border-top: 1px solid var(--vp-c-divider);
  padding: 16px;
  background: var(--vp-c-bg-soft);
}
</style> 