<template>
  <div class="dynamic-playground">
    <DemoHeader
      description="AI小鲸弹窗组件连接AI智能体，体验实时对话能力"
      title="实时会话样例"
    />
    <div class="demo-content">
      <div class="feature-cards">
        <div class="feature-card">
          <div class="card-icon">💬</div>
          <h3>实时对话</h3>
          <p>支持流式输出，让对话更加自然流畅</p>
        </div>
        <div class="feature-card">
          <div class="card-icon">📎</div>
          <h3>内容引用</h3>
          <p>选中文本即可快速引用并提问</p>
        </div>
        <div class="feature-card">
          <div class="card-icon">⚡️</div>
          <h3>快捷操作</h3>
          <p>支持快速翻译、解释等常用功能</p>
        </div>
      </div>

      <div class="article-section">
        <div class="article-card">
          <h2>使用示例</h2>
          <p>👇 试试选中下面的文本，体验快捷操作功能</p>
          <div class="article">
            <h3>BK AI: Revolutionizing the Future of Artificial Intelligence</h3>
            <p>{{ article }}</p>
          </div>
          <div class="quick-actions">
            <button
              class="action-btn"
              @click="
                quickActions(
                  { label: '解释', key: 'explanation', prompt: '解释一下内容： {{ SELECTED_TEXT }}' },
                  'BK AI: Revolutionizing the Future of Artificial Intelligence',
                )
              "
            >
              <span class="action-icon">💡</span>
              解释标题
            </button>
            <button
              class="action-btn"
              @click="
                quickActions(
                  { label: '翻译', key: 'translate', prompt: '翻译一下内容： {{ SELECTED_TEXT }}' },
                  'BK AI: Revolutionizing the Future of Artificial Intelligence',
                )
              "
            >
              <span class="action-icon">🌐</span>
              翻译标题
            </button>
          </div>

          <!-- 调试模式下显示日志 -->
          <EventLogger
            v-if="isDebugMode"
            :logs="eventLogs"
            @clear="clearLogs"
          />
        </div>
      </div>
    </div>

    <div>
      <div>
        <AIBlueking
      ref="aiBlueking"
      :request-options="{
        data: {
          preset: 'QA',
        },
      }"
      :prompts="prompts"
      :url="url"
      teleport-to="body"
      @close="handleClose"
      @shortcut-click="handleShortcutClick"
      @show="handleShowAi"
      @stop="handleStop"
    />
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { ref, computed } from 'vue';

  import AIBlueking, { AIBluekingExpose, ShortCut } from '../src/vue3.ts';
  import DemoHeader from './components/demo-header.vue';
  import EventLogger from './components/event-logger.vue';
  import { useEventLogger } from './composables/use-event-logger.ts';

  const prompts = ['请推荐几本关于人工智能的书籍。', '请用 Python 写一个简单的 Hello World 程序。'];

  // 检查 URL 中是否包含 debug=true
  const isDebugMode = computed(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('debug') === 'true';
  });

  const aiBlueking = ref<AIBluekingExpose | null>(null);

  const prefix = (process.env.BK_API_URL_TMPL || '')
    .replace('{api_name}', process.env.BK_API_GATEWAY_NAME || '')
    .replace(/^(http|https):/, `${window.location.protocol}`);

  const url = `${prefix}/prod/bk_plugin/plugin_api/assistant/`;

  // 事件日志相关
  const { eventLogs, addLog, clearLogs } = useEventLogger();

  // 修改现有的事件处理方法，添加日志记录
  const handleShowAi = () => {
    addLog('show', 'AI chat window opened');
  };

  const handleClose = () => {
    addLog('close', 'AI chat window closed');
  };

  const quickActions = (shortcut: { label: string; prompt: string; key: string }, cite: string) => {
    aiBlueking.value?.handleShow();

    aiBlueking.value?.sendChat({
      message: shortcut.label,
      cite,
      shortcut,
    });
    addLog('quick-action', { message: shortcut.label, cite, prompt: shortcut.prompt });
  };

  const handleShortcutClick = (shortcut: ShortCut) => {
    addLog('shortcut-click', shortcut);
  };

  // const handleAiClick = (data: any) => {
  //   addLog('ai-click', data);
  // };

  // // 清空消息
  // const handleClear = () => {
  //   addLog('clear', 'All messages cleared');
  // };

  // // 发送消息
  // const handleSend = (args: any) => {
  //   addLog('send', { content: args.content, cite: args.cite, prompt: args.prompt });
  // };

  // 暂停聊天
  const handleStop = () => {
    addLog('stop', 'Chat stream stopped');
  };

  const article = `In the rapidly evolving world of technology...`; // 将原有的长文本提取为变量
</script>

<style lang="scss" scoped>
  .dynamic-playground {
    max-width: 1200px;
    margin: 0 auto;
  }

  .feature-cards {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 24px;
    margin-bottom: 40px;
  }

  .feature-card {
    padding: 24px;
    text-align: center;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
    transition: transform 0.2s;

    &:hover {
      transform: translateY(-4px);
    }

    .card-icon {
      margin-bottom: 16px;
      font-size: 32px;
    }

    h3 {
      margin-bottom: 12px;
      font-size: 18px;
      color: #333;
    }

    p {
      line-height: 1.6;
      color: #666;
    }
  }

  .article-section {
    position: relative;
    margin-bottom: 40px;

    :deep(.event-logger) {
      margin-top: 24px;
    }
  }

  .article-card {
    padding: 32px;
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);

    &.mt20 {
      margin-top: 20px;
    }

    h2 {
      margin-bottom: 16px;
      font-size: 24px;
      color: #333;
    }

    > p {
      margin-bottom: 24px;
      color: #666;
    }
  }

  .article {
    padding: 24px;
    margin-bottom: 24px;
    background: #f5f7fa;
    border-radius: 8px;

    h3 {
      margin-bottom: 16px;
      font-size: 20px;
      color: #333;
    }

    p {
      line-height: 1.8;
      color: #666;

      &::selection {
        color: #fff;
        background: rgba(20, 130, 255, 0.8);
      }
    }
  }

  .quick-actions {
    display: flex;
    gap: 16px;
  }

  .action-btn {
    display: flex;
    gap: 8px;
    align-items: center;
    padding: 8px 16px;
    color: #1482ff;
    cursor: pointer;
    background: rgba(20, 130, 255, 0.1);
    border: 1px solid rgba(20, 130, 255, 0.2);
    border-radius: 4px;
    transition: all 0.2s;

    &:hover {
      background: rgba(20, 130, 255, 0.15);
      border-color: rgba(20, 130, 255, 0.3);
    }

    .action-icon {
      font-size: 16px;
    }
  }

  .floating-triggers {
    position: fixed;
    right: 20px;
    bottom: 20px;
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .ai-image {
    width: 64px;
    height: 64px;
    cursor: pointer;
    transition: transform 0.3s;

    &:hover {
      transform: scale(1.1);
    }
  }

  .float-image {
    position: relative;
    right: -32px;
    transition: right 0.3s;

    &:hover {
      right: 0;
    }
  }
</style>
