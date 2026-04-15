<template>
  <div class="execution-summary">
    <div class="execution-summary-header">
      <Input
        v-model="keyword"
        class="execution-summary-header-input"
        clearable
        :placeholder="t('搜索 关键字')"
        @update:model-value="emits('updateKeyword', $event)"
      />
    </div>
    <div class="execution-summary-content">
      <template v-if="messageGroups.length">
        <div
          v-for="(group, index) in messageGroups"
          :key="group.uuid"
          class="execution-summary-content-item"
          @mouseenter="hoverGroupId = group.uuid"
          @mouseleave="hoverGroupId = undefined"
        >
          <div class="content-item-header">
            <span class="timeline-dot" />
            <span
              v-overflow-tips="{ ...commonTippyOptions }"
              class="content-item-title"
            >
              {{
                typeof group.userMessageTitle === 'number' ? formatTime(group.userMessageTitle) : group.userMessageTitle
              }}
            </span>
            <Button
              v-show="hoverGroupId === group.uuid"
              class="content-item-locate"
              text
              theme="primary"
              @click="handleLocate(group)"
            >
              {{ t('在对话中定位') }}
            </Button>
          </div>
          <div class="content-item-messages">
            <MessageRender
              v-for="(message, mIndex) in group.messages"
              :key="mIndex"
              :message="message"
            />
          </div>
          <div
            v-if="index < messageGroups.length - 1"
            class="timeline-line"
          />
        </div>
      </template>
      <template v-else>
        <div class="execution-summary-content-empty">
          <Exception type="empty" />
          <div class="execution-summary-content-empty-text">
            {{ keyword ? t('搜索结果为空') : t('暂无数据') }}
            <Button
              v-if="keyword"
              text
              theme="primary"
              @click="handleClearSearch"
            >
              {{ t('清空搜索') }}
            </Button>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { shallowRef } from 'vue';

  import { Button, Exception, Input } from 'bkui-vue';

  import { useCommonTippyInject, useKeywordProvider } from '../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../directives';
  import { t } from '../../lang/lang';
  import MessageRender from '../chat-message/message-render/message-render.vue';

  import type { MessageGroup } from '../../composables';

  defineProps<{
    messageGroups: MessageGroup[];
  }>();

  const emits = defineEmits<{
    (e: 'locateMessageGroup', uuid: string, group: MessageGroup): void;
    (e: 'updateKeyword', keyword: string): void;
  }>();
  const commonTippyOptions = useCommonTippyInject();
  const { keyword } = useKeywordProvider();

  // const dateValue = deepRef<[Date, Date]>([new Date(), new Date()]);
  const hoverGroupId = shallowRef<string | undefined>(undefined);

  const formatTime = (timestamp?: number) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
  };

  const handleLocate = (group: MessageGroup) => {
    emits('locateMessageGroup', group.uuid, group);
  };
  const handleClearSearch = () => {
    keyword.value = '';
    emits('updateKeyword', '');
  };
</script>
<style lang="scss">
  .execution-summary {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 300px;
    height: 100%;
    padding-bottom: 8px;

    &-header {
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 14px 16px 16px;

      &-date-picker,
      &-input {
        flex: 1;
      }
    }

    &-content {
      display: flex;
      flex: 1;
      flex-direction: column;
      max-height: calc(100% - 54px);
      padding: 0 16px;
      overflow-y: auto;

      &-item {
        position: relative;
        padding-left: 14px;

        .content-item-header {
          display: flex;
          align-items: center;
          height: 22px;
          margin-bottom: 8px;
        }

        .timeline-dot {
          position: absolute;
          top: 8px;
          left: 0;
          width: 6px;
          height: 6px;
          background: #4d4f56;
          border-radius: 50%;
        }

        .content-item-title {
          overflow: hidden;
          text-overflow: ellipsis;
          font-size: 12px;
          font-weight: bold;
          line-height: 22px;
          color: #4d4f56;
          white-space: nowrap;
        }

        .content-item-locate {
          padding-left: 4px;
          margin-left: auto;
          font-size: 12px;
        }

        .content-item-messages {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .timeline-line {
          position: absolute;
          top: 20px;
          bottom: 0;
          left: 2.5px;
          width: 1px;
          background: #eaebf0;
        }
      }

      &-empty {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        width: 100%;

        .bk-exception-page {
          .bk-exception-img {
            height: 200px;
          }
        }
      }
    }
  }
</style>
