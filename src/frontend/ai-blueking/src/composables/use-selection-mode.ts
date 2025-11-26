import { SessionContentRole } from '@blueking/ai-ui-sdk/enums';
import type { ISessionContent } from '@blueking/ai-ui-sdk/types';
import { computed, ref, h } from 'vue';
import { Message as BkMessage } from 'bkui-vue';

import { HIDE_ROLE_LIST } from '../config';
import type { SessionStore } from '../store/sessionStore';
import { copyToClipboard } from '../utils';

interface UseSelectionModeOptions {
  sessionStore: SessionStore;
  sessionContents: { value: ISessionContent[] };
  getChatGroupApi: (data: any) => Promise<any>;
  shareSessionApi: (data: any) => Promise<any>;
  onTransferMessages?: (messageIds: string[]) => void;
  onShareMessages?: (messageIds: string[]) => void;
}

export function useSelectionMode({
  sessionStore,
  sessionContents,
  getChatGroupApi,
  shareSessionApi,
  onTransferMessages,
  onShareMessages,
}: UseSelectionModeOptions) {
  const loading = ref(false);

  // 动态生成聊天群名称
  const chatGroupName = computed(() => {
    const agentName = sessionStore.agentInfo.value?.agentName || '';
    const sessionName = sessionStore.currentSession.value?.sessionName || '';
    const username = sessionStore.agentInfo.value?.chatGroup?.username || '';

    // 构造格式：智能体名称-会话名称-咨询用户
    const parts = [agentName, sessionName, username].filter(part => part.trim() !== '');
    return parts.length > 0 ? parts.join('-') : '小鲸转人工'; // 如果所有部分都为空，使用默认名称
  });

  // 获取所有可见消息的ID
  const visibleMessageIds = computed(() => {
    return sessionContents.value
      .filter(
        (item): item is ISessionContent & { id: number } =>
          !HIDE_ROLE_LIST.includes(item.role) && item.id !== undefined
      )
      .map(item => item.id.toString());
  });

  // 是否全选
  const isSelectAll = computed(() => {
    return sessionStore.isSelectAll(visibleMessageIds.value);
  });

  // 是否半选
  const isIndeterminate = computed(() => {
    return sessionStore.isIndeterminate(visibleMessageIds.value);
  });

  /**
   * 处理确认选择
   */
  const handleConfirmSelection = async () => {
    const selectedMessages = sessionStore.getSelectedMessages();

    // 根据选择模式类型触发不同的事件
    if (sessionStore.selectModeType.value === 'transfer') {
      // 触发 transfer-messages 事件
      onTransferMessages?.(selectedMessages);

      // 调用 getChatGroupApi 方法
      try {
        loading.value = true;
        // 获取选中的消息内容
        const selectedMessageContents = sessionContents.value.filter(
          item =>
            item.id !== undefined &&
            selectedMessages.includes(item.id.toString()) &&
            !HIDE_ROLE_LIST.includes(item.role)
        );

        // 构造消息数组
        const messages = selectedMessageContents.map(item => ({
          role: item.role === SessionContentRole.Ai ? 'ai' : 'user',
          content: item.content,
        })) as import('@blueking/ai-ui-sdk/types').IChatGroupMessage[];

        // 调用 getChatGroupApi
        await getChatGroupApi({
          chat_group_name: chatGroupName.value,
          messages,
          session_code: sessionStore.currentSession.value?.sessionCode || '',
        });
      } catch (error) {
        console.error('调用 getChatGroupApi 失败:', error);
        sessionStore.handleSdkError('getChatGroupApi', error);
      } finally {
        loading.value = false;
      }
    } else if (sessionStore.selectModeType.value === 'share') {
      // 触发 share-messages 事件
      onShareMessages?.(selectedMessages);

      // 调用 shareSessionApi
      loading.value = true;
      try {
        const result = await shareSessionApi({
          session_code: sessionStore.currentSession.value?.sessionCode || '',
          content_ids: selectedMessages,
        });

        const shareCode = result?.share_token || '';
        const url = result?.share_page || '';

        const container = document.querySelector('.ai-blueking-wrapper');
        const shareUrl = `${url}share-page/${shareCode}`;

        // 把 shareUrl 写入剪贴板
        const isSuccess = await copyToClipboard(shareUrl);

        if (isSuccess) {
          BkMessage({
            theme: 'success',
            getContainer: container,
            message: '分享链接已复制到剪贴板',
          });
        } else {
          BkMessage({
            theme: 'error',
            getContainer: container,
            message: '复制失败',
          });
        }
      } catch (error) {
        console.error('调用 shareSessionApi 失败:', error);
        sessionStore.handleSdkError('shareSessionApi', error);
      } finally {
        loading.value = false;
      }
    }
    sessionStore.exitSelectMode();
  };

  /**
   * 处理取消选择
   */
  const handleCancelSelection = () => {
    sessionStore.exitSelectMode();
  };

  /**
   * 处理全选变化
   */
  const handleSelectAllChange = (value: boolean) => {
    sessionStore.toggleSelectAll(visibleMessageIds.value, value);
  };

  /**
   * 进入选择模式
   */
  const enterSelectMode = (type: 'transfer' | 'share') => {
    sessionStore.enterSelectMode(type);
  };

  return {
    // 处理函数
    handleConfirmSelection,
    handleCancelSelection,
    handleSelectAllChange,
    enterSelectMode,

    // 计算属性
    visibleMessageIds,
    isSelectAll,
    isIndeterminate,
    loading,
  };
}
