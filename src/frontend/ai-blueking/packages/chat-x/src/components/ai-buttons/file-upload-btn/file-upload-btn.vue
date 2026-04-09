<template>
  <div class="file-upload-btn">
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

  import { isEn, MAX_UPLOAD_FILE_SIZE, MAX_UPLOAD_FILES } from '../../../common';
  import { FileUploadIcon } from '../../../icons';
  import { t } from '../../../lang/lang';

  import type { AITippyProps } from '../../../types';

  import 'tippy.js/dist/tippy.css';

  export type FileUploadBtnProps = {
    accept?: string;
    maxFiles?: number;
    multiple?: boolean;
    tippyOptions?: AITippyProps;
  };
  const props = withDefaults(defineProps<FileUploadBtnProps>(), {
    accept: 'image/*', // 默认只允许上传图片
    maxFiles: 3,
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
      if (files.length > Math.max(props.maxFiles, MAX_UPLOAD_FILES)) {
        Message({
          message: isEn ? `You can only upload up to ${props.maxFiles} files` : `最多上传${props.maxFiles}个文件`,
          theme: 'error',
        });
        return;
      }
      // 限制最大上传文件数量
      emit(
        'upload',
        Array.from(files).filter(file => file.size > 0 && file.size < MAX_UPLOAD_FILE_SIZE),
      );
    }
    target.value = '';
  };
</script>
<style lang="scss">
  .file-upload-btn {
    display: flex;
    align-items: center;

    .file-upload-btn-input {
      display: none;
    }

    .file-upload-btn-icon {
      display: flex;
      align-items: center;
      justify-content: flex-start;
      width: 24px;
      height: 24px;
      font-size: 16px;
      color: #979ba5;

      &:hover {
        cursor: pointer;
      }
    }
  }
</style>
