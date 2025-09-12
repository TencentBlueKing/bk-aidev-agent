<template>
  <div class="changelog">
    <div v-for="(version, index) in versions" :key="index" class="version">
      <div class="version-header">
        <h2>{{ version.version }}</h2>
        <span class="date">{{ version.date }}</span>
      </div>
      
      <div v-if="version.important" class="important-notice">
        <div class="important-content" v-html="version.important"></div>
      </div>
      
      <div v-if="version.features" class="section">
        <h3>✨ 新增功能</h3>
        <ul>
          <li v-for="(feature, i) in version.features" :key="i" v-html="feature"></li>
        </ul>
      </div>
      
      <div v-if="version.improvements" class="section">
        <h3>🛠 改进</h3>
        <ul>
          <li v-for="(improvement, i) in version.improvements" :key="i" v-html="improvement"></li>
        </ul>
      </div>
      
      <div v-if="version.fixes" class="section">
        <h3>🐛 修复</h3>
        <ul>
          <li v-for="(fix, j) in version.fixes" :key="j" v-html="fix"></li>
        </ul>
      </div>
      
      <div v-if="version.breaking" class="section breaking">
        <h3>⚠️ 破坏性变动</h3>
        <ul>
          <li v-for="(change, k) in version.breaking" :key="k" v-html="change"></li>
        </ul>
      </div>
      
      <div v-if="version.demo" class="demo-code">
        <div class="demo-title">使用示例</div>
        <div class="demo-content">
          <slot :name="`demo-${index}`"></slot>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  props: {
    versions: {
      type: Array,
      required: true
    }
  }
}
</script>

<style scoped>
.changelog {
  max-width: 900px;
  margin: 0 auto;
}

.version {
  margin-bottom: 3rem;
  padding-bottom: 2rem;
  border-bottom: 1px solid var(--vp-c-divider-light);
}

.version-header {
  display: flex;
  align-items: baseline;
  margin-bottom: 1.5rem;
}

.version-header h2 {
  margin: 0;
  font-size: 1.5rem;
  color: var(--vp-c-brand);
}

.date {
  margin-left: 1rem;
  font-size: 0.9rem;
  color: var(--vp-c-text-2);
}

.section {
  margin-bottom: 1.5rem;
}

.section h3 {
  margin: 1rem 0;
  font-size: 1.1rem;
}

.section.breaking h3 {
  color: var(--vp-c-red);
}

.demo-code {
  margin-top: 2rem;
  border-radius: 8px;
  overflow: hidden;
}

.demo-title {
  padding: 0.75rem 1rem;
  background-color: var(--vp-c-bg-soft);
  font-weight: 600;
  font-size: 0.9rem;
}

.demo-content {
  background-color: var(--vp-c-bg-soft);
  padding: 1rem;
}

.important-notice {
  margin-bottom: 1.5rem;
  padding: 1rem 1.25rem;
  border-left: 4px solid var(--vp-c-red);
  background-color: rgba(255, 59, 48, 0.05);
  border-radius: 4px;
}

.important-content {
  font-weight: 500;
  color: var(--vp-c-red);
  line-height: 1.6;
}

.important-content strong {
  font-weight: 700;
}
</style> 