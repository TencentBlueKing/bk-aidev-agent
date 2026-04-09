<template>
  <div class="bkai-history-dropdown">
    <div class="history-dropdown-header">
      <h1 class="history-dropdown-header-title">{{ t('历史会话') }}</h1>
      <history-search
        v-model="searchKey"
        :placeholder="t('搜索会话名称')"
      />
    </div>
    <div class="history-dropdown-content">
      <template v-if="groupedSessions.length > 0">
        <history-group
          v-for="group in groupedSessions"
          :key="group.key"
          :current-session-code="currentSessionCode"
          :sessions="group.sessionList"
          :title="group.alias"
        >
          <history-item
            v-for="session in group.sessionList"
            :key="session.sessionCode"
            :is-active="isActiveSession(session.sessionCode)"
            :is-editing="editingSessionCode === session.sessionCode"
            :session="session"
            @click="handleSessionClick"
            @delete="handleSessionDelete"
            @edit="handleSessionEdit"
            @rename-cancel="handleRenameCancel"
            @rename-confirm="handleRenameConfirm"
          />
        </history-group>
      </template>
      <bk-exception
        v-else
        :description="searchKey ? t('搜索为空') : t('暂无对话')"
        scene="part"
        style="margin-top: 100px"
        :type="searchKey ? 'search-empty' : 'empty'"
      ></bk-exception>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';

  import { Exception as BkException } from 'bkui-vue';

  import { t } from '../../../lang';
  import HistoryGroup from './history-group.vue';
  import HistoryItem from './history-item.vue';
  import HistorySearch from './history-search.vue';

  import type { HistoryDropdownEmits, HistoryDropdownProps, TimeBucket, TimeBucketKey } from './types';
  import type { ISession } from '@blueking/chat-helper';

  const props = defineProps<HistoryDropdownProps>();
  const emit = defineEmits<HistoryDropdownEmits>();

  const searchKey = ref('');
  const editingSessionCode = ref<null | string>(null);

  /**
   * 当前会话编码
   */
  const currentSessionCode = computed(() => props.sessionBusinessManager.currentSession.value?.sessionCode);

  /**
   * 分组后的会话列表（按时间分组）
   */
  const groupedSessions = computed(() => {
    const groups: Record<TimeBucketKey, TimeBucket> = {
      today: { key: 'today', alias: t('今天'), sessionList: [] },
      yesterday: { key: 'yesterday', alias: t('昨天'), sessionList: [] },
      '3days': { key: '3days', alias: t('3天前'), sessionList: [] },
      '5days': { key: '5days', alias: t('5天前'), sessionList: [] },
      '1week': { key: '1week', alias: t('1周前'), sessionList: [] },
      before: { key: 'before', alias: t('更早'), sessionList: [] },
    };

    // 1. 搜索过滤
    const filtered = props.sessionBusinessManager.sessionList.value.filter(s =>
      s.sessionName.toLowerCase().includes(searchKey.value.toLowerCase()),
    );

    // 2. 时间分组
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    const days3Ago = new Date(today);
    days3Ago.setDate(today.getDate() - 3);
    const days5Ago = new Date(today);
    days5Ago.setDate(today.getDate() - 5);
    const week1Ago = new Date(today);
    week1Ago.setDate(today.getDate() - 7);

    for (const session of filtered) {
      const sessionDate = new Date(session.createdAt || '');
      const sessionDateOnly = sessionDate.toDateString();

      if (sessionDateOnly === today.toDateString()) {
        groups.today.sessionList.push(session);
      } else if (sessionDateOnly === yesterday.toDateString()) {
        groups.yesterday.sessionList.push(session);
      } else if (sessionDate >= days3Ago && sessionDate > days5Ago) {
        groups['3days'].sessionList.push(session);
      } else if (sessionDate >= days5Ago && sessionDate > week1Ago) {
        groups['5days'].sessionList.push(session);
      } else if (sessionDate >= week1Ago) {
        groups['1week'].sessionList.push(session);
      } else {
        groups.before.sessionList.push(session);
      }
    }

    // 3. 每个分组内按时间倒序排列（最新的在最上面）
    for (const group of Object.values(groups)) {
      group.sessionList.sort((a, b) => {
        const dateA = new Date(a.createdAt || 0).getTime();
        const dateB = new Date(b.createdAt || 0).getTime();
        return dateB - dateA;
      });
    }

    // 4. 只返回有会话的分组
    return Object.values(groups).filter(g => g.sessionList.length > 0);
  });

  /**
   * 检查是否为当前激活的会话
   */
  const isActiveSession = (sessionCode: string) => {
    return currentSessionCode.value === sessionCode;
  };

  /**
   * 处理会话点击
   * 注意：只使用 emit 触发事件，不直接调用 props 回调。
   * 因为组件通过 h() 渲染时，Vue 3 的 emit 机制会自动将事件路由到
   * 父组件传入的 onSessionSwitch 处理器，直接调用会导致双重触发。
   */
  const handleSessionClick = (session: ISession) => {
    if (!isActiveSession(session.sessionCode)) {
      emit('session-switch', session.sessionCode);
      emit('close');
    }
  };

  /**
   * 处理会话编辑
   */
  const handleSessionEdit = (session: ISession) => {
    editingSessionCode.value = session.sessionCode;
  };

  /**
   * 处理会话删除
   */
  const handleSessionDelete = (sessionCode: string) => {
    emit('session-delete', sessionCode);
  };

  /**
   * 处理重命名确认（乐观更新）
   * 先直接修改 sessionList 中的 sessionName，使 UI 立即展示新名称，
   * 再 emit 事件触发后端 API 调用。API 失败时由上层负责回滚。
   */
  const handleRenameConfirm = (sessionCode: string, newName: string) => {
    const session = props.sessionBusinessManager.sessionList.value.find(
      s => s.sessionCode === sessionCode,
    );
    if (session) {
      session.sessionName = newName;
    }
    editingSessionCode.value = null;
    emit('session-rename', sessionCode, newName);
  };

  /**
   * 处理重命名取消
   */
  const handleRenameCancel = () => {
    editingSessionCode.value = null;
  };
</script>

<style lang="scss" scoped>
  .bkai-history-dropdown {
    width: 245px;
    height: 507px;
    background-color: #fff;
    border-radius: 4px;
    overflow-y: auto;
    padding: 8px 4px;

    .history-dropdown-header {
      display: flex;
      flex-direction: column;
      padding: 0 8px;
      font-size: 12px;
      line-height: 22px;
      color: #313238;

      .history-dropdown-header-title {
        font-size: 12px;
        line-height: 22px;
        color: #313238;
        font-weight: 700;
        margin-bottom: 10px;
      }
    }

    .history-dropdown-content {
      margin-top: 10px;
    }
  }
</style>
