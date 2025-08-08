<template>
  <div class="bkai-history-panel">
    <div class="history-panel-header">
      <h1 class="history-panel-header-title">{{ t('历史会话') }}</h1>
      <bk-input
        v-model="searchKey"
        behavior="simplicity"
        :placeholder="t('搜索')"
        style="height: 22px"
      >
        <template #suffix>
          <span class="input-icon">
            <search />
          </span>
        </template>
      </bk-input>
    </div>
    <div class="history-panel-content">
      <div
        v-for="item in historyList"
        :key="item.key"
        class="history-panel-content-item"
      >
        <div class="history-panel-content-item-title">
          <span>{{ item.alias }}</span>
        </div>
        <div class="history-panel-content-item-list">
          <div
            v-for="session in item.sessionList"
            :key="session.sessionCode"
            class="history-panel-content-item-list-item"
            :class="{ active: isCurrentSession(session) }"
            @click="handleSessionClick(session)"
          >
            <template v-if="!session.isEdit">
              <bk-overflow-title style="width: calc(100% - 42px)">
                {{ session.sessionName }}
              </bk-overflow-title>
              <span class="history-panel-content-item-list-item-action">
                <i
                  v-bk-tooltips="{
                    content: t('编辑'),
                    boundary: 'parent',
                  }"
                  class="bkai-icon bkai-bianji"
                  @click.stop="handleEdit(session)"
                ></i>
                <bk-pop-confirm
                  :title="t('确认删除会话 ?')"
                  content="删除操作无法撤回，请谨慎操作!"
                  :confirm-config="{
                    theme: 'danger',
                  }"
                  trigger="click"
                  boundary="parent"
                  @confirm="handleDelete(session.sessionCode)"
                >
                  <i
                    v-bk-tooltips="{
                      content: t('删除'),
                      boundary: 'parent',
                    }"
                    class="bkai-icon bkai-shanchu"
                    @click.stop
                  ></i>
                </bk-pop-confirm>
              </span>
            </template>
            <bk-input
              v-else
              :ref="
                (el: HTMLInputElement) => {
                  if (session.isEdit) inputRefs[session.sessionCode] = el;
                }
              "
              v-model="session.sessionName"
              style="width: 100%; height: 28px"
              @blur="handleBlur(session)"
              @enter="handleEnter"
              @click.stop
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import {
    Input as BkInput,
    PopConfirm as BkPopConfirm,
    OverflowTitle as BkOverflowTitle,
  } from 'bkui-vue';
  import { ref, computed, nextTick } from 'vue';

  import { t } from '../lang';
  import { Search } from 'bkui-vue/lib/icon';
  import type { SessionStore } from '../store/sessionStore';
  import type { ISessionEditItem, HistoryItem } from '../store/types';

  const props = defineProps<{
    sessionStore: SessionStore;
  }>();

  const emit = defineEmits<{
    (e: 'close'): void;
  }>();

  const searchKey = ref('');

  const sessionStore = props.sessionStore;

  const inputRefs = ref<Record<string, any>>({});

  const historyList = computed(() => {
    const groups: Record<string, HistoryItem> = {
      today: { key: 'today', alias: t('今天'), sessionList: [] },
      yesterday: { key: 'yesterday', alias: t('昨天'), sessionList: [] },
      before: { key: 'before', alias: t('之前'), sessionList: [] },
    };

    const filteredSessions = sessionStore.sessionList.value.filter(item =>
      item.sessionName.toLowerCase().includes(searchKey.value.toLowerCase())
    );

    for (const session of filteredSessions) {
      const date = new Date(session.createdAt || '');
      const today = new Date();
      const yesterday = new Date();
      yesterday.setDate(yesterday.getDate() - 1);

      if (date.toDateString() === today.toDateString()) {
        groups.today.sessionList.push(session);
      } else if (date.toDateString() === yesterday.toDateString()) {
        groups.yesterday.sessionList.push(session);
      } else {
        groups.before.sessionList.push(session);
      }
    }

    return Object.values(groups).filter(group => group.sessionList.length > 0);
  });

  /**
   * 检查是否为当前会话
   */
  const isCurrentSession = (session: ISessionEditItem) => {
    return sessionStore.currentSession.value?.sessionCode === session.sessionCode;
  };

  /**
   * 处理会话点击事件
   */
  const handleSessionClick = (session: ISessionEditItem) => {
    // 如果不是当前会话，则切换到该会话
    if (!isCurrentSession(session)) {
      sessionStore.switchSessionWithContents(session);
      emit('close');
    }
  };

  const handleDelete = (sessionCode: string) => {
    // 删除会话
    sessionStore.deleteSession(sessionCode);
  };

  const handleBlur = (session: ISessionEditItem) => {
    // 结束编辑并更新会话
    sessionStore.finishEditSession(session.sessionCode, {
      sessionName: session.sessionName,
    });
  };

  const handleEdit = (session: ISessionEditItem) => {
    // 开始编辑会话
    sessionStore.startEditSession(session.sessionCode);

    nextTick(() => {
      const input = inputRefs.value[session.sessionCode];
      if (input) {
        input.focus();
      }
    });
  };

  const handleEnter = (_value: string, event: Event) => {
    // 获取输入框元素
    const input = event.target as HTMLInputElement;
    input.blur();
  };
</script>

<style lang="scss" scoped>
  .bkai-history-panel {
    width: 245px;
    height: 507px;
    background-color: #fff;
    border-radius: 4px;
    overflow-y: auto;
    padding: 8px 4px;
    .history-panel-header {
      display: flex;
      flex-direction: column;
      padding: 0 8px;
      font-size: 12px;
      line-height: 22px;
      color: #313238;
      .history-panel-header-title {
        font-size: 12px;
        line-height: 22px;
        color: #313238;
        font-weight: 700;
        margin-bottom: 10px;
      }
    }
    .history-panel-content {
      margin-top: 10px;
      .history-panel-content-item {
        .history-panel-content-item-title {
          font-size: 12px;
          line-height: 20px;
          color: #979ba5;
          margin-bottom: 4px;
          padding: 0 8px;
        }
        .history-panel-content-item-list {
          .history-panel-content-item-list-item {
            display: flex;
            align-items: center;
            justify-content: space-between;
            font-size: 12px;
            height: 28px;
            color: #4d4f56;
            padding: 0 8px;
            border-radius: 2px;
            cursor: pointer;
            .history-panel-content-item-list-item-action {
              color: #979ba5;
              display: flex;
              align-items: center;
              gap: 4px;
              .bkai-icon {
                font-size: 14px;
              }
            }
            &:hover {
              background: #f0f1f5;
            }
            &.active {
              background: #e1ecff;
              color: #3a84ff;
              font-weight: 700;
            }
          }
        }
      }
    }
  }
</style>
