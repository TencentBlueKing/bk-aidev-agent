<template>
  <motion.div
    v-if="!hasSessionContents"
    class="greeting-box"
    :transition="{
      duration: 0.5,
      ease: [0.33, 1, 0.68, 1],
      type: 'tween',
    }"
    :animate="{ opacity: 1 }"
    :initial="{ opacity: 1 }"
  >
    <div class="greeting-title">
      {{ title }}
    </div>
    <div class="greeting-animation-wrapper">
      <motion.div
        class="greeting-text"
        :transition="{
          duration: 0.5,
          ease: [0.25, 0.46, 0.45, 0.94],
          delay: 0,
        }"
        :animate="{
          opacity: 1,
          y: 0,
        }"
        :initial="{
          opacity: 0,
          y: -20,
        }"
      >
        <div
          ref="greetingTextRef"
          class="greeting-markdown"
          v-html="renderedGreetingText"
        ></div>
      </motion.div>
    </div>
  </motion.div>
</template>

<script setup lang="ts">
  import { motion } from 'motion-v';
  import { computed, ref, onMounted, onUpdated } from 'vue';

  interface Props {
    title: string;
    greetingText: string;
    hasSessionContents: boolean;
    renderMarkdown: (text: string) => string;
    greetingMaxHeight: number;
  }

  const props = defineProps<Props>();

  const greetingTextRef = ref<HTMLElement | null>(null);
  const greetingTextHeight = ref(0);

  const renderedGreetingText = computed(() => {
    return props.renderMarkdown(props.greetingText);
  });

  const updateGreetingTextHeight = () => {
    if (greetingTextRef.value) {
      greetingTextHeight.value = greetingTextRef.value.offsetHeight;
    }
  };

  const getGreetingHeight = () => {
    return greetingTextRef.value?.offsetHeight || 0;
  };

  defineExpose({
    greetingTextRef,
    greetingTextHeight,
    updateGreetingTextHeight,
    getGreetingHeight,
  });

  onMounted(() => {
    updateGreetingTextHeight();
  });

  onUpdated(() => {
    updateGreetingTextHeight();
  });
</script>

<style lang="scss" scoped>
  .greeting-box {
    position: absolute;
    top: 92px;
    left: 50%;
    z-index: 2;
    display: flex;
    flex-direction: column;
    gap: 8px;
    align-items: center;
    width: 100%;
    transform: translateX(-50%);

    .greeting-animation-wrapper {
      overflow: hidden;
    }

    .greeting-title {
      margin-bottom: 22px;
      font-size: 21px;
      font-weight: 700;
      line-height: 24px;
      color: #313238;
    }

    .greeting-text {
      width: 100%;
      max-width: 600px;
      max-height: v-bind('greetingMaxHeight + "px"');
      font-size: 14px;
      line-height: 22px;
      color: #4d4f56;
      transform-origin: center top;
      overflow-y: auto;
      padding: 8px 0;

      // greeting-markdown 样式现在从公共样式文件导入
    }
  }
</style>
