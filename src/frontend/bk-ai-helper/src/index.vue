<template>
  <div class="bk-ai-helper">
    <img
      alt="logo"
      class="bk-ai-helper-logo"
      src="./assets/ai.png"
    />
    <p
      ref="triggerRef"
      class="bk-ai-helper-title"
    >
      {{ props.title }}
    </p>

    <!-- Tippy 弹层内容 -->
    <div
      ref="popoverContent"
      class="bk-ai-helper-popover"
    >
      <div class="popover-header">
        <span class="popover-title">{{ props.formTitle }}</span>
        <BkErrorIcon
          class="close-icon"
          fill="#c4c6cc"
          @click.stop="closeTippy"
        />
      </div>
      <div class="popover-body">
        <BkInput
          ref="inputRef"
          v-model="input"
          :disabled="loading"
          :placeholder="props.placeholder"
          :resize="false"
          :rows="6"
          type="textarea"
          v-bind="formOptions"
        />
        <div
          class="arrow-icon-container"
          :class="{ disabled: !canSubmit }"
        >
          <BkLoadingIcon
            v-if="loading"
            class="loading-icon"
          />
          <BkArrowsRightIcon
            v-else
            class="arrow-icon"
            @click.stop="handleSubmit"
          />
        </div>
        <!-- Loading 遮罩 -->
        <div
          v-if="loading"
          class="loading-mask"
        >
          <div class="loading-content">
            <BkLoadingIcon class="mask-loading-icon" />
            <span class="loading-text">{{ t('思考中...') }}</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onMounted, onUnmounted, ref } from 'vue';

  import { Input as BkInput, Message } from 'bkui-vue';
  import { ArrowsRight as BkArrowsRightIcon, Error as BkErrorIcon, Loading as BkLoadingIcon } from 'bkui-vue/lib/icon';
  import tippy, { type Instance } from 'tippy.js';

  import { t } from './lang';
  import { type ChatCompletionResponse, sendChatRequest } from './utils';

  import 'tippy.js/dist/tippy.css';

  defineOptions({
    name: 'BkAiHelper',
  });

  const input = ref('');
  const inputRef = ref<InstanceType<typeof BkInput> | null>(null);
  const loading = ref(false);
  const triggerRef = ref<HTMLElement | null>(null);
  const popoverContent = ref<HTMLElement | null>(null);
  let tippyInstance: Instance | null = null;

  // 是否可以提交
  const canSubmit = computed(() => !loading.value && input.value.trim().length > 0);

  const props = withDefaults(
    defineProps<{
      baseUrl?: string;
      formOptions?: Record<string, unknown>;
      formTitle?: string;
      placeholder?: string;
      prompt?: string;
      title?: string;
    }>(),
    {
      baseUrl: AI_HELPER_BASE_URL || '',
      formOptions: undefined,
      formTitle: t('规则描述'),
      placeholder: t('请输入规则描述（Enter 发送，Shift + Enter 换行）'),
      title: t('帮我写'),
      prompt: '',
    },
  );

  const emit = defineEmits<{
    error: [error: Error];
    response: [response: string];
    success: [response: ChatCompletionResponse];
  }>();

  const closeTippy = () => {
    tippyInstance?.hide();
  };

  // 处理键盘事件：Enter 发送，Shift + Enter 换行
  const handleKeydown = (event: KeyboardEvent) => {
    if ((event.code === 'Enter' || event.key === 'Enter' || event.keyCode === 13) && !event.shiftKey) {
      event.preventDefault(); // 阻止默认的换行行为
      handleSubmit();
    }
  };

  // 提交处理
  const handleSubmit = async () => {
    // 如果不能提交，直接返回
    if (!canSubmit.value) {
      return;
    }

    if (!props.baseUrl) {
      Message({
        theme: 'error',
        message: t('缺少 baseUrl 配置'),
      });
      return;
    }

    loading.value = true;

    try {
      const response = await sendChatRequest(input.value, {
        baseUrl: props.baseUrl,
        prompt: props.prompt,
      });
      Message({
        theme: 'success',
        message: t('提交成功'),
      });
      emit('success', response);
      emit('response', response.data.choices[0].delta.content as string);
      closeTippy();
      input.value = '';
    } catch (error) {
      const err = error instanceof Error ? error : new Error(String(error));
      Message({
        theme: 'error',
        message: `${t('请求失败')}: ${err.message}`,
      });
      emit('error', err);
    } finally {
      loading.value = false;
    }
  };

  onMounted(() => {
    if (triggerRef.value && popoverContent.value) {
      tippyInstance = tippy(triggerRef.value, {
        content: popoverContent.value,
        trigger: 'click',
        interactive: true,
        placement: 'bottom-start',
        theme: 'light',
        arrow: false,
        maxWidth: 'none',
        appendTo: () => document.body,
        onShow(_instance) {
          // 显示时移除隐藏样式
          if (popoverContent.value) {
            popoverContent.value.style.display = 'block';
          }
        },
        onHidden(_instance) {
          // 隐藏后恢复隐藏样式
          if (popoverContent.value) {
            popoverContent.value.style.display = 'none';
          }
        },
      });
    }

    // 监听 textarea 的 keydown 事件
    if (inputRef.value) {
      const textarea = (inputRef.value.$el as HTMLElement)?.querySelector('textarea');
      if (textarea) {
        textarea.addEventListener('keydown', handleKeydown);
      }
    }
  });

  onUnmounted(() => {
    // 清理事件监听
    if (inputRef.value) {
      const textarea = (inputRef.value.$el as HTMLElement)?.querySelector('textarea');
      if (textarea) {
        textarea.removeEventListener('keydown', handleKeydown);
      }
    }
  });
</script>

<style scoped lang="scss">
  .bk-ai-helper {
    display: flex;
    gap: 4px;
    align-items: center;
    font-size: 12px;

    .bk-ai-helper-logo {
      width: 15px;
      height: 15px;
    }

    .bk-ai-helper-title {
      font-size: 12px;
      line-height: 20px;
      color: #3a84ff;
      cursor: pointer;
      user-select: none;
    }
  }

  .bk-ai-helper-popover {
    display: none;
    width: 500px;
    padding: 16px;
    background: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgb(0 0 0 / 15%);

    .popover-header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 12px;

      .popover-title {
        font-size: 14px;
        font-weight: 500;
        color: #313238;
      }

      .close-icon {
        cursor: pointer;

        &:hover {
          fill: #979ba5;
        }
      }
    }

    .popover-body {
      position: relative;

      @keyframes fade-in {
        from {
          opacity: 0;
        }

        to {
          opacity: 1;
        }
      }

      @keyframes pulse {
        0%,
        100% {
          opacity: 1;
        }

        50% {
          opacity: 0.5;
        }
      }

      @keyframes rotate {
        from {
          transform: rotate(0deg);
        }

        to {
          transform: rotate(360deg);
        }
      }

      :deep(.bk-input) {
        width: 100%;
      }

      .arrow-icon-container {
        position: absolute;
        right: 6px;
        bottom: 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        width: 20px;
        height: 20px;
        cursor: pointer;
        background: #3a84ff;
        border-radius: 4px;
        transition: all 0.3s ease;

        &:hover {
          background: #5a97ff;
        }

        .arrow-icon {
          fill: #fff;
          transform: rotate(-90deg);
        }

        .loading-icon {
          fill: #fff;
          animation: rotate 1s linear infinite;
        }

        &.disabled {
          cursor: not-allowed;
          background: #dcdee5;

          &:hover {
            background: #dcdee5;
          }

          .arrow-icon {
            fill: #c4c6cc;
          }
        }
      }

      .loading-mask {
        position: absolute;
        inset: 0;
        z-index: 1;
        display: flex;
        align-items: center;
        justify-content: center;
        background: rgb(255 255 255 / 92%);
        border-radius: 2px;
        backdrop-filter: blur(2px);
        animation: fade-in 0.3s ease;

        .loading-content {
          display: flex;
          flex-direction: column;
          gap: 12px;
          align-items: center;
          padding: 20px;

          .mask-loading-icon {
            font-size: 32px;
            color: #3a84ff;
            animation: rotate 1s linear infinite;
          }

          .loading-text {
            font-size: 14px;
            color: #63656e;
            animation: pulse 1.5s ease-in-out infinite;
          }
        }
      }

      .popover-footer {
        display: none;
        gap: 8px;
        justify-content: flex-end;
        margin-top: 12px;
      }
    }
  }
</style>

<style lang="scss">
  // Tippy 全局样式覆盖
  .tippy-box[data-theme~='light'] {
    padding: 0;
    background-color: transparent;
    box-shadow: none;

    .tippy-content {
      padding: 0;
    }
  }
</style>
