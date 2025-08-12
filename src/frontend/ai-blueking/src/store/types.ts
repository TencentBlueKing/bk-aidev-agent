import type { ISession, ISessionContent, ISessionPrompt } from '@blueking/ai-ui-sdk/types';

/**
 * 扩展 ISession 接口，添加 isEdit 属性
 */
export interface ISessionEditItem extends ISession {
  isEdit?: boolean;
}

/**
 * 会话历史分组项
 */
export interface HistoryItem {
  key: string;
  alias: string;
  sessionList: ISessionEditItem[];
}

/**
 * 为所有需要的 SDK 方法定义一个清晰的接口（Interface），以获得更好的类型提示和代码健壮性。
 */
export interface SdkApi {
  setCurrentSession: (session: ISession) => void;
  getSessionContentsApi: (sessionCode: string) => Promise<ISessionContent[]>;
  setSessionContents: (contents: ISessionContent[]) => void;
  modifySessionApi: (session: ISession) => Promise<any>;
  deleteSessionApi: (sessionCode: string) => Promise<any>;
  renameSessionApi: (sessionCode: string) => Promise<ISession>;
  setCurrentSessionChain: (session: ISession) => void;
  getSessionsApi: () => Promise<ISession[]>;
  getAgentInfoApi: () => Promise<IAgentInfo>;
  plusSessionApi: (session: ISession) => Promise<any>;
  handleCompleteRole: (sessionCode: string, prompts: ISessionPrompt[]) => Promise<any>;
}

import type { IAgentInfo as AIUIAgentInfo } from '@blueking/ai-ui-sdk/types';

// 使用 ai-ui-sdk 中的 IAgentInfo 类型
export type IAgentInfo = AIUIAgentInfo;
