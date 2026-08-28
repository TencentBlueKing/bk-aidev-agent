<template>
  <div
    class="ai-chat-input-container"
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
        :placeholder="resolvedPlaceholder"
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
        <template #before-send>
          <slot
            name="model-selector"
            v-bind="{ models, selectedModel }"
          >
            <ModelSelector
              v-if="models?.length"
              v-model="selectedModel"
              class="chat-input-model-selector"
              :models="models"
              :tippy-options="tippyOptions"
              @change="handleModelChange"
            />
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
  import { type KeyboardPayload } from '../../edix';
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
  import { buildDefaultPlaceholder } from './build-default-placeholder';
  import AiSlashInput from './ai-slash-input/ai-slash-input.vue';
  import { tagSchemaToMessageString } from './ai-slash-input/constants';
  import InputAttachment from './input-attachment/input-attachment.vue';
  import { ModelSelector } from './model-selector';

  import type { IModelOption } from './model-selector';

  const aiSlashInputRef = useTemplateRef<InstanceType<typeof AiSlashInput>>('aiSlashInputRef');
  const filesRef = useTemplateRef<HTMLDivElement>('filesRef');
  const citeModel = defineModel<string>('cite', {
    required: false,
    default: '',
  });
  // 当前选中的模型（值为 llm_name，v-model:selectedModel）
  const selectedModel = defineModel<string>('selectedModel', {
    required: false,
  });
  const maxHeight = shallowRef(280);
  export type ChatInputEmits = {
    (e: 'selectShortcut', shortcut: Shortcut): void;
    (e: 'deleteShortcut'): void;
    (e: 'update:modelValue', value: string | TagSchema, selectedResourceList: IAiSlashMenuItem[]): void;
    (e: 'modelChange', model: IModelOption): void;
  };
  export type ChatInputProps = {
    defaultUploadFiles?: UploadFile[];
    inputMaxHeight?: number;
    messageStatus?: MessageStatus;
    models?: IModelOption[]; // 可选模型列表，传入后在发送按钮左侧展示模型选择器
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
    prompts: () => [],
    resources: () => [],
    skills: () => [],
    inputMaxHeight: 280,
    supportUpload: true,
  });
  const emit = defineEmits<ChatInputEmits>();
  const resolvedPlaceholder = computed(() => {
    if (props.placeholder !== undefined) {
      return props.placeholder;
    }
    return buildDefaultPlaceholder({
      isEn,
      hasSkills: (props.skills?.length ?? 0) > 0,
      hasPrompts: (props.prompts?.length ?? 0) > 0,
      hasResources: (props.resources?.length ?? 0) > 0,
    });
  });
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
    if (Array.isArray(props.modelValue) && !tagSchemaToMessageString(props.modelValue).trim()) {
      return MessageStatus.Disabled;
    }
    return props.messageStatus;
  });

  watchPostEffect(() => {
    const defaultHeight = props.inputMaxHeight || 280;
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
        content = typeof props.modelValue === 'string' ? props.modelValue : tagSchemaToMessageString(props.modelValue);
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
            text: tagSchemaToMessageString(props.modelValue as TagSchema),
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
  const handleModelChange = (model: IModelOption) => {
    emit('modelChange', model);
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

  .ai-chat-input-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    padding: 0 16px 16px;

    .chat-input {
      position: relative;
      display: flex;
      flex-direction: column;
      width: 100%;
      min-width: variables.$chat-input-min-width;
      max-width: variables.$chat-input-max-width;
      min-height: 110px;
      max-height: 280px; // 与 inputMaxHeight 默认一致；有文件时由 inline style 叠加预览区高度
      overflow: hidden; // 触顶后由内部 ai-slash-input 滚动
      padding-bottom: var(--ai-spacing-comfortable, 8px);
      background: #fff;
      border: 1px solid #dcdee5; // 未激活：灰色描边
      border-radius: 8px;

      &::before {
        z-index: var(--chat-z-index);
        opacity: 0;
        transition: opacity 0.15s ease;

        @include border.linear-gradient-border(180deg, #6cbaff, #3a84ff);
      }

      // 激活（编辑区 / 内部控件聚焦）时切换为蓝色渐变描边
      &:focus-within {
        border-color: transparent;

        &::before {
          opacity: 1;
        }
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

      // 模型选择器靠右与发送按钮成组：吸收左侧剩余空间，把自身与发送按钮一起推到右端
      .chat-input-model-selector {
        margin-left: auto;
      }

      // 已选快捷指令 tag：默认态与 bkui Tag 一致，hover 使用 shortcut 语义色
      .selected-shortcut-btn {
        height: 32px;
        padding: 0 10px;
        color: #3a84ff;
        background: #e1ecff;
        transition:
          background-color 0.2s,
          color 0.2s;

        .ai-common-icon {
          color: #3a84ff;
        }

        &:hover {
          color: #1768ef;
          background: #cddffe;

          .ai-common-icon {
            color: #3a84ff;
          }
        }
      }

      .ai-shortcut-btns-item {
        height: 32px;
        padding: 0 8px;
        border-radius: 8px;
      }
    }
  }
</style>
