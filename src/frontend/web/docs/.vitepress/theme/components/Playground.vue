<template>
  <div class="playground">
    <div class="editor-container">
      <div class="editor-header">
        <div class="tabs">
          <button 
            v-for="tab in tabs" 
            :key="tab.name"
            :class="{ active: activeTab === tab.name }"
            @click="activeTab = tab.name"
          >
            {{ tab.label }}
          </button>
        </div>
        <button class="run-btn" @click="executeCode">
          <span class="icon">▶</span> 运行
        </button>
      </div>
      
      <div class="editor-wrapper">
        <div class="monaco-placeholder">
          <pre>{{ code[activeTab] }}</pre>
          <div class="monaco-note">
            编辑器将在预览模式加载，请在完整环境运行
          </div>
        </div>
      </div>
    </div>
    
    <div class="preview-container">
      <div class="preview-header">
        <span>预览</span>
      </div>
      <div class="preview-content">
        <div class="preview-placeholder">
          <div class="preview-message">
            预览内容将在实际环境中显示
          </div>
          <div class="preview-desc">
            AI小鲸是一个对话式组件，需要完整环境才能展示
          </div>
        </div>
      </div>
      
      <div class="console">
        <div class="console-header">
          <span>控制台</span>
          <button @click="clearLogs">清空</button>
        </div>
        <div class="console-content">
          <div v-for="(log, index) in logs" :key="index" class="log-item">
            <span class="log-time">[{{ log.time }}]</span>
            <span :class="['log-message', `log-${log.type}`]">{{ log.message }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'

const props = defineProps({
  initialCode: {
    type: Object,
    default: () => ({
      template: '<div>\n  <button @click="showAI">显示 AI 小鲸</button>\n  \n  <AIBlueking \n    ref="aiBlueking"\n    :url="apiUrl"\n  />\n</div>',
      script: `{
  import AIBlueking from '@blueking/ai-blueking';
  setup() {
    const aiBlueking = ref(null);
    const apiUrl = 'https://your-api-endpoint.com/assistant/';
    
    const showAI = () => {
      aiBlueking.value.show();
    };
    
    return {
      aiBlueking,
      apiUrl,
      showAI
    };
  }
}`,
      style: '.ai-button {\n  background: var(--ai-blueking-primary-color);\n  color: white;\n  border: none;\n  padding: 8px 16px;\n  border-radius: 4px;\n  cursor: pointer;\n}'
    })
  }
})

const tabs = [
  { name: 'template', label: 'Template' },
  { name: 'script', label: 'Script' },
  { name: 'style', label: 'Style' }
]

const activeTab = ref('template')
const code = ref(JSON.parse(JSON.stringify(props.initialCode)))
const logs = ref([
  { time: '12:00:00', message: '加载成功，点击运行按钮执行代码', type: 'info' }
])

function executeCode() {
  try {
    addLog('代码执行中...', 'info')
    setTimeout(() => {
      addLog('AI 小鲸组件已加载', 'success')
    }, 500)
  } catch (error) {
    addLog(`执行错误: ${error.message}`, 'error')
  }
}

function addLog(message, type = 'log') {
  const now = new Date()
  const time = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}`
  logs.value.push({ time, message, type })
}

function clearLogs() {
  logs.value = []
}

onMounted(() => {
  addLog('组件已挂载', 'info')
})
</script>

<style scoped>
.playground {
  display: flex;
  height: 500px;
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  overflow: hidden;
  margin: 24px 0;
}

.editor-container, .preview-container {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 1rem;
  background-color: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-divider);
}

.tabs {
  display: flex;
  gap: 0.5rem;
}

.tabs button {
  padding: 0.25rem 0.75rem;
  background: none;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
}

.tabs button.active {
  background-color: var(--vp-c-brand);
  color: white;
}

.run-btn {
  padding: 0.25rem 0.75rem;
  background-color: var(--vp-c-green);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.run-btn:hover {
  background-color: var(--vp-c-green-dark);
}

.editor-wrapper {
  flex: 1;
  overflow: auto;
  background-color: #1e1e1e;
  color: #d4d4d4;
}

.monaco-placeholder {
  padding: 12px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
}

.monaco-placeholder pre {
  margin: 0;
  white-space: pre-wrap;
}

.monaco-note {
  margin-top: 12px;
  padding: 8px;
  background-color: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  font-size: 12px;
  color: #aaa;
}

.preview-container {
  border-left: 1px solid var(--vp-c-divider);
}

.preview-header {
  padding: 0.5rem 1rem;
  background-color: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-divider);
  font-weight: 500;
}

.preview-content {
  flex: 1;
  padding: 1rem;
  overflow: auto;
  background-color: var(--vp-c-bg);
  display: flex;
  align-items: center;
  justify-content: center;
}

.preview-placeholder {
  text-align: center;
  color: var(--vp-c-text-2);
}

.preview-message {
  font-size: 16px;
  font-weight: 500;
  margin-bottom: 8px;
}

.preview-desc {
  font-size: 14px;
}

.console {
  border-top: 1px solid var(--vp-c-divider);
  height: 150px;
  overflow: auto;
  display: flex;
  flex-direction: column;
}

.console-header {
  display: flex;
  justify-content: space-between;
  padding: 0.5rem 1rem;
  background-color: var(--vp-c-bg-soft);
  border-bottom: 1px solid var(--vp-c-divider);
  font-weight: 500;
  font-size: 14px;
}

.console-header button {
  padding: 0.15rem 0.5rem;
  background: none;
  border: 1px solid var(--vp-c-divider);
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.console-content {
  padding: 0.5rem 1rem;
  font-family: monospace;
  font-size: 13px;
  overflow-y: auto;
  flex: 1;
}

.log-item {
  margin-bottom: 4px;
  line-height: 1.4;
}

.log-time {
  color: var(--vp-c-text-2);
  margin-right: 0.5rem;
  font-size: 12px;
}

.log-info {
  color: var(--vp-c-brand);
}

.log-success {
  color: var(--vp-c-green);
}

.log-error {
  color: var(--vp-c-red);
}

.log-warning {
  color: var(--vp-c-yellow);
}

@media (max-width: 768px) {
  .playground {
    flex-direction: column;
    height: auto;
  }
  
  .editor-container, .preview-container {
    height: 400px;
  }
  
  .preview-container {
    border-left: none;
    border-top: 1px solid var(--vp-c-divider);
  }
}
</style> 