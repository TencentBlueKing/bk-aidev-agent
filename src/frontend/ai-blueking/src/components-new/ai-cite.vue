<template>
  <section
    class="ai-cite"
    v-show="text"
  >
    <span class="content">
      <span
        class="content-text"
        :class="{ 'show-close-icon': showCloseIcon }"
      >
        <i class="bkai-icon icon-yinyong"></i>
        <span
          ref="citeTextRef"
          class="ai-cite-text"
          >{{ `${t('框选内容')}：${text}` }}</span
        >
      </span>
      <i
        v-if="showCloseIcon"
        class="bkai-icon icon-close-line-2 close-icon"
        @click="$emit('close')"
      ></i>
    </span>
  </section>
</template>

<script setup lang="ts">
  import { nextTick, ref, onMounted, watch } from 'vue';

  import { Instance } from 'tippy.js';

  import { useTooltip } from '../composables/use-tippy';
  import { t } from '../lang';

  const props = defineProps<{
    text: string;
    showCloseIcon?: boolean;
  }>();

  defineEmits<{
    close: [];
  }>();

  const tippyInstance = ref<Instance | null>(null);

  watch(
    () => props.text,
    () => {
      tippyInstance.value && destroyInstance(tippyInstance.value);
      nextTick(() => {
        initTooltip();
      });
    },
  );

  const citeTextRef = ref<HTMLElement | null>(null);

  // 检查文本是否溢出
  const checkTextOverflow = (element: HTMLElement) => {
    return element.scrollWidth > element.clientWidth;
  };

  const { createTooltip, destroyInstance } = useTooltip({
    arrow: true,
    delay: [0, 0],
  });

  // 初始化 tooltip
  const initTooltip = () => {
    if (citeTextRef.value) {
      const element = citeTextRef.value;
      if (checkTextOverflow(element)) {
        tippyInstance.value = createTooltip(element, props.text, {
          appendTo: document.querySelector('.ai-blueking-container-wrapper') as HTMLElement,
        });
      }
    }
  };

  onMounted(() => {
    nextTick(() => {
      initTooltip();
    });
  });
</script>

<style lang="scss" scoped>
  .ai-cite {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: center;
    user-select: none;

    .content {
      position: relative;
      display: flex;
      align-items: center;
      max-width: 100%;
      padding: 4px 8px;
      font-size: 12px;
      line-height: 20px;
      color: #979ba5;
      background-color: #f0f1f5;
      border-radius: 2px;

      &:hover {
        background-color: #eaebf0;
      }

      .content-text {
        display: flex;
        align-items: center;
        max-width: 100%;

        &.show-close-icon {
          max-width: calc(100% - 20px);
        }
      }

      .bkai-icon {
        margin-right: 0;
        font-size: 12px;
        color: #979ba5;
      }

      .icon-yinyong {
        flex-shrink: 0;
        margin-right: 4px;
      }

      .ai-cite-text {
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        cursor: default;
      }

      .close-icon {
        flex-shrink: 0;
        margin-left: 8px;
        cursor: pointer;
      }
    }
  }
</style>
