<template>
  <div
    ref="messageToolsRef"
    class="ai-message-tools-container"
    :class="{ 'is-loading': hasLoadingTool }"
  >
    <div
      v-if="$slots.prepend"
      class="ai-message-tools-prepend"
    >
      <slot name="prepend" />
    </div>
    <div class="message-tools">
      <template
        v-for="tool in messageTools"
        :key="tool.id"
      >
        <DeleteTool
          v-if="tool.id === 'delete'"
          v-bind="tool"
          :disabled="isToolDisabled(tool)"
          :loading="isToolLoading(tool)"
          :tippy-options="tippyOptions"
          @confirm="handleDeleteConfirm(tool)"
        />
        <ToolBtn
          v-else
          v-bind="tool"
          :disabled="isToolDisabled(tool)"
          :loading="isToolLoading(tool)"
          :tippy-options="tippyOptions"
          @click="handleAction(tool)"
        />
      </template>
    </div>
    <div
      v-if="updateTools.length > 0"
      class="ai-divider"
      style="margin-right: 4px; margin-left: 4px"
    />
    <div
      v-if="updateTools.length > 0"
      class="message-tools"
    >
      <template
        v-for="tool in updateTools"
        :key="tool.id"
      >
        <Tippy
          v-if="tool.id === 'like' || tool.id === 'unlike'"
          ref="feedbackTippyRef"
          v-bind="tippyProps"
          @show="handleTippyShow(tool.id)"
        >
          <ToolBtn
            v-bind="tool"
            :id="getSubmitToolId(tool.id as 'like' | 'unlike')"
            :active="submitId === tool.id"
            :disabled="isToolDisabled(tool)"
            :loading="isToolLoading(tool)"
            :tippy-options="{
              ...tippyOptions,
              content: getTippyContent(tool.id as 'like' | 'unlike'),
            }"
            @click="handleAction(tool)"
          />
          <template #content>
            <UserFeedback
              :loading="userFeedbackLoading"
              :reason-list="userFeedbackReasonList"
              :title="tool.id === 'like' ? t('什么原因让你满意？') : t('什么原因让你不满意？')"
              @cancel="handleCancel"
              @submit="(reasonList, otherReason) => handleSubmit(tool, reasonList, otherReason)"
            />
          </template>
        </Tippy>
        <DeleteTool
          v-else-if="tool.id === 'delete'"
          v-bind="tool"
          :disabled="isToolDisabled(tool)"
          :loading="isToolLoading(tool)"
          :tippy-options="tippyOptions"
          @confirm="handleDeleteConfirm(tool)"
        />
        <ToolBtn
          v-else
          v-bind="tool"
          :disabled="isToolDisabled(tool)"
          :loading="isToolLoading(tool)"
          :tippy-options="tippyOptions"
          @click="handleAction(tool)"
        />
      </template>
    </div>
    <div
      v-if="$slots.append"
      class="ai-message-tools-append"
    >
      <slot name="append" />
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue';

  import { type TippyContent, Tippy, useTippy } from 'vue-tippy';

  import { CONST_MESSAGE_TOOLS, CONST_UPDATE_TOOLS } from '../../common/constants';
  import { t } from '../../lang/lang';
  import { MessageToolsStatus } from '../../types/tool';
  import { isPromiseLike } from '../../utils/utils';
  import ToolBtn from '../ai-buttons/tool-btn/tool-btn.vue';
  import DeleteTool from './delete-tool/delete-tool.vue';
  import UserFeedback from './user-feedback/user-feedback.vue';

  import type { UserMessage } from '../../ag-ui/types/messages';
  import type { AITippyProps, IToolBtn, TagSchema } from '../../types';

  import 'tippy.js/dist/tippy.css';

  export type MessageToolsProps = {
    messageTools?: IToolBtn[];
    messageToolsStatus?: MessageToolsStatus;
    onAction?: (
      tool: IToolBtn,
      content?: UserMessage['content'],
      docSchema?: TagSchema,
    ) => Promise<string[] | void> | string[] | void;
    tippyOptions?: AITippyProps;
    updateTools?: IToolBtn[];
  };
  const props = withDefaults(defineProps<MessageToolsProps>(), {
    messageTools: () => CONST_MESSAGE_TOOLS,
    updateTools: () => CONST_UPDATE_TOOLS,
  });
  const emit = defineEmits<{
    (e: 'feedback', tool: IToolBtn, reasonList: string[], otherReason: string): void;
    (e: 'loadingChange', loading: boolean): void;
  }>();

  defineSlots<{
    // 工具图标右侧的附加内容，如 AI 消息的时间
    append?: () => unknown;
    // 工具图标左侧的附加内容，如用户消息的时间
    prepend?: () => unknown;
  }>();

  // 纯本地交互按钮不进入按钮级 loading（like/unlike 已有独立反馈弹窗 loading）
  const LOCAL_ACTION_TOOL_IDS = new Set<string>(['copy', 'share', 'edit', 'cite']);

  const feedbackTippyRef = useTemplateRef<InstanceType<typeof Tippy> & ReturnType<typeof useTippy>[]>(
    'feedbackTippyRef',
  );
  const userFeedbackLoading = shallowRef(false);
  const userFeedbackReasonList = shallowRef<string[]>([]);
  const submitId = shallowRef<'like' | 'unlike' | null>(null);
  const loadingTool = shallowRef<IToolBtn | null>(null);

  const isSameTool = (a: IToolBtn | null, b: IToolBtn): boolean => {
    if (!a) return false;
    if (a.id !== undefined && b.id !== undefined) {
      return a.id === b.id;
    }
    return a === b;
  };

  const isToolLoading = (tool: IToolBtn): boolean => Boolean(tool.loading || isSameTool(loadingTool.value, tool));

  const hasLoadingTool = computed(
    () =>
      loadingTool.value !== null ||
      props.messageTools.some(tool => Boolean(tool.loading)) ||
      props.updateTools.some(tool => Boolean(tool.loading)),
  );

  watch(
    hasLoadingTool,
    (loading, prevLoading) => {
      if (loading || prevLoading !== undefined) {
        emit('loadingChange', loading);
      }
    },
    { immediate: true },
  );

  const tippyProps = computed(() => {
    return {
      arrow: false,
      interactive: true,
      offset: [0, 6],
      theme: 'ai-chat-box-light light',
      trigger: 'click',
      appendTo: () => document.body,
      ...(props.tippyOptions || {}),
    } as InstanceType<typeof Tippy>['$props'];
  });

  // 流式生成或同组异步操作进行中时禁用除复制外的其余按钮；正在 loading 的按钮保持主色加载态而非置灰
  const isToolDisabled = (tool: IToolBtn) =>
    !isToolLoading(tool) &&
    (props.messageToolsStatus === MessageToolsStatus.Disabled || hasLoadingTool.value) &&
    tool.id !== 'copy';

  const shouldTrackAsyncLoading = (tool: IToolBtn): boolean =>
    !tool.triggerSelection && (!tool.id || !LOCAL_ACTION_TOOL_IDS.has(tool.id));

  const runTrackedAction = async (tool: IToolBtn) => {
    if (hasLoadingTool.value) return;
    const result = props.onAction?.(tool);
    if (!isPromiseLike(result)) return;

    loadingTool.value = tool;
    try {
      await result;
    } finally {
      if (isSameTool(loadingTool.value, tool)) {
        loadingTool.value = null;
      }
    }
  };

  const handleAction = async (tool: IToolBtn) => {
    if (tool.id === 'like' || tool.id === 'unlike') {
      if (hasLoadingTool.value) return;
      try {
        userFeedbackLoading.value = true;
        userFeedbackReasonList.value = [];
        userFeedbackReasonList.value = (await props.onAction?.(tool)) || [];
      } finally {
        userFeedbackLoading.value = false;
      }
      return;
    }
    if (!shouldTrackAsyncLoading(tool)) {
      await props.onAction?.(tool);
      return;
    }
    await runTrackedAction(tool);
  };
  const handleDeleteConfirm = async (tool: IToolBtn) => {
    await runTrackedAction(tool);
  };
  const handleCancel = () => {
    feedbackTippyRef.value?.forEach(tippy => tippy?.hide?.());
  };
  const getSubmitToolId = (id: 'like' | 'unlike') => {
    if (!submitId.value) return id;
    if (submitId.value === 'like' && id === 'like') return 'activeLike';
    if (submitId.value === 'unlike' && id === 'unlike') return 'activeUnLike';
    return id;
  };
  const getTippyContent = (id: 'like' | 'unlike'): TippyContent => {
    const toolId = getSubmitToolId(id);
    if (toolId === 'activeLike') return t('取消满意');
    if (toolId === 'activeUnLike') return t('取消不满意');
    return props.updateTools?.find(tool => tool.id === toolId)?.description || '';
  };
  const handleSubmit = (tool: IToolBtn, reasonList: string[], otherReason: string) => {
    handleCancel();
    if (submitId.value === tool.id) {
      submitId.value = null;
    } else {
      submitId.value = tool.id as 'like' | 'unlike';
    }
    emit('feedback', tool, reasonList, otherReason);
  };
  const handleTippyShow = (id: IToolBtn['id']) => {
    if (props.messageToolsStatus === MessageToolsStatus.Disabled || hasLoadingTool.value) return false;
    if (submitId.value && submitId.value === id) {
      submitId.value = null;
      return false;
    }
    return;
  };
  onUnmounted(() => {
    handleCancel();
    userFeedbackReasonList.value = [];
    if (hasLoadingTool.value) {
      emit('loadingChange', false);
    }
  });
</script>
<style lang="scss">
  .ai-message-tools-container {
    display: flex;
    gap: 4px;
    align-items: center;
    width: 100%;

    .message-tools {
      display: flex;
      gap: 4px;
      align-items: center;
      width: fit-content;
    }

    .ai-message-tools-prepend,
    .ai-message-tools-append {
      display: flex;
      align-items: center;
    }

    .ai-message-tools-prepend {
      margin-right: 4px;
    }

    .ai-message-tools-append {
      margin-left: 4px;
    }

    // 消息无时间时 MessageTime 不渲染内容，此时收掉包裹容器避免留下多余间距
    .ai-message-tools-prepend:empty,
    .ai-message-tools-append:empty {
      display: none;
    }
  }
</style>
