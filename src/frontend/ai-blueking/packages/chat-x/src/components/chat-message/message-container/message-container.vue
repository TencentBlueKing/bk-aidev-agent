<template>
  <div
    ref="messageContainerRef"
    class="ai-message-container"
  >
    <div
      v-for="(group, groupIndex) in messageGroups"
      :id="group.uuid"
      :key="groupIndex"
      class="message-group"
      :style="{
        backgroundColor: group.checked ? '#f5f7fa' : 'transparent',
      }"
      @mouseenter="handleMouseEnter(group)"
      @mouseleave="e => handleMouseLeave(group, e)"
    >
      <Checkbox
        v-if="enableSelection && group.type !== MessageRole.Loading"
        class="message-group-checkbox"
        :model-value="group.checked"
        @update:model-value="(checked: boolean) => handleCheckboxChange(group, checked)"
      />
      <div
        class="message-group-messages"
        :class="{
          'message-group-enabled-selection':
            renderMode === RenderMode.Share || (enableSelection && group.type !== MessageRole.Loading),
        }"
        :style="{
          width: enableSelection && group.type !== MessageRole.Loading ? 'calc(100% - 16px)' : '100%',
        }"
      >
        <template
          v-for="(message, index) in group.messages"
          :key="index"
        >
          <slot
            name="default"
            v-bind="{ message, messageToolsStatus }"
          >
            <MessageRender
              :key="index"
              :message="message"
              :message-tools-status="messageToolsStatus"
              :on-action="(tool: IToolBtn) => handleUserAction(tool, message)"
              :on-input-confirm="
                (content: UserMessage['content'], docSchema: TagSchema) =>
                  handleUserInputConfirm(message, content, docSchema)
              "
              :on-shortcut-confirm="
                (formModel: Record<string, unknown>) => handleUserShortcutConfirm(message, formModel)
              "
              :tippy-options="messageToolsTippyOptions"
            />
          </slot>
        </template>
        <MessageTools
          v-if="
            renderMode !== RenderMode.Share &&
            !(enableSelection && group.type !== MessageRole.Loading) &&
            !group.pause &&
            group.type === MessageRole.Assistant &&
            messageToolsStatus !== MessageToolsStatus.Hidden
          "
          :message-tools="messageTools"
          :message-tools-status="messageToolsStatus"
          :on-action="(tool: IToolBtn) => handleAgentAction(tool, group.messages)"
          :style="{ visibility: group.isHover ? 'visible' : 'hidden' }"
          :tippy-options="props.messageToolsTippyOptions"
          @feedback="
            (tool: IToolBtn, reasonList: string[], otherReason: string) =>
              props.onAgentFeedback?.(tool, group.messages, reasonList, otherReason)
          "
        />
      </div>
    </div>
    <div
      ref="messageContainerBottomRef"
      class="message-container-bottom"
      tabindex="0"
    />
    <div class="ai-message-fixed-bottom">
      <ScrollBtn
        v-show="messageStatus === MessageStatus.Streaming || messageStatus === MessageStatus.StopLoading"
        :loading="messageStatus === MessageStatus.StopLoading"
        :title="messageStatus === MessageStatus.StopLoading ? t('正在停止') : t('停止生成')"
        @click="$emit('stopStreaming')"
      >
        <template #icon>
          <CloseCircleIcon />
        </template>
      </ScrollBtn>
      <ScrollBtn
        v-show="debouncedShowScrollBottomBtn"
        :title="t('返回底部')"
        @click="toScrollBottom"
      >
        <template #icon>
          <ArrowDownIcon />
        </template>
      </ScrollBtn>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, useTemplateRef } from 'vue';

  import { Checkbox } from 'bkui-vue';

  import { type Message, type UserMessage, MessageRole, MessageStatus } from '../../../ag-ui/types';
  import { CONST_MESSAGE_TOOLS, RenderMode } from '../../../common';
  import { type MessageGroup, useClipboard, useContainerScrollProvider } from '../../../composables';
  import { ArrowDownIcon, CloseCircleIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import { MessageToolsStatus } from '../../../types/tool';
  import ScrollBtn from '../../ai-buttons/scroll-btn/scroll-btn.vue';
  import MessageTools, { type MessageToolsProps } from '../../message-tools/message-tools.vue';
  import MessageRender from '../message-render/message-render.vue';

  import type { IToolBtn, TagSchema } from '../../../types';

  export type MessageContainerEmits = {
    (e: 'stopStreaming'): void;
  };

  export type MessageContainerProps = {
    enableSelection?: boolean; // 是否启用多选模式
    messageGroups: MessageGroup[]; // 消息分组列表
    messages: Message[];
    messageStatus?: MessageStatus;
    messageToolsStatus?: MessageToolsStatus; // 工具按钮状态  disabled 禁用 hidden 隐藏
    messageToolsTippyOptions?: MessageToolsProps['tippyOptions'];
    onAgentAction?: AgentActionCallback;
    onAgentFeedback?: AgentFeedbackCallback;
    onUserAction?: UserActionCallback;
    renderMode?: RenderMode;
  } & {
    onUserInputConfirm?: (message: Message, content: UserMessage['content'], docSchema: TagSchema) => Promise<void>;
    onUserShortcutConfirm?: (message: Message, formModel: Record<string, unknown>) => Promise<void>;
  };

  /**
   * Agent 工具操作回调类型
   * @param tool - 工具按钮信息
   * @param messages - 当前消息组的消息列表（用于 cite 等需要消息内容的操作）
   */
  type AgentActionCallback = (tool: IToolBtn, messages: Message[]) => Promise<string[] | void>;

  /**
   * Agent 反馈回调类型
   * @param tool - 工具按钮信息（like/unlike）
   * @param messages - 当前消息组的消息列表
   * @param reasonList - 选择的反馈原因列表
   * @param otherReason - 其他原因（自定义输入）
   */
  type AgentFeedbackCallback = (tool: IToolBtn, messages: Message[], reasonList: string[], otherReason: string) => void;

  /**
   * User 工具操作回调类型
   * @param tool - 工具按钮信息
   * @param message - 当前用户消息（用于 delete 等需要消息信息的操作）
   */
  type UserActionCallback = (tool: IToolBtn, message: Message) => Promise<string[] | void>;

  const props = withDefaults(defineProps<MessageContainerProps>(), {
    enableSelection: false,
  });
  // 选中的消息
  const selectedUserMessages = defineModel<Message[]>('selectedUserMessages', {
    required: false,
  });

  defineEmits<MessageContainerEmits>();

  const messageContainerRef = useTemplateRef<HTMLElement>('messageContainerRef');
  const messageContainerBottomRef = useTemplateRef<HTMLElement>('messageContainerBottomRef');

  const { toScrollBottom, debouncedShowScrollBottomBtn } = useContainerScrollProvider(
    messageContainerRef,
    messageContainerBottomRef,
  );
  const { copy } = useClipboard();
  const messageTools = computed(() => {
    return CONST_MESSAGE_TOOLS.filter(tool => props.renderMode !== RenderMode.Test || tool.id !== 'share');
  });
  const handleMouseEnter = (group: { isHover: boolean }) => {
    group.isHover = true;
  };
  const handleMouseLeave = (group: { isHover: boolean }, e: MouseEvent) => {
    const related = (e as MouseEvent & { toElement?: Element }).toElement ?? e.relatedTarget;
    if (related instanceof Element && related.classList.contains('ai-user-feedback')) {
      return;
    }
    group.isHover = false;
  };
  const handleCheckboxChange = (
    selectedGroup: { checked: boolean; messages: Message[]; type: MessageRole },
    checked: boolean,
  ) => {
    const isUserGroup = selectedGroup.type === MessageRole.User;
    props.messageGroups?.forEach((group, index) => {
      if (group === selectedGroup) {
        group.checked = checked;
        const relatedGroup = isUserGroup ? props.messageGroups.at(index + 1) : props.messageGroups.at(index - 1);
        if (relatedGroup) {
          relatedGroup.checked = checked;
        }
      }
    });
    selectedUserMessages.value = props.messageGroups
      ?.filter(group => group.checked)
      .map(group => group.messages)
      .flat();
  };

  const handleAgentAction = async (tool: IToolBtn, messages: Message[]) => {
    if (tool.id === 'copy') {
      const markdownContent = messages
        .filter(message => message.role !== MessageRole.Reasoning)
        .map(message => (typeof message.content === 'string' ? message.content : JSON.stringify(message.content || '')))
        .join('\n');
      copy(markdownContent);
    }
    // 传递 messages 给外部回调，支持 cite 等需要消息内容的操作
    // 需要 return 以便 like/unlike 等操作能获取返回的原因列表
    return props.onAgentAction?.(tool, messages);
  };
  const handleUserAction = async (tool: IToolBtn, message: Message) => {
    props.onUserAction?.(tool, message);
  };

  /**
   * 处理用户输入确认
   * @param content 用户输入内容
   * @param docSchema 用户输入文档结构
   */
  const handleUserInputConfirm = async (message: Message, content: UserMessage['content'], docSchema: TagSchema) => {
    props.onUserInputConfirm?.(message, content, docSchema);
  };
  /**
   * 处理用户快捷指令输入确认提交
   * @param formModel 用户快捷表单数据
   */
  const handleUserShortcutConfirm = async (message: Message, formModel: Record<string, unknown>) => {
    props.onUserShortcutConfirm?.(message, formModel);
  };
</script>
<style lang="scss">
  .ai-message-container {
    position: relative;
    display: flex;
    flex: 1;
    flex-direction: column;
    width: 100%;
    max-width: 1000px;
    height: 100%;
    max-height: 100%;
    margin: 0 auto;

    // 使用 CSS contain 限制重排范围
    // strict 包含 size, layout, paint（但不包括 size 因为我们需要自适应高度）
    contain: layout paint;
    overflow-y: auto;

    .message-group {
      display: flex;
      gap: 8px;
      width: 100%;
      padding: 8px;

      &-enabled-selection {
        .ai-user-message-tools {
          display: none !important;
        }
      }

      &-checkbox {
        flex: 0 0 16px;
        align-self: baseline;
        height: 16px;
        margin-right: auto;
      }

      &-messages {
        display: flex;
        flex-direction: column;
        gap: 12px;
        width: 100%;
        margin-left: auto;
        contain: content;
      }
    }

    .message-container-bottom {
      display: flex;
      flex: 0 0 2px;
      width: 100%;
      height: 2px;
      min-height: 2%;
      max-height: 2px;
      background-color: transparent;
    }

    .ai-message-fixed-bottom {
      position: sticky;
      right: 0;
      bottom: 12px;
      left: 0;
      z-index: 10;
      display: flex;
      gap: 8px;
      align-items: center;
      justify-content: center;
      width: 100%;
      margin-top: auto;

      .ai-close-circle-icon {
        color: #ea3636;
      }

      .ai-arrow-down-icon {
        color: #979ba5;
      }
    }
  }
</style>
