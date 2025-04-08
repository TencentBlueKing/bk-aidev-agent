<template>
  <div class="event-logger">
    <div class="logger-header">
      <h3>事件日志</h3>
      <div class="header-actions">
        <button
          class="action-btn"
          @click="showEventList = true"
        >
          <span class="action-icon">📋</span>
          事件列表
        </button>
        <button
          class="clear-btn"
          @click="$emit('clear')"
        >
          清空日志
        </button>
      </div>
    </div>
    <div class="log-content">
      <div
        v-for="(log, index) in logs"
        class="log-item"
        :key="index"
      >
        <span class="log-time">{{ log.time }}</span>
        <span class="log-type">{{ log.type }}</span>
        <span class="log-data">{{ log.data }}</span>
      </div>
    </div>

    <!-- 事件列表模态框 -->
    <ModalLayout
      v-if="showEventList"
      title="AIBlueking 事件列表"
      @close="showEventList = false"
    >
      <div class="event-list">
        <div
          v-for="event in events"
          class="event-item"
          :key="event.name"
        >
          <div class="event-name">{{ event.name }}</div>
          <div class="event-desc">{{ event.description }}</div>
          <div class="event-params">
            <div class="param-title">参数：</div>
            <div class="param-content">{{ event.params }}</div>
          </div>
        </div>
      </div>
    </ModalLayout>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import ModalLayout from './modal-layout.vue';

  interface EventLog {
    time: string;
    type: string;
    data: string;
  }

  defineProps<{
    logs: EventLog[];
  }>();

  defineEmits<{
    clear: [];
  }>();

  const showEventList = ref(false);

  // AIBlueking 组件的事件列表
  const events = [
    {
      name: 'ai-click',
      description: '点击带有 data-ai 属性的元素时触发',
      params: '点击元素的 data-ai 属性值',
    },
    {
      name: 'choose-prompt',
      description: '选择内置提示词时触发',
      params: '{ id: number; content: string }',
    },
    {
      name: 'clear',
      description: '清空聊天记录时触发',
      params: '无',
    },
    {
      name: 'close',
      description: '关闭聊天窗口时触发',
      params: '无',
    },
    {
      name: 'scroll-load',
      description: '向上滚动加载更多消息时触发',
      params: '无',
    },
    {
      name: 'send',
      description: '发送消息时触发',
      params: '{ content: string; cite?: string; prompt?: string }',
    },
    {
      name: 'shortcut-click',
      description: '点击快捷操作按钮时触发',
      params: '{ type: string; label: string; content: string }',
    },
    {
      name: 'stop',
      description: '停止当前消息流时触发',
      params: '无',
    },
  ];
</script>

<style lang="scss" scoped>
  .event-logger {
    padding: 24px;
    background: #f5f7fa;
    border-radius: 8px;

    .logger-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 16px;

      h3 {
        margin: 0;
        font-size: 18px;
        color: #333;
      }

      .header-actions {
        display: flex;
        gap: 12px;
      }
    }

    .action-btn {
      display: flex;
      gap: 4px;
      align-items: center;
      padding: 4px 12px;
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
        font-size: 14px;
      }
    }

    .clear-btn {
      padding: 4px 12px;
      color: #666;
      cursor: pointer;
      background: #fff;
      border: 1px solid #ddd;
      border-radius: 4px;
      transition: all 0.2s;

      &:hover {
        color: #1482ff;
        border-color: #1482ff;
      }
    }

    .log-content {
      height: 200px;
      overflow-y: auto;
      font-family: 'Fira Code', monospace;
    }

    .log-item {
      display: flex;
      gap: 12px;
      padding: 8px;
      font-size: 13px;
      border-bottom: 1px solid #eee;

      &:last-child {
        border-bottom: none;
      }

      .log-time {
        color: #999;
      }

      .log-type {
        color: #1482ff;
      }

      .log-data {
        color: #666;
        word-break: break-all;
      }
    }
  }

  .event-list {
    .event-item {
      padding: 16px;
      margin-bottom: 16px;
      background: #f5f7fa;
      border-radius: 8px;

      &:last-child {
        margin-bottom: 0;
      }

      .event-name {
        margin-bottom: 8px;
        font-family: 'Fira Code', monospace;
        font-size: 16px;
        font-weight: 600;
        color: #1482ff;
      }

      .event-desc {
        margin-bottom: 12px;
        line-height: 1.6;
        color: #444;
      }

      .event-params {
        display: flex;
        gap: 8px;
        font-size: 14px;

        .param-title {
          color: #666;
        }

        .param-content {
          font-family: 'Fira Code', monospace;
          color: #1a1a1a;
        }
      }
    }
  }
</style>
