<template>
  <div
    ref="messageContainerRef"
    class="ai-message-container"
  >
    <div
      v-for="(group, groupIndex) in visibleMessageGroups"
      :id="group.uid"
      :key="groupIndex"
      class="message-group"
      :data-message-group-id="group.uid"
      :style="{
        backgroundColor: group.checked ? '#f5f7fa' : 'transparent',
      }"
      @mouseenter="handleMouseEnter(group)"
      @mouseleave="e => handleMouseLeave(group, e)"
    >
      <slot
        name="group"
        v-bind="{ group }"
      >
        <Checkbox
          v-if="enableSelection && group.type !== MessageRole.Loading"
          class="message-group-checkbox"
          :class="{ 'is-user-group': group.type === MessageRole.User }"
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
          <div
            v-for="(message, index) in group.messages"
            :key="index"
            class="ai-message-item"
            :data-message-id="resolveMessageDomId(message)"
          >
            <slot
              name="default"
              v-bind="{ message, messageToolsStatus, onInterruptResume: props.onInterruptResume }"
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
                :on-interrupt-resume="props.onInterruptResume"
                :on-shortcut-confirm="
                  (formModel: Record<string, unknown>) => handleUserShortcutConfirm(message, formModel)
                "
                :tippy-options="messageToolsTippyOptions"
              >
                <template
                  v-if="$slots.answeredQuestion"
                  #answeredQuestion="slotProps"
                >
                  <slot
                    name="answeredQuestion"
                    v-bind="slotProps"
                  />
                </template>
              </MessageRender>
            </slot>
          </div>
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
            :update-tools="updateTools"
            @feedback="
              (tool: IToolBtn, reasonList: string[], otherReason: string) =>
                props.onAgentFeedback?.(tool, group.messages, reasonList, otherReason)
            "
          >
            <!-- 设计稿：AI 消息的时间在工具图标右侧 -->
            <template #append>
              <MessageTime :created-at="resolveGroupCreatedAt(group.messages)" />
            </template>
          </MessageTools>
        </div>
      </slot>
    </div>
    <div
      ref="messageContainerBottomRef"
      class="message-container-bottom"
      tabindex="0"
    />
    <div class="ai-message-fixed-bottom">
      <ScrollBtn
        v-show="
          renderMode !== RenderMode.Share &&
          (messageStatus === MessageStatus.Streaming ||
            messageStatus === MessageStatus.StopLoading ||
            messageStatus === MessageStatus.Fetching ||
            messageStatus === MessageStatus.Pending)
        "
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
        @click="() => toScrollBottom('smooth')"
      >
        <template #icon>
          <ArrowDownIcon />
        </template>
      </ScrollBtn>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, onMounted, useTemplateRef } from 'vue';

  import { Checkbox } from 'bkui-vue';

  import { type Message, type UserMessage, MessageRole, MessageStatus } from '../../../ag-ui/types';
  import { CONST_MESSAGE_TOOLS, CONST_UPDATE_TOOLS, RenderMode } from '../../../common';
  import { type MessageGroup, useClipboard, useContainerScrollProvider } from '../../../composables';
  import { ArrowDownIcon, CloseCircleIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import { MessageToolsStatus } from '../../../types/tool';
  import ScrollBtn from '../../ai-buttons/scroll-btn/scroll-btn.vue';
  import MessageTime from '../../message-tools/message-time/message-time.vue';
  import MessageTools, { type MessageToolsProps } from '../../message-tools/message-tools.vue';
  import MessageRender from '../message-render/message-render.vue';

  import type { OnInterruptResume } from '../../../ag-ui/types/interrupt';
  import type { IToolBtn, TagSchema } from '../../../types';
  import type { UserQuestionAnsweredCardSlots } from '../interrupt-message/user-question/user-question-answered-card.vue';

  export type MessageContainerEmits = {
    (e: 'stopStreaming'): void;
  };

  export type MessageContainerProps = {
    enableSelection?: boolean; // 是否启用多选模式
    messageGroups: MessageGroup[]; // 消息分组列表
    messages: Message[];
    messageStatus?: MessageStatus;
    // 自定义 AI 消息主工具组（copy/cite/rebuild/share 一排）；以内置列表为基底，按 id 覆盖同名项、追加新项
    messageTools?: IToolBtn[];
    messageToolsStatus?: MessageToolsStatus; // 工具按钮状态  disabled 禁用 hidden 隐藏
    messageToolsTippyOptions?: MessageToolsProps['tippyOptions'];
    onAgentAction?: AgentActionCallback;
    onAgentFeedback?: AgentFeedbackCallback;
    onInterruptResume?: OnInterruptResume; // ag-ui human-in-the-loop 中断响应回调
    onUserAction?: UserActionCallback;
    renderMode?: RenderMode;
    // 自定义 AI 消息反馈工具组（like/unlike/delete 一排）；以内置列表为基底，按 id 覆盖同名项、追加新项
    updateTools?: IToolBtn[];
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

  defineSlots<{
    // 中断消息「已回答内容」回显的自定义 slot，透传给内部 MessageRender
    answeredQuestion: UserQuestionAnsweredCardSlots['answer'];
    // 自定义单条消息渲染（默认回退到内部 MessageRender）
    default: (props: {
      message: Message;
      messageToolsStatus?: MessageToolsStatus;
      onInterruptResume?: OnInterruptResume;
    }) => unknown;
    group: (props: { group: MessageGroup }) => unknown;
  }>();

  /**
   * 单条消息的 DOM 标识：优先服务端消息 ID，流式渲染中尚未拿到 ID 时回退到前端 uid
   * @returns 两者都缺失时返回 undefined，此时不输出 data-message-id 属性
   */
  const resolveMessageDomId = (message: Message): string | undefined => {
    const domId = message.id || message.uid;
    return domId === undefined ? undefined : String(domId);
  };

  /**
   * AI 回答组的时间取组内最后一条带时间的消息，对应本轮回答完成时间
   * 组内 reasoning / activity 等子消息不单独展示时间，只在组级工具栏显示一次
   */
  const resolveGroupCreatedAt = (messages: Message[]): number | string | undefined => {
    for (let index = messages.length - 1; index >= 0; index--) {
      const createdAt = messages[index]?.createdAt;
      if (createdAt) {
        return createdAt;
      }
    }
    return undefined;
  };

  const messageContainerRef = useTemplateRef<HTMLElement>('messageContainerRef');
  const messageContainerBottomRef = useTemplateRef<HTMLElement>('messageContainerBottomRef');

  const { jumpToBottom, toScrollBottom, debouncedShowScrollBottomBtn } = useContainerScrollProvider(
    messageContainerRef,
    messageContainerBottomRef,
  );

  // 首屏与切换会话时容器都是全新挂载（scrollTop 为 0），先瞬时定位到底部，
  // 再在首帧布局后补一次，避免历史消息渲染过程中出现从顶部滚到底部的动画
  onMounted(() => {
    if (!props.messageGroups?.length) return;
    jumpToBottom();
    requestAnimationFrame(() => jumpToBottom());
  });

  const { copy } = useClipboard();
  /**
   * 按 id 合并工具列表：以内置列表为基底，同 id 覆盖（字段级合并）、新 id 追加，其余保留；
   * 最后过滤掉标记 hidden 的项，实现「隐藏内置按钮」（如 { id: 'share', hidden: true }）。
   * @param base 内置基底列表
   * @param extra 业务自定义列表
   */
  const mergeToolsById = (base: IToolBtn[], extra?: IToolBtn[]): IToolBtn[] => {
    if (!extra?.length) return base;
    const merged = base.map(tool => {
      const override = extra.find(item => item.id === tool.id);
      return override ? { ...tool, ...override } : tool;
    });
    const appended = extra.filter(item => !base.some(tool => tool.id === item.id));
    return [...merged, ...appended].filter(tool => !tool.hidden);
  };
  const messageTools = computed(() => {
    const tools = mergeToolsById(CONST_MESSAGE_TOOLS, props.messageTools);
    return tools.filter(tool => props.renderMode !== RenderMode.Test || tool.id !== 'share');
  });
  const updateTools = computed(() => mergeToolsById(CONST_UPDATE_TOOLS, props.updateTools));
  // Share 模式仅展示历史消息，过滤自动注入或外部传入的 Loading 占位组
  const visibleMessageGroups = computed(() =>
    props.renderMode === RenderMode.Share
      ? props.messageGroups.filter(group => group.type !== MessageRole.Loading)
      : props.messageGroups,
  );
  const handleMouseEnter = (group: MessageGroup) => {
    const lastMessage = group.messages?.at(-1);
    if (lastMessage?.role === MessageRole.Interrupt) {
      return;
    }
    group.isHover = true;
  };
  const handleMouseLeave = (group: MessageGroup, e: MouseEvent) => {
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
    padding: 0 16px;
    margin: 0 auto;

    // 使用 CSS contain 限制重排范围
    // strict 包含 size, layout, paint（但不包括 size 因为我们需要自适应高度）
    contain: layout paint;
    overflow-y: auto;

    .message-group {
      display: flex;
      gap: 8px;
      width: 100%;
      padding: 8px 0;

      &-enabled-selection {
        .ai-user-message-tools {
          display: none !important;
        }
      }

      &-checkbox {
        flex: 0 0 16px;

        // 兄弟节点 .message-group-messages 未参与基线对齐组，baseline 会退化为贴组顶部，
        // 错位程度随首个内容结构变化。改为顶部对齐 + 定量补偿，使勾选框在首行行高内垂直居中
        align-self: flex-start;
        height: 16px;
        margin-top: calc((var(--ai-line-height, 20px) - 16px) / 2);
        margin-right: auto;

        // 用户消息是带 8px 纵向内边距的气泡，需再下移一个内边距才能对齐气泡内首行文字
        &.is-user-group {
          margin-top: calc((var(--ai-line-height, 20px) - 16px) / 2 + 8px);
        }
      }

      &-messages {
        display: flex;
        flex-direction: column;
        gap: 12px;
        width: 100%;
        margin-left: auto;

        // contain: content;
      }
    }

    // 仅作为单条消息的 DOM 定位锚点，沿用父级的列向弹性布局，不改变原有排版
    .ai-message-item {
      display: flex;
      flex-direction: column;
      min-width: 0;
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
