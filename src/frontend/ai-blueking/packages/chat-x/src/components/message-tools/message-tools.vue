<template>
  <div
    ref="messageToolsRef"
    class="message-tools-container"
  >
    <div
      class="message-tools"
      style="margin-right: 8px"
    >
      <template
        v-for="tool in messageTools"
        :key="tool.id"
      >
        <DeleteTool
          v-if="tool.id === 'delete'"
          v-bind="tool"
          :disabled="messageToolsStatus === MessageToolsStatus.Disabled"
          :tippy-options="tippyOptions"
          @confirm="handleDeleteConfirm(tool)"
        />
        <ToolBtn
          v-else
          v-bind="tool"
          :disabled="messageToolsStatus === MessageToolsStatus.Disabled"
          :tippy-options="tippyOptions"
          @click="handleAction(tool)"
        />
      </template>
    </div>
    <div
      v-if="updateTools.length > 0"
      class="ai-divider"
      style="margin-right: 8px"
    />
    <div class="message-tools">
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
            :disabled="messageToolsStatus === MessageToolsStatus.Disabled"
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
          :disabled="messageToolsStatus === MessageToolsStatus.Disabled"
          :tippy-options="tippyOptions"
          @confirm="handleDeleteConfirm(tool)"
        />
        <ToolBtn
          v-else
          v-bind="tool"
          :disabled="messageToolsStatus === MessageToolsStatus.Disabled"
          :tippy-options="tippyOptions"
          @click="handleAction(tool)"
        />
      </template>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, onUnmounted, shallowRef, useTemplateRef } from 'vue';

  import { type TippyContent, Tippy, useTippy } from 'vue-tippy';

  import { CONST_MESSAGE_TOOLS, CONST_UPDATE_TOOLS } from '../../common/constants';
  import { t } from '../../lang/lang';
  import { MessageToolsStatus } from '../../types/tool';
  import ToolBtn from '../ai-buttons/tool-btn/tool-btn.vue';
  import DeleteTool from './delete-tool/delete-tool.vue';
  import UserFeedback from './user-feedback/user-feedback.vue';

  import type { UserMessage } from '../../ag-ui/types/messages';
  import type { AITippyProps, IToolBtn, TagSchema } from '../../types';

  import 'tippy.js/dist/tippy.css';

  export type MessageToolsProps = {
    messageTools?: IToolBtn[];
    messageToolsStatus?: MessageToolsStatus;
    onAction?: (tool: IToolBtn, content?: UserMessage['content'], docSchema?: TagSchema) => Promise<string[] | void>;
    tippyOptions?: AITippyProps;
    updateTools?: IToolBtn[];
  };
  const props = withDefaults(defineProps<MessageToolsProps>(), {
    messageTools: () => CONST_MESSAGE_TOOLS,
    updateTools: () => CONST_UPDATE_TOOLS,
  });
  const emit = defineEmits<{
    (e: 'feedback', tool: IToolBtn, reasonList: string[], otherReason: string): void;
  }>();

  const feedbackTippyRef = useTemplateRef<InstanceType<typeof Tippy> & ReturnType<typeof useTippy>[]>(
    'feedbackTippyRef',
  );
  const userFeedbackLoading = shallowRef(false);
  const userFeedbackReasonList = shallowRef<string[]>([]);
  const submitId = shallowRef<'like' | 'unlike' | null>(null);

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

  const handleAction = async (tool: IToolBtn) => {
    if (tool.id === 'like' || tool.id === 'unlike') {
      try {
        userFeedbackLoading.value = true;
        userFeedbackReasonList.value = [];
        userFeedbackReasonList.value = (await props.onAction?.(tool)) || [];
      } finally {
        userFeedbackLoading.value = false;
      }
      return;
    }
    await props.onAction?.(tool);
  };
  const handleDeleteConfirm = async (tool: IToolBtn) => {
    await props.onAction?.(tool);
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
    if (props.messageToolsStatus === MessageToolsStatus.Disabled) return false;
    if (submitId.value && submitId.value === id) {
      submitId.value = null;
      return false;
    }
    return;
  };
  onUnmounted(() => {
    handleCancel();
    userFeedbackReasonList.value = [];
  });
</script>
<style lang="scss">
  .message-tools-container {
    display: flex;
    align-items: center;
    width: 100%;

    .message-tools {
      display: flex;
      gap: 4px;
      align-items: center;
      width: fit-content;
    }
  }
</style>
