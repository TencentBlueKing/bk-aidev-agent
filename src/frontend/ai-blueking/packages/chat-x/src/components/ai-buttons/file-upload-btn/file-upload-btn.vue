<template>
  <div class="ai-file-upload-btn">
    <input
      ref="fileInputRef"
      :accept="accept"
      class="file-upload-btn-input"
      multiple
      type="file"
      @change="handleFileInputChange"
    />
    <span
      v-tippy="{
        ...tippyOptions,
        content: uploadTip,
        theme: 'ai-chat-box ai-file-upload-tip',
        offset: [0, 16],
        maxWidth: 420,
      }"
      class="ai-shortcut-btn file-upload-btn-icon"
      @click="handleClickUpload"
    >
      <slot>
        <FileUploadIcon />
      </slot>
    </span>
  </div>
</template>
<script setup lang="ts">
  import { computed, useTemplateRef } from 'vue';

  import { Message } from 'bkui-vue';
  import { directive as vTippy } from 'vue-tippy';

  import { isEn, MAX_UPLOAD_FILE_SIZE, MAX_UPLOAD_FILES } from '../../../common';
  import { FileUploadIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import { formatDefaultUploadAcceptTip, formatUploadNotAddedMessage, isDefaultUploadAccept } from '../../../utils';

  import type { AITippyProps } from '../../../types';

  import 'tippy.js/dist/tippy.css';

  export type FileUploadBtnProps = {
    accept?: string;
    multiple?: boolean;
    tippyOptions?: AITippyProps;
  };
  const props = withDefaults(defineProps<FileUploadBtnProps>(), {
    // 不限制文件类型：缺省时不下发 accept，系统文件选择器不做过滤；ChatInput 会传入默认允许列表
    accept: undefined,
    multiple: true,
  });
  const emit = defineEmits<{
    (e: 'upload', files: File[]): void;
  }>();

  const fileInputRef = useTemplateRef<HTMLInputElement>('fileInputRef');

  const maxUploadMb = (MAX_UPLOAD_FILE_SIZE / (1024 * 1024)).toFixed(1);
  // 限制值随常量变化；有 accept 时补上支持格式，默认列表用分类文案
  const uploadTip = computed(() => {
    const base = t('上传文件，最多支持 {count} 个，单个最大 {size}MB')
      .replace('{count}', String(MAX_UPLOAD_FILES))
      .replace('{size}', maxUploadMb);
    if (!props.accept) {
      return base;
    }
    const formatTip = isDefaultUploadAccept(props.accept)
      ? formatDefaultUploadAcceptTip(isEn)
      : t('支持格式：{formats}').replace('{formats}', props.accept);
    return `${base}\n${formatTip}`;
  });

  const handleClickUpload = () => {
    fileInputRef.value?.click();
  };
  const handleFileInputChange = (event: Event) => {
    const target = event.target as HTMLInputElement;
    const files = target.files;
    if (files?.length) {
      const picked = Array.from(files);
      const toEmit: File[] = [];
      let sizeRejected = 0;
      for (const file of picked) {
        if (file.size > 0 && file.size < MAX_UPLOAD_FILE_SIZE) {
          toEmit.push(file);
        } else {
          sizeRejected += 1;
        }
      }
      // 上传个数上限由上层（如 ChatInput）统一处理并提示，避免与按钮层「单次截断」各弹一条 Message
      if (sizeRejected > 0) {
        Message({
          message: formatUploadNotAddedMessage(sizeRejected, maxUploadMb, isEn),
          theme: 'error',
        });
      }
      if (toEmit.length) {
        emit('upload', toEmit);
      }
    }
    target.value = '';
  };
</script>
<style lang="scss">
  .ai-file-upload-btn {
    display: flex;
    align-items: center;

    .file-upload-btn-input {
      display: none;
    }

    .file-upload-btn-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 32px;
      height: 32px;
      padding: 0;
      font-size: var(--ai-icon-size-sm, 16px); // small=16px / normal=18px
      color: #979ba5;
      border-radius: 8px;
      transition: background-color 0.2s;

      &:hover {
        cursor: pointer;
        background: #f0f1f5;
      }
    }
  }

  .tippy-box[data-theme~='ai-file-upload-tip'] {
    .tippy-content {
      white-space: pre-line;
    }
  }
</style>
