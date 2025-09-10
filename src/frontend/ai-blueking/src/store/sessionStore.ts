import type { ISession, ISessionContent, IAgentInfo } from '@blueking/ai-ui-sdk/types';
import { ref } from 'vue';

import { HIDE_ROLE_LIST } from '../config';
import { t } from '../lang';
import { uuid as generateUuid } from '../utils';

import type { ISessionEditItem, SdkApi } from './types';

// 错误事件发射器类型
export interface SdkErrorEvent {
  apiName: string;
  code: number;
  message: string;
  data: unknown;
}

// 错误回调函数类型
export type SdkErrorCallback = (error: SdkErrorEvent) => void;

/**
 * 使用会话管理 Store
 */
export function useSessionStore() {
  const sessionList = ref<ISessionEditItem[]>([]);
  const currentSession = ref<ISessionEditItem | null>(null);
  const sessionContentLoading = ref<boolean>(false);
  const sessionUpdateCounter = ref<Record<string, number>>({});
  let sdkApi: Partial<SdkApi> = {};

  // 存储会话的原始值
  const originalSessionValues = ref<Record<string, ISessionEditItem>>({});

  // 消息选择模式状态
  const isSelectMode = ref(false);
  const selectedMessages = ref<Set<string>>(new Set());
  const selectModeType = ref<'transfer' | 'share' | null>(null);

  // 错误回调函数
  let sdkErrorCallback: SdkErrorCallback | null = null;

  /**
   * 注册错误回调函数
   * @param callback 错误回调函数
   */
  const registerErrorCallback = (callback: SdkErrorCallback) => {
    sdkErrorCallback = callback;
  };

  /**
   * 进入选择模式
   * @param type 选择模式类型
   */
  const enterSelectMode = (type: 'transfer' | 'share') => {
    isSelectMode.value = true;
    selectModeType.value = type;
    selectedMessages.value = new Set();
  };

  /**
   * 退出选择模式
   */
  const exitSelectMode = () => {
    isSelectMode.value = false;
    selectModeType.value = null;
    selectedMessages.value = new Set();
  };

  /**
   * 切换消息选择状态
   * @param messageId 消息ID
   */
  const toggleMessageSelection = (messageId: string) => {
    const newSet = new Set(selectedMessages.value);
    if (newSet.has(messageId)) {
      newSet.delete(messageId);
    } else {
      newSet.add(messageId);
    }
    selectedMessages.value = newSet;
  };

  /**
   * 全选/取消全选
   * @param messageIds 所有可选择的消息ID数组
   * @param selectAll 是否全选
   */
  const toggleSelectAll = (messageIds: string[], selectAll: boolean) => {
    if (selectAll) {
      // 全选
      const newSet = new Set(selectedMessages.value);
      messageIds.forEach(id => newSet.add(id));
      selectedMessages.value = newSet;
    } else {
      // 取消全选
      const newSet = new Set(selectedMessages.value);
      messageIds.forEach(id => newSet.delete(id));
      selectedMessages.value = newSet;
    }
  };

  /**
   * 检查是否全选
   * @param messageIds 所有可选择的消息ID数组
   * @returns 是否全选
   */
  const isSelectAll = (messageIds: string[]): boolean => {
    if (messageIds.length === 0) return false;
    return messageIds.every(id => selectedMessages.value.has(id));
  };

  /**
   * 检查是否部分选择（半选状态）
   * @param messageIds 所有可选择的消息ID数组
   * @returns 是否部分选择
   */
  const isIndeterminate = (messageIds: string[]): boolean => {
    if (messageIds.length === 0) return false;
    const selectedCount = messageIds.filter(id => selectedMessages.value.has(id)).length;
    return selectedCount > 0 && selectedCount < messageIds.length;
  };

  /**
   * 获取已选择的消息ID数组
   * @returns 已选择的消息ID数组
   */
  const getSelectedMessages = (): string[] => {
    return Array.from(selectedMessages.value);
  };

  /**
   * 检查消息是否被选择
   * @param messageId 消息ID
   * @returns 是否被选择
   */
  const isMessageSelected = (messageId: string): boolean => {
    return selectedMessages.value.has(messageId);
  };

  /**
   * 处理 SDK API 错误
   * @param apiName API 名称
   * @param error 错误对象
   */
  const handleSdkError = (apiName: string, error: unknown) => {
    if (!sdkErrorCallback) {
      console.error(`SDK API ${apiName} error:`, error);
      return;
    }

    // 提取错误信息，兼容内部拦截器的错误格式
    const errorObj = error as any;
    const message =
      errorObj?.error?.message || errorObj?.message || errorObj?.response?.message || '系统错误';
    const code = errorObj?.error?.code || errorObj?.code || errorObj?.response?.code || -1;
    const data = errorObj?.error?.data || errorObj?.data || errorObj?.response?.data || error;

    const errorEvent: SdkErrorEvent = {
      apiName,
      code,
      message,
      data,
    };

    sdkErrorCallback(errorEvent);
  };

  const agentInfo = ref<IAgentInfo>({
    agentName: '',
    conversationSettings: {
      openingRemark: '',
      predefinedQuestions: [],
    },
    promptSetting: {
      content: [],
    },
  });
  /**
   * 检查 SDK 方法是否已注册
   * @param methodName SDK 方法名
   * @throws Error 如果方法未注册
   */
  const checkSdkMethod = <T extends keyof SdkApi>(methodName: T): NonNullable<SdkApi[T]> => {
    if (!sdkApi[methodName]) {
      throw new Error(`${methodName} not registered`);
    }

    return sdkApi[methodName] as NonNullable<SdkApi[T]>;
  };

  /**
   * 完整的会话切换流程
   * @param session 目标会话
   */
  const switchSessionWithContents = async (session: ISession | ISessionEditItem) => {
    try {
      const setChain = checkSdkMethod('setCurrentSessionChain');

      await setChain(session);
      setCurrentSession(session);
    } catch (error) {
      console.error('Failed to switch session:', error);
      handleSdkError('setCurrentSessionChain', error);
      throw error;
    }
  };

  /**
   * 设置会话列表
   * @param sessions 会话列表
   */
  const setSessionList = (sessions: ISession[]) => {
    sessionList.value = sessions.map(item => ({ ...item, isEdit: false }));

    // 如果当前有会话，更新当前会话的信息
    if (currentSession.value) {
      const updatedCurrentSession = sessions.find(
        s => s.sessionCode === currentSession.value?.sessionCode
      );
      if (updatedCurrentSession) {
        currentSession.value = {
          ...currentSession.value,
          ...updatedCurrentSession,
          isEdit: currentSession.value.isEdit,
        };
      }
    }
  };

  /**
   * 添加会话
   * @param session 会话信息
   */
  const addSession = (session: ISession) => {
    const newSession = { ...session, isEdit: false };

    sessionList.value.unshift(newSession);

    return newSession;
  };

  /**
   * 创建新会话
   * @param sessionCode 可选的会话代码，如果不提供则自动生成
   * @returns Promise<ISessionEditItem> 新创建的会话
   */
  const addNewSession = async (sessionCode?: string) => {
    // 如果没有提供 sessionCode，则生成新的会话代码
    const newSessionCode = sessionCode || generateUuid();

    // 所有新会话统一命名为"新会话"
    const sessionName = t('新会话');

    const newSession: ISession = {
      sessionCode: newSessionCode,
      sessionName,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };

    // 添加到本地会话列表
    const session = addSession(newSession);

    // 创建 session 并同步到后台
    const plusSession = checkSdkMethod('plusSessionApi');

    try {
      await plusSession(session);
    } catch (error) {
      handleSdkError('plusSessionApi', error);
      throw error;
    }

    // 切换到新会话
    await switchSessionWithContents(session);

    return session;
  };

  /**
   * 开始编辑会话
   * @param sessionCode 会话代码
   */
  const startEditSession = (sessionCode: string) => {
    const session = sessionList.value.find(s => s.sessionCode === sessionCode);

    if (session) {
      // 保存原始值
      originalSessionValues.value[sessionCode] = { ...session };
      // 设置编辑状态
      updateSession(sessionCode, { isEdit: true }, { syncBackend: false });
    }
  };

  /**
   * 结束编辑会话
   * @param sessionCode 会话代码
   * @param updates 更新内容
   */
  const finishEditSession = async (sessionCode: string, updates: Partial<ISessionEditItem>) => {
    const originalSession = originalSessionValues.value[sessionCode];

    if (!originalSession) {
      return null;
    }

    // 检查内容是否有实际变化（与原始值比较）
    const hasContentChanged = Object.entries(updates).some(([key, value]) => {
      if (key === 'isEdit') return false;

      return originalSession[key as keyof ISessionEditItem] !== value;
    });

    // 更新会话
    const result = await updateSession(
      sessionCode,
      { ...updates, isEdit: false },
      { syncBackend: hasContentChanged }
    );

    // 清理原始值
    delete originalSessionValues.value[sessionCode];

    return result;
  };

  /**
   * 更新会话
   * @param sessionCode 会话代码
   * @param updates 部分更新内容
   * @param options 更新选项
   */
  const updateSession = async (
    sessionCode: string,
    updates: Partial<ISessionEditItem>,
    options: {
      syncBackend?: boolean;
      forceSync?: boolean;
    } = {}
  ) => {
    const { syncBackend = true, forceSync = false } = options;
    const index = sessionList.value.findIndex(s => s.sessionCode === sessionCode);

    if (index === -1) {
      return null;
    }

    const oldSession = sessionList.value[index];
    const updatedSession = { ...oldSession, ...updates };

    // 更新本地状态
    sessionList.value[index] = updatedSession;
    // 强制触发响应式更新
    sessionList.value = [...sessionList.value];

    // 增加会话更新计数器
    if (!sessionUpdateCounter.value[sessionCode]) {
      sessionUpdateCounter.value[sessionCode] = 0;
    }
    sessionUpdateCounter.value[sessionCode]++;

    // 如果更新的是当前会话，也更新 currentSession
    if (currentSession.value && currentSession.value.sessionCode === sessionCode) {
      currentSession.value = { ...currentSession.value, ...updates };
    }

    // 判断是否需要同步到后端
    if ((syncBackend && !updates.isEdit) || forceSync) {
      try {
        const modifySession = checkSdkMethod('modifySessionApi');
        // 同步到后端时，确保 isEdit 为 false
        const sessionToSync = { ...updatedSession, isEdit: false };

        await modifySession(sessionToSync);
      } catch (error) {
        console.error('Failed to sync session to backend:', error);
        handleSdkError('modifySessionApi', error);
        // 如果同步失败，回滚本地状态
        sessionList.value[index] = oldSession;
        sessionList.value = [...sessionList.value];
        if (currentSession.value && currentSession.value.sessionCode === sessionCode) {
          currentSession.value = oldSession;
        }
      }
    }

    return updatedSession;
  };

  /**
   * 删除会话
   * @param sessionCode 会话代码
   * @returns 如果删除的是当前会话，返回下一个可用的会话；否则返回 null
   */
  const deleteSession = async (sessionCode: string): Promise<ISessionEditItem | null> => {
    const deleteApi = checkSdkMethod('deleteSessionApi');

    try {
      await deleteApi(sessionCode);
    } catch (error) {
      handleSdkError('deleteSessionApi', error);
      throw error;
    }

    const index = sessionList.value.findIndex(s => s.sessionCode === sessionCode);

    if (index === -1) {
      return null;
    }

    const isDeletingCurrentSession = currentSession.value?.sessionCode === sessionCode;

    // 先从列表中删除
    sessionList.value.splice(index, 1);

    // 如果删除的是当前会话，需要切换到新会话
    if (isDeletingCurrentSession) {
      // 如果还有其他会话
      if (sessionList.value.length > 0) {
        // 优先选择今天的会话，否则选择第一个会话
        const today = new Date().toDateString();
        const todaySessions = sessionList.value.filter(
          s => new Date(s.createdAt || '').toDateString() === today
        );
        const nextSession = todaySessions.length > 0 ? todaySessions[0] : sessionList.value[0];

        await switchSessionWithContents(nextSession);

        return nextSession;
      }

      // 如果没有其他会话，则创建一个新会话
      await initSession(false);

      return null;
    }

    // 如果删除的不是当前会话，则不需要切换
    return null;
  };

  /**
   * 设置当前会话（仅前端状态）
   * @param session 会话信息
   */
  const setCurrentSession = (session: ISession | ISessionEditItem) => {
    // 查找会话是否已在列表中
    const existingSession = sessionList.value.find(s => s.sessionCode === session.sessionCode);

    if (existingSession) {
      // 如果会话已存在，直接设置为当前会话
      currentSession.value = existingSession;
    } else {
      // 如果会话不存在，添加到列表并设置为当前会话
      const newSession = addSession(session);

      currentSession.value = newSession;
    }
  };

  /**
   * 注册 SDK 方法
   * @param methods 部分 SDK 方法
   */
  const registerSdkMethods = (methods: Partial<SdkApi>) => {
    sdkApi = methods;
  };

  /**
   * 初始化会话
   * @param isInitChat 是否初始化聊天
   * @param loadRecentSession 是否加载最近的会话（即使有内容）
   * @returns Promise<{
   *   openingRemark: string
   *   predefinedQuestions: string[]
   * }>
   */
  const initSession = async (isInitChat = true, loadRecentSession = false) => {
    // 获取会话列表
    let sessions = sessionList.value;

    if (isInitChat) {
      const getSessions = checkSdkMethod('getSessionsApi');
      try {
        sessions = await getSessions();
        setSessionList(sessions);
      } catch (error) {
        handleSdkError('getSessionsApi', error);
        throw error;
      }
    }

    let targetSession: ISessionEditItem | null = null;
    let targetSessionContents: ISessionContent[] = [];

    // 如果有现有会话，检查最近的一条会话
    if (sessions.length > 0) {
      // 按创建时间降序排序，获取最新的会话
      const latestSession = sessions.sort(
        (a, b) => new Date(b.createdAt || '').getTime() - new Date(a.createdAt || '').getTime()
      )[0];

      // 获取最新会话的内容
      const getContents = checkSdkMethod('getSessionContentsApi');

      try {
        targetSessionContents = await getContents(latestSession.sessionCode);
      } catch (error) {
        handleSdkError('getSessionContentsApi', error);
        throw error;
      }

      // 检查会话内容是否为空（检查每个内容的 content 字段）
      const hasContent = targetSessionContents
        .filter(item => !HIDE_ROLE_LIST.includes(item.role))
        .some(item => item.content && item.content.trim() !== '');

      // 如果内容为空，直接使用这个会话；如果 loadRecentSession 为 true，也使用这个会话
      if (!hasContent || loadRecentSession) {
        targetSession = { ...latestSession, isEdit: false };
      }
    }

    // 如果没有找到合适的现有会话，创建新会话
    if (!targetSession) {
      targetSession = await addNewSession();
      targetSessionContents = [];
    } else {
      // 使用现有会话
      const setContents = checkSdkMethod('setSessionContents');

      setContents(targetSessionContents);
      switchSessionWithContents(targetSession);
    }

    if (!agentInfo.value || isInitChat) {
      // 获取会话设置
      const getAgentInfo = checkSdkMethod('getAgentInfoApi');

      try {
        const agentInfoData = await getAgentInfo();

        Object.assign(agentInfo.value, agentInfoData);
      } catch (error) {
        // 如果 getAgentInfo 出错，抛出统一的错误事件
        handleSdkError('getAgentInfoApi', error);
        throw error;
      }
    }

    // 处理角色设置
    if (agentInfo.value?.promptSetting?.content?.length && targetSessionContents.length === 0) {
      // 只要已有内容，则不需要再自动塞入 prompt
      const handleRole = checkSdkMethod('handleCompleteRole');

      try {
        await handleRole(targetSession.sessionCode, agentInfo.value.promptSetting.content);
      } catch (error) {
        handleSdkError('handleCompleteRole', error);
        throw error;
      }
    }

    return {
      conversationSettings: agentInfo.value?.conversationSettings,
    };
  };

  /**
   * 获取最新的会话列表
   * @returns Promise<ISessionEditItem[]> 会话列表
   */
  const getSessionList = async () => {
    const getSessions = checkSdkMethod('getSessionsApi');
    let sessions: ISession[];
    try {
      sessions = await getSessions();
      setSessionList(sessions);
    } catch (error) {
      handleSdkError('getSessionsApi', error);
      throw error;
    }

    // 如果当前有会话，更新当前会话的信息
    if (currentSession.value) {
      const updatedCurrentSession = sessions.find(
        s => s.sessionCode === currentSession.value?.sessionCode
      );
      if (updatedCurrentSession) {
        currentSession.value = {
          ...currentSession.value,
          ...updatedCurrentSession,
          isEdit: currentSession.value.isEdit,
        };
      }
    }

    // 增加所有会话的更新计数器以触发相关组件刷新
    sessions.forEach(session => {
      if (!sessionUpdateCounter.value[session.sessionCode]) {
        sessionUpdateCounter.value[session.sessionCode] = 0;
      }
      sessionUpdateCounter.value[session.sessionCode]++;
    });

    return sessionList.value;
  };

  return {
    sessionList,
    currentSession,
    setSessionList,
    addSession,
    addNewSession,
    initSession,
    updateSession,
    startEditSession,
    finishEditSession,
    deleteSession,
    setCurrentSession,
    registerSdkMethods,
    registerErrorCallback,
    switchSessionWithContents,
    sessionContentLoading,
    agentInfo,
    getSessionList,
    sessionUpdateCounter,
    // 选择模式相关
    isSelectMode,
    selectedMessages,
    selectModeType,
    enterSelectMode,
    exitSelectMode,
    toggleMessageSelection,
    toggleSelectAll,
    isSelectAll,
    isIndeterminate,
    getSelectedMessages,
    isMessageSelected,
    // 错误处理
    handleSdkError,
  };
}

export type SessionStore = ReturnType<typeof useSessionStore>;
