<template>
  <div class="ai-user-message">
    <CiteContent
      v-if="citeContent && typeof citeContent === 'string'"
      class="ai-user-message-cite"
      :content="citeContent"
    />
    <!-- 非编辑状态 -->
    <template v-if="!isEdit">
      <template v-if="binaryFiles.length">
        <div
          v-if="binaryImageFiles.length"
          class="ai-user-message-binary-files"
        >
          <FileContent
            :files="binaryImageFiles"
            :readonly="true"
          />
        </div>
        <div
          v-for="(file, index) in binaryNonImageFiles"
          :key="file.url ?? index"
          class="ai-user-message-binary-files"
        >
          <FileContent
            :files="[file]"
            :readonly="true"
          />
        </div>
      </template>
      <div
        v-if="citeContent || textParts.length"
        class="ai-user-message-content"
      >
        <template v-if="Array.isArray(citeContent)">
          <!-- property.extra.cite 是数组时，显示结构化内容 -->
          <KeyValueContent
            :content="citeContent"
            :title="citeTitle"
          />
        </template>
        <!-- agui user message content 显示-->
        <TextContent
          v-for="(text, index) in textParts"
          v-else-if="content"
          :key="index"
          :content="text"
        />
      </div>
      <MessageTools
        v-if="messageToolsStatus !== MessageToolsStatus.Hidden"
        class="ai-user-message-tools"
        :message-tools="CONST_USER_MESSAGE_TOOLS"
        :message-tools-status="messageToolsStatus"
        :on-action="handleAction"
        :tippy-options="tippyOptions"
        :update-tools="[]"
      />
    </template>
    <!-- 编辑状态 -->
    <template v-else>
      <ShortcutRender
        v-if="shortcut"
        v-bind="shortcut"
        class="user-shortcut-render"
        @close="handleClose"
        @submit="handleSubmit"
      />
      <ChatInput
        v-else
        ref="chatInputRef"
        v-model="editContent"
        class="user-edit-input"
        :default-upload-files="binaryFiles"
        :on-send-message="handleSendMessage"
        :support-upload="globalConfig?.supportUpload.value ?? false"
      >
        <template #send-icon>
          <div class="user-edit-footer">
            <Button
              size="small"
              @click="handleCancel"
              >{{ t('取消') }}</Button
            >
            <Button
              size="small"
              theme="primary"
              @click="handleSave"
              >{{ t('发送') }}</Button
            >
          </div>
        </template>
      </ChatInput>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { computed, shallowRef, useTemplateRef } from 'vue';

  import { Button } from 'bkui-vue';

  import { type TextInputContent, MessageContentType } from '../../../ag-ui/types';
  import { CONST_USER_MESSAGE_TOOLS } from '../../../common/constants';
  import { useClipboard } from '../../../composables';
  import { injectGlobalConfig } from '../../../composables/use-global-config';
  import { t } from '../../../lang/lang';
  import {
    type IToolBtn,
    type Shortcut,
    type ShortcutComponent,
    type TagSchema,
    type UploadFile,
    MessageToolsStatus,
  } from '../../../types';
  import { isImageFile } from '../../../utils';
  import ShortcutRender from '../../ai-shortcut/shortcut-render/shortcut-render.vue';
  import CiteContent from '../../chat-content/cite-content/cite-content.vue';
  import FileContent from '../../chat-content/file-content/file-content.vue';
  import KeyValueContent from '../../chat-content/key-value-content/key-value-content.vue';
  import TextContent from '../../chat-content/text-content/text-content.vue';
  import ChatInput from '../../chat-input/chat-input.vue';
  import MessageTools, { type MessageToolsProps } from '../../message-tools/message-tools.vue';

  import type { UserMessage } from '../../../ag-ui/types/messages';

  export type UserMessageActionsProps = {
    messageToolsStatus?: MessageToolsStatus;
    onInputConfirm?: (content: UserMessage['content'], docSchema: TagSchema) => Promise<void>;
    onShortcutConfirm?: (formModel: Record<string, unknown>) => Promise<void>;
  };
  const props = defineProps<
    Partial<UserMessage> & Pick<MessageToolsProps, 'onAction' | 'tippyOptions'> & UserMessageActionsProps
  >();
  const globalConfig = injectGlobalConfig();
  const { copy } = useClipboard();
  const isEdit = shallowRef(false);
  const editContent = shallowRef<string | TagSchema>('');
  const chatInputRef = useTemplateRef<InstanceType<typeof ChatInput>>('chatInputRef');
  const citeTitle = computed(() => {
    const cite = props.property?.extra?.cite;
    if (!cite || typeof cite === 'string') {
      return undefined;
    }
    return cite.title;
  });
  const citeContent = computed(() => {
    const cite = props.property?.extra?.cite;
    if (!cite || typeof cite === 'string') {
      return cite;
    }
    return cite.data;
  });
  const shortcut = computed(() => {
    if (!props.property?.extra) return null;
    const { extra } = props.property;
    const { shortcut, cite, context } = extra || {};
    if (shortcut) {
      return shortcut;
    }
    if (cite && typeof cite === 'object' && cite.data?.length) {
      const components: ShortcutComponent[] = [];
      for (const item of cite.data) {
        const data = context?.find(ctx => ctx.__label === item.key);
        if (data?.__key) {
          components.push({
            formItemProps: {
              label: data.__label,
              required: !!data.fillBack,
            },
            props: {
              default: data.__value,
            },
            key: data.__key,
            type: 'textarea',
          });
        }
      }
      return {
        components,
        name: cite.title,
      };
    }
    return null;
  }) as Partial<Shortcut>;

  const isBinaryImage = (file: UploadFile) => !!file.url || isImageFile(file.mimeType || file.file?.type);

  // 二进制文件
  const binaryFiles = computed(() => {
    if (!Array.isArray(props.content)) return [];
    return props.content?.filter(item => item.type === MessageContentType.Binary) as UploadFile[];
  });
  const binaryImageFiles = computed(() => binaryFiles.value.filter(f => isBinaryImage(f)));
  const binaryNonImageFiles = computed(() => binaryFiles.value.filter(f => !isBinaryImage(f)));
  // 文本内容（统一为 string[]，兼容 content 为 string 或 InputContent[]）
  const textParts = computed((): string[] => {
    if (!props.content) return [];
    if (typeof props.content === 'string') return [props.content];
    return props.content
      .filter((item): item is TextInputContent => item.type === MessageContentType.Text && !!item.text?.trim())
      .map(item => item.text);
  });
  const handleAction = async (tool: IToolBtn) => {
    if (tool.id === 'edit') {
      if (textParts.value.length) {
        editContent.value = textParts.value[0] ?? '';
        isEdit.value = true;
      }
      if (binaryFiles.value.length) {
        isEdit.value = true;
      }
    } else if (tool.id === 'copy') {
      copy(typeof props.content === 'string' ? props.content : JSON.stringify(props.content || ''));
    }
    await props.onAction?.(tool);
  };

  /**
   * 处理保存编辑
   * 调用 onAction 传递 edit-confirm 事件和编辑后的内容
   */
  const handleSave = async () => {
    await chatInputRef.value?.triggerSendMessage?.();
    isEdit.value = false;
  };

  const handleCancel = () => {
    isEdit.value = false;
  };

  const handleClose = () => {
    isEdit.value = false;
  };
  /**
   * 处理快捷表单提交
   */
  const handleSubmit = async (formModel: Record<string, unknown>) => {
    props.onShortcutConfirm?.(formModel);
    isEdit.value = false;
  };
  const handleSendMessage = async (content: UserMessage['content'], docSchema: TagSchema) => {
    props.onInputConfirm?.(content, docSchema);
    isEdit.value = false;
  };
</script>
<style lang="scss">
  .ai-user-message {
    display: flex;
    flex-direction: column;
    gap: 6px;
    align-items: flex-end;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height, 20px);
    color: #313238;

    &-content {
      display: flex;
      width: fit-content;
      padding: 8px var(--ai-spacing-comfortable, 8px);
      word-break: break-all;
      background-color: #e1ecff;
      border-radius: 4px;

      .ai-text-content {
        width: auto;
        padding: 0;
        background-color: transparent;
        border-radius: 0;
      }
    }

    &-tools {
      visibility: hidden;
      justify-content: flex-end;

      // margin-top: 4px;
    }

    .user-edit-input {
      align-items: flex-end;
      margin-bottom: 12px;

      // 编辑态输入框贴合内容高度，不沿用主输入区的 4 行最小高度
      .ai-slash-input {
        min-height: auto;
      }

      .user-edit-footer {
        display: flex;
        gap: 8px;
        align-items: center;
        justify-content: flex-end;
        width: 100%;
      }
    }

    .user-shortcut-render {
      margin-bottom: 12px;
    }

    &:hover {
      .ai-user-message-tools {
        visibility: visible;
      }
    }
  }
</style>
