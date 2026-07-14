import { type Ref, inject, provide, shallowRef } from 'vue';

import type { AIFileInfo } from '../ag-ui/types/file';

/** 文件产物预览 Provider/Consumer 通信 token */
export const ARTIFACT_PREVIEW_TOKEN = Symbol('ARTIFACT_PREVIEW_TOKEN');

/** 文件产物侧栏 Tab 的保留唯一标识（固定 Tab，不可关闭） */
export const FILE_ARTIFACT_TAB_NAME = 'file-artifact';

/**
 * 会话级文件产物：在 AIFileInfo 基础上补充命中所需的唯一 id 与所属消息。
 * 由于同一会话可能出现「多个 AssistantMessage + 同名文件」，文件名不可作为唯一键，
 * 统一用 messageUid + 消息内下标 + outputId 组合出全局唯一 id。
 */
export type SessionArtifact = AIFileInfo & {
  artifactId: string;
  messageUid: string;
};

export type OpenArtifactPreviewPayload = {
  /** 被点击的文件 */
  file: AIFileInfo;
  /** 文件在所属消息 artifacts 中的下标 */
  index: number;
  /** 所属 AssistantMessage 的 uid */
  messageUid: string;
};

type ArtifactPreviewContext = {
  /** 当前命中的文件 id */
  activeArtifactId: Ref<string>;
  /** 由文件卡片触发：命中文件并弹出/切换到文件产物侧栏 */
  openPreview: (payload: OpenArtifactPreviewPayload) => void;
  /** 直接设置命中文件 id（侧栏列表内切换用） */
  setActiveArtifactId: (id: string) => void;
};

/** 统一的文件产物唯一 id 生成规则，Provider 与文件卡片两侧必须一致 */
export const buildArtifactId = (messageUid: string, index: number, outputId: string) =>
  `${messageUid}#${index}#${outputId}`;

/**
 * 文件产物预览 Provider（在 ChatContainer 内使用）。
 * 仅维护「命中文件」这一份数据状态；打开侧栏 Tab 的副作用由外部 onOpen 注入，
 * 避免 composable 直接依赖 useCustomTab，保持职责单一。
 */
export const useArtifactPreviewProvider = (options: {
  /** 命中文件后触发：由容器负责 addCustomTab + 展开侧栏 + 选中 Tab */
  onOpen: (artifactId: string) => void;
}) => {
  const activeArtifactId = shallowRef('');

  const setActiveArtifactId = (id: string) => {
    activeArtifactId.value = id;
  };

  const openPreview = (payload: OpenArtifactPreviewPayload) => {
    const id = buildArtifactId(payload.messageUid, payload.index, payload.file.outputId);
    activeArtifactId.value = id;
    options.onOpen(id);
  };

  provide<ArtifactPreviewContext>(ARTIFACT_PREVIEW_TOKEN, {
    activeArtifactId,
    openPreview,
    setActiveArtifactId,
  });

  return {
    activeArtifactId,
    openPreview,
    setActiveArtifactId,
  };
};

/** 文件产物预览 Consumer（在深层文件卡片中使用），无 Provider 时返回 undefined 兜底 */
export const useArtifactPreviewConsumer = () =>
  inject<ArtifactPreviewContext | undefined>(ARTIFACT_PREVIEW_TOKEN, undefined);
