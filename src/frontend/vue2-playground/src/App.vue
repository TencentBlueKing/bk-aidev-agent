<template>
  <div id="app">
    <header class="header">
      <h1>AI 小鲸 Vue2 Playground</h1>
      <p>版本: {{ version }}</p>
    </header>
    
    <div class="main-content">
      <div class="controls">
        <button @click="handleShow" class="btn">显示 AI 小鲸</button>
        <button @click="handleStop" class="btn">停止生成</button>
        <button @click="handleSendMessage" class="btn">发送消息</button>
        <button @click="logSessionContents" class="btn btn-debug">调试会话内容</button>
      </div>
      
      <div class="conversation-info">
        <h3>会话内容 ({{ messagesCount }}条消息)</h3>
        <pre v-if="messagesCount > 0">{{ JSON.stringify(sessionContents, null, 2) }}</pre>
        <p v-else>暂无会话内容</p>
        <p>数组长度: {{ sessionContents ? sessionContents.length : 0 }}</p>
      </div>
      
      <!-- 引入测试组件 -->
      <test-component />
    </div>
    
    <!-- AI 小鲸组件 -->
    <ai-blueking
      ref="aiBlueking"
      :url="aiUrl"
      :title="'AI 小鲸 Vue2 测试'"
      :hello-text="'我是 AI 小鲸 Vue2 版本'"
      :shortcuts="shortcuts"
      @close="onClose"
      @show="onShow"
      @stop="onStop"
      @shortcut-click="onShortcutClick"
    />
  </div>
</template>

<script>
// 导入 Vue2 版本的 AI 小鲸组件
import AiBlueking from '@blueking/ai-blueking/vue2';
import '@blueking/ai-blueking/dist/vue2/style.css';

// 导入测试组件
import TestComponent from './components/TestComponent.vue';

export default {
  name: 'App',
  components: {
    AiBlueking,
    TestComponent
  },
  data() {
    return {
      version: '0.5.3-beta.6',
      testMessage: '你好，AI 小鲸！',
      shortcuts: [
        {
          type: 'explanation',
          label: '解释代码',
          prompt: '请解释下面的代码：',
        },
        {
          type: 'translate',
          label: '翻译内容',
          prompt: '请翻译下面的内容：',
        },
        {
          type: 'custom',
          label: '优化代码',
          prompt: '请优化下面的代码：',
        }
      ]
    };
  },
  computed: {
    sessionContents() { 
      return this.$refs.aiBlueking?.sessionContents || [];
    },
    messagesCount() {
      return this.sessionContents.length || 0;
    },
    aiUrl() {
      console.log(process.env, process.env.VUE_APP_BK_API_URL_TMPL, process.env.VUE_APP_BK_API_GATEWAY_NAME);
      const prefix = (process.env.VUE_APP_BK_API_URL_TMPL || '')
        .replace('{api_name}', process.env.VUE_APP_BK_API_GATEWAY_NAME || '')
        .replace(/^(http|https):/, `${window.location.protocol}`);

      const url = `${prefix}/prod/bk_plugin/plugin_api/assistant/`;
      return url;
    }
  },
  methods: {
    handleShow() {
      this.$refs.aiBlueking?.handleShow();
    },
    handleStop() {
      this.$refs.aiBlueking?.handleStop();
    },
    handleSendMessage() {
      this.$refs.aiBlueking?.handleSendMessage(this.testMessage);
    },
    onClose() {
      console.log('AI 小鲸已关闭');
    },
    onShow() {
      console.log('AI 小鲸已显示');
    },
    onStop() {
      console.log('AI 小鲸已停止生成');
    },
    onShortcutClick(shortcut) {
      console.log('快捷操作已点击', shortcut);
    },
    logSessionContents() {
      const contents = this.$refs.aiBlueking?.sessionContents;
      console.log('会话内容类型:', typeof contents);
      console.log('是否为数组:', Array.isArray(contents));
      console.log('会话内容:', contents);
      console.log('长度:', contents ? contents.length : 0);
      
      if (contents && Array.isArray(contents)) {
        alert(`会话内容数组长度: ${contents.length}`);
      } else {
        alert('会话内容不是数组或为空');
      }
    }
  },
  mounted() {
    // 添加一个定时器来监控 sessionContents 变化
    this.intervalId = setInterval(() => {
      if (this.$refs.aiBlueking && this.$refs.aiBlueking.sessionContents) {
        console.log('定时检查会话内容:', this.$refs.aiBlueking.sessionContents);
      }
    }, 3000);
  },
  beforeDestroy() {
    // 清除定时器
    if (this.intervalId) {
      clearInterval(this.intervalId);
    }
  }
};
</script>

<style lang="scss" scoped>
#app {
  font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
  margin: 0;
  padding: 20px;
}

.header {
  text-align: center;
  margin-bottom: 30px;
  
  h1 {
    margin-bottom: 10px;
  }
  
  p {
    color: #666;
  }
}

.main-content {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
  border: 1px solid #eaeaea;
  border-radius: 8px;
  background-color: #f9f9f9;
}

.controls {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.btn {
  padding: 8px 16px;
  background-color: #3a84ff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  transition: background-color 0.3s;
  
  &:hover {
    background-color: #2a64cf;
  }
}

.conversation-info {
  h3 {
    margin-bottom: 10px;
  }
  
  pre {
    background-color: #f1f1f1;
    padding: 15px;
    border-radius: 4px;
    overflow: auto;
    max-height: 300px;
  }
}

.btn-debug {
  background-color: #e67e22;
  
  &:hover {
    background-color: #d35400;
  }
}
</style> 