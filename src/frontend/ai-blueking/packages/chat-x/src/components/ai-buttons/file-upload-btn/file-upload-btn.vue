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
        content: t('上传图片, 最多支持上传 3 个, 最大支持 2.4MB'),
        theme: 'ai-chat-box',
        offset: [0, 16],
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
  import { useTemplateRef } from 'vue';

  import { Message } from 'bkui-vue';
  import { directive as vTippy } from 'vue-tippy';

  import { isEn, MAX_UPLOAD_FILE_SIZE } from '../../../common';
  import { FileUploadIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import { formatUploadNotAddedMessage } from '../../../utils';

  import type { AITippyProps } from '../../../types';

  import 'tippy.js/dist/tippy.css';

  export type FileUploadBtnProps = {
    accept?: string;
    maxFiles?: number;
    multiple?: boolean;
    tippyOptions?: AITippyProps;
  };
  withDefaults(defineProps<FileUploadBtnProps>(), {
    accept: 'image/*', // 默认允许常见图片类型（含 SVG）
    maxFiles: 3, // 预留/文档用；实际上传个数由上层（如 ChatInput）校验
    multiple: true,
  });
  const emit = defineEmits<{
    (e: 'upload', files: File[]): void;
  }>();

  const fileInputRef = useTemplateRef<HTMLInputElement>('fileInputRef');

  const handleClickUpload = () => {
    fileInputRef.value?.click();
  };
  const handleFileInputChange = (event: Event) => {
    const target = event.target as HTMLInputElement;
    const files = target.files;
    if (files?.length) {
      const maxMb = (MAX_UPLOAD_FILE_SIZE / (1024 * 1024)).toFixed(1);
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
          message: formatUploadNotAddedMessage(sizeRejected, maxMb, isEn),
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
</style>
