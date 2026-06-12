<template>
  <div
    class="chat-input-container"
    :style="{ '--chat-z-index': CHAT_Z_INDEX }"
  >
    <slot name="top" />
    <slot name="interrupt" />
    <div
      class="chat-input"
      :style="{ maxHeight: maxHeight + 'px' }"
    >
      <slot name="input-header">
        <CiteContent
          v-if="citeModel"
          class="chat-input-cite"
          :content="citeModel"
          @close="handleCloseCite"
        />
      </slot>
      <slot
        name="files"
        v-bind="{ files: uploadFiles }"
      >
        <div
          v-if="uploadFiles.length"
          ref="filesRef"
          class="chat-input-files"
        >
          <FileContent
            :files="uploadFiles"
            @delete-file="handleDeleteFile"
          />
        </div>
      </slot>
      <AiSlashInput
        ref="aiSlashInputRef"
        :model-value="modelValue"
        :placeholder="placeholder"
        :prompts="prompts"
        :resources="resources"
        :skills="skills"
        @keydown="handleKeyDown"
        @update:model-value="handleUpdateModelValue"
        @upload="handleUpload"
      />
      <InputAttachment
        :message-state="messageState"
        :send-disabled-tip="sendDisabledTip"
        :tippy-options="tippyOptions"
        @send-message="handleSendMessage"
        @stop-sending="handleStopSending"
      >
        <template #default>
          <FileUploadBtn
            v-if="supportUpload"
            :tippy-options="tippyOptions"
            @upload="handleUpload"
          />
          <span
            v-if="supportUpload && (shortcuts?.length || selectedShortcut)"
            class="ai-divider"
          />
          <slot name="attachment">
            <ShortcutBtns
              v-if="shortcuts && !selectedShortcut"
              :shortcuts="shortcuts"
              @select-shortcut="handleSelectShortcut"
            />
            <ShortcutBtn
              v-if="selectedShortcut"
              class="selected-shortcut-btn"
              :shortcut="selectedShortcut"
            >
              <template #append>
                <CloseIcon @click="handleDeleteShortcut" />
              </template>
            </ShortcutBtn>
          </slot>
        </template>
        <template #send-icon>
          <slot name="send-icon" />
        </template>
      </InputAttachment>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, ref as deepRef, shallowRef, useTemplateRef, watchPostEffect } from 'vue';

  import { Message } from 'bkui-vue';

  import {
    type Interrupt,
    type InterruptResume,
    type UserMessage,
    MessageContentType,
    MessageStatus,
  } from '../../ag-ui/types';
  import { CHAT_Z_INDEX, isEn, MAX_UPLOAD_FILE_SIZE, MAX_UPLOAD_FILES } from '../../common';
  import { type KeyboardPayload, docToString } from '../../edix';
  import { CloseIcon } from '../../icons';
  import {
    type AITippyProps,
    type IAiSlashMenuItem,
    type ISkillListItem,
    type Shortcut,
    type TagSchema,
    type UploadFile,
    UploadStatus,
  } from '../../types';
  import { formatUploadNotAddedMessage } from '../../utils';
  import FileUploadBtn from '../ai-buttons/file-upload-btn/file-upload-btn.vue';
  import ShortcutBtn from '../ai-shortcut/shortcut-btn/shortcut-btn.vue';
  import ShortcutBtns from '../ai-shortcut/shortcut-btns/shortcut-btns.vue';
  import CiteContent from '../chat-content/cite-content/cite-content.vue';
  import FileContent from '../chat-content/file-content/file-content.vue';
  import AiSlashInput from './ai-slash-input/ai-slash-input.vue';
  import InputAttachment from './input-attachment/input-attachment.vue';

  const aiSlashInputRef = useTemplateRef<InstanceType<typeof AiSlashInput>>('aiSlashInputRef');
  const filesRef = useTemplateRef<HTMLDivElement>('filesRef');
  const citeModel = defineModel<string>('cite', {
    required: false,
    default: '',
  });
  const maxHeight = shallowRef(200);
  export type ChatInputEmits = {
    (e: 'selectShortcut', shortcut: Shortcut): void;
    (e: 'deleteShortcut'): void;
    (e: 'update:modelValue', value: string | TagSchema, selectedResourceList: IAiSlashMenuItem[]): void;
  };
  export type ChatInputProps = {
    defaultUploadFiles?: UploadFile[];
    inputMaxHeight?: number;
    messageStatus?: MessageStatus;
    modelValue: string | TagSchema;
    onSendMessage?: (
      message: UserMessage['content'],
      docSchema: TagSchema,
      options?: { interrupt?: Interrupt; payload?: InterruptResume },
    ) => Promise<void>;
    onStopSending?: () => Promise<void>;
    onUpload?: (files: File) => Promise<{
      download_url?: string;
    }>;
    placeholder?: string;
    prompts?: string[];
    resources?: IAiSlashMenuItem[];
    sendDisabledTip?: string;
    shortcutId?: string;
    shortcuts?: Shortcut[];
    skills?: ISkillListItem[];
    supportUpload?: boolean; // 是否支持上传文件 默认是true
    tippyOptions?: AITippyProps; // tips配置
  };
  const props = withDefaults(defineProps<ChatInputProps>(), {
    placeholder: isEn
      ? `Input "/" to trigger skill
Input "\\" to trigger prompt
Input "@" to trigger tool and MCP
Use Shift + Enter to enter a new line`
      : `输入 "/" 唤出 Skill
输入 "\\" 唤出 Prompt
输入 "@" 唤出 工具和 MCP
通过 Shift + Enter 进行换行输入`,
    prompts: () => [],
    resources: () => [],
    skills: () => [],
    inputMaxHeight: 200,
    supportUpload: true,
  });
  const emit = defineEmits<ChatInputEmits>();
  const uploadFiles = deepRef<Partial<UploadFile>[]>(props.defaultUploadFiles || []);
  const selectedShortcut = computed(() => {
    return props.shortcuts?.find(shortcut => shortcut.id === props.shortcutId);
  });
  const messageState = computed(() => {
    if (
      props.messageStatus &&
      [MessageStatus.Pending, MessageStatus.Streaming, MessageStatus.Fetching].includes(props.messageStatus)
    ) {
      return props.messageStatus;
    }
    if (props.modelValue?.length < 1) {
      return MessageStatus.Disabled;
    }
    if (Array.isArray(props.modelValue) && !docToString(props.modelValue).trim()) {
      return MessageStatus.Disabled;
    }
    return props.messageStatus;
  });

  watchPostEffect(() => {
    const defaultHeight = props.inputMaxHeight || 200;
    if (uploadFiles.value.length < 1 || !filesRef.value) {
      maxHeight.value = defaultHeight;
      return;
    }
    const filesHeight = filesRef.value?.clientHeight || 0;
    maxHeight.value = defaultHeight + filesHeight;
  });
  const handleSendMessage = async () => {
    try {
      if (props.sendDisabledTip) {
        return;
      }
      aiSlashInputRef.value?.cleanup?.();
      let content: undefined | UserMessage['content'] = undefined;

      // 如果没有上传文件，则使用输入框的值
      if (!uploadFiles.value?.length) {
        content = typeof props.modelValue === 'string' ? props.modelValue : docToString(props.modelValue);
      } else {
        // 如果上传了文件，则使用上传的文件
        content = uploadFiles.value?.slice().map(file => ({
          type: MessageContentType.Binary,
          url: file.url,
          mimeType: file.file?.type || '',
          filename: file.file?.name || '',
        }));
        // 如果输入框有值，则将输入框的值作为内容
        if (props.modelValue) {
          content.push({
            type: MessageContentType.Text,
            text: docToString(props.modelValue as TagSchema),
          });
        }
      }
      props.onSendMessage?.(content, props.modelValue as TagSchema);
      uploadFiles.value = [];
    } catch (error) {
      console.error(error);
    }
  };
  const handleKeyDown = (event: KeyboardEvent & KeyboardPayload) => {
    if (event.key === 'Enter' || event.key === 'NumpadEnter') {
      if (event.shiftKey) {
        return;
      }
      if (messageState.value === MessageStatus.Disabled) {
        return;
      }
      if (props.sendDisabledTip) {
        return;
      }
      if (
        messageState.value === MessageStatus.Fetching ||
        messageState.value === MessageStatus.Streaming ||
        messageState.value === MessageStatus.Pending
      ) {
        return;
      }
      handleSendMessage();
    }
  };
  const handleStopSending = async () => {
    try {
      props.onStopSending?.();
    } catch (error) {
      console.error(error);
    }
  };
  const handleCloseCite = () => {
    citeModel.value = '';
  };
  const handleSelectShortcut = (shortcut: Shortcut) => {
    emit('selectShortcut', shortcut);
  };
  const handleDeleteShortcut = () => {
    emit('deleteShortcut');
  };
  const fileKey = (f: File) => `${f.name}_${f.size}_${f.lastModified}`;
  const maxUploadMb = (MAX_UPLOAD_FILE_SIZE / (1024 * 1024)).toFixed(1);
  const handleUpload = async (files: File[]) => {
    if (!props.supportUpload) {
      return;
    }
    if (uploadFiles.value.length >= MAX_UPLOAD_FILES) {
      if (files.length > 0) {
        Message({
          message: formatUploadNotAddedMessage(files.length, maxUploadMb, isEn),
          theme: 'error',
        });
      }
      return;
    }
    const existingKeys = new Set(uploadFiles.value.map(item => (item.file ? fileKey(item.file) : '')));
    let notUploadedCount = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (uploadFiles.value.length >= MAX_UPLOAD_FILES) {
        notUploadedCount += files.length - i;
        break;
      }
      const key = fileKey(file);
      if (existingKeys.has(key)) {
        notUploadedCount += 1;
        continue;
      }
      if (file.size <= 0 || file.size >= MAX_UPLOAD_FILE_SIZE) {
        notUploadedCount += 1;
        continue;
      }
      existingKeys.add(key);
      const fileItem: Partial<UploadFile> = {
        file,
        status: UploadStatus.Pending,
      };
      uploadFiles.value.push(fileItem);
      props
        .onUpload?.(file)
        .then((res: { download_url?: string }) => {
          if (res && typeof res === 'object' && 'download_url' in res) {
            fileItem.url = res.download_url;
            fileItem.status = UploadStatus.Success;
            return;
          }
          fileItem.status = UploadStatus.Error;
        })
        .catch(() => {
          fileItem.status = UploadStatus.Error;
        });
    }
    if (notUploadedCount > 0) {
      Message({
        message: formatUploadNotAddedMessage(notUploadedCount, maxUploadMb, isEn),
        theme: 'error',
      });
    }
  };
  const handleDeleteFile = (file: Partial<UploadFile>) => {
    uploadFiles.value = uploadFiles.value.filter(item => {
      if (item.file) {
        return item.file !== file.file;
      }
      if (item.url) {
        return item.url !== file.url;
      }
      if (item.filename) {
        return item.filename !== file.filename;
      }
      return true;
    });
  };
  const handleUpdateModelValue = (value: string | TagSchema, selectedResourceList: IAiSlashMenuItem[]) => {
    emit('update:modelValue', value, selectedResourceList);
  };
  /**
   * 聚焦输入框
   */
  const focus = () => {
    aiSlashInputRef.value?.focus?.();
  };
  defineExpose({
    focus,
    triggerSendMessage: handleSendMessage,
  });
</script>
<style lang="scss">
  @use '../../styles/variables.scss' as variables;
  @use '../../styles/border.scss' as border;

  .chat-input-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;

    .chat-input {
      position: relative;
      display: flex;
      flex-direction: column;
      width: 100%;
      min-width: variables.$chat-input-min-width;
      max-width: variables.$chat-input-max-width;
      min-height: 110px;
      max-height: 200px;
      background: #fff;
      border-radius: 8px;

      &::before {
        z-index: var(--chat-z-index);

        @include border.linear-gradient-border(180deg, #6cbaff, #3a84ff);
      }

      .chat-input-cite {
        margin: 8px 8px 0;
        background: #f0f1f5;

        .ai-cite-content-text {
          color: #4d4f56;
        }
      }

      .chat-input-files {
        display: flex;
        width: 100%;
        padding: 8px 8px 0;
      }

      .selected-shortcut-btn {
        height: 24px;
        padding: 0 10px;
        color: #3a84ff;
        background: #e1ecff;

        .ai-common-icon {
          color: #3a84ff;
        }
      }
    }
  }
</style>
