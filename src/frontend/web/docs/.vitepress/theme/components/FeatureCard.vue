<template>
  <div class="feature-card">
    <div class="feature-icon">
      <span class="emoji">{{ icon }}</span>
    </div>
    <h3 class="feature-title">{{ title }}</h3>
    <p class="feature-desc">{{ description }}</p>
  </div>
</template>

<script>
export default {
  props: {
    icon: {
      type: String,
      default: '✨'
    },
    title: {
      type: String,
      required: true
    },
    description: {
      type: String,
      default: ''
    }
  }
}
</script>

<style scoped>
.feature-card {
  background: var(--vp-c-bg-soft);
  border-radius: var(--vp-border-radius);
  padding: 24px;
  height: 100%;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

.feature-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 16px rgba(0, 0, 0, 0.1);
  background: linear-gradient(to bottom right, var(--vp-c-bg-soft), white);
}

.feature-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 50px;
  height: 50px;
  background: var(--vp-c-brand-dimm);
  border-radius: 12px;
  margin-bottom: 16px;
}

.emoji {
  font-size: 24px;
}

.feature-title {
  font-size: 18px;
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--vp-c-text-1);
}

.feature-desc {
  color: var(--vp-c-text-2);
  font-size: 14px;
  line-height: 1.6;
  margin: 0;
}
</style> 