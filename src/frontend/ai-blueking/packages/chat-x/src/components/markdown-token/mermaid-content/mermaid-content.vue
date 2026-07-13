<template>
  <div
    :key="svgDomStr"
    ref="mermaidContentRef"
    class="ai-mermaid-content"
    v-html="svgDomStr"
  />
</template>

<script setup lang="ts">
  import { nextTick, shallowRef, useTemplateRef, watch } from 'vue';

  import throttle from 'lodash/throttle';

  import type { Token } from '../../../markdown-it';
  type MermaidModule = typeof import('mermaid');
  const svgDomStr = shallowRef<string>('');
  const mermaidContentRef = useTemplateRef<HTMLElement>('mermaidContentRef');
  const props = defineProps<{
    token: Token[];
  }>();

  const emit = defineEmits<{
    (e: 'mounted', payload: { el: HTMLElement | null }): void;
  }>();

  // Mermaid 实例
  let mermaidInstance: MermaidModule | null = null;
  // 缓存上一次的 mermaid 代码，避免重复渲染
  let lastMermaidCode = '';

  // 初始化 mermaid
  const getMermaidInstance = async (): Promise<MermaidModule> => {
    if (mermaidInstance) {
      return mermaidInstance;
    }
    if (!mermaidInstance) {
      try {
        mermaidInstance = await import('mermaid');
        mermaidInstance.default.initialize({
          suppressErrorRendering: true,
        });
      } catch (error) {
        console.error('Failed to initialize mermaid:', error);
        throw error;
      }
    }
    return mermaidInstance!;
  };

  /**
   * 从 token 数组中提取 mermaid 代码
   * @param tokens - token 数组
   * @returns mermaid 代码
   */
  const extractMermaidCode = (tokens: Token[]): string => {
    for (const token of tokens) {
      const info = token.info ? token.info.trim() : '';
      if (token.type === 'fence' && info === 'mermaid' && token.content) {
        return token.content;
      }
    }
    return '';
  };
  /**
   * 渲染 mermaid 图表
   * @param tokens - 新的 token 数组
   * @param oldTokens - 旧的 token 数组
   */
  const renderMermaid = throttle(
    async (tokens: Token[]) => {
      const newCode = extractMermaidCode(tokens);
      // 如果代码没有变化，直接返回，避免重复渲染
      if (newCode === lastMermaidCode) {
        return;
      }
      lastMermaidCode = newCode;
      const mermaid = await getMermaidInstance();
      // 渲染
      try {
        const isValid = await mermaid.default.parse(newCode, {
          suppressErrors: true,
        });
        if (!isValid) {
          return;
        }
        const { svg } = await mermaid.default.render(
          'mermaid-content-' + Math.random().toString(36).substring(2, 15),
          newCode,
        );
        if (svgDomStr.value === svg) {
          return;
        }
        svgDomStr.value = svg;
        nextTick(() => {
          emit('mounted', {
            get el() {
              return mermaidContentRef.value;
            },
          });
        });
      } catch (error) {
        console.warn('Failed to render mermaid:', error);
      }
    },
    100,
    {
      leading: true,
      trailing: true,
    },
  );
  // 监听代码变化，实现增量渲染
  watch(() => props.token, renderMermaid, {
    immediate: true,
    deep: true,
  });
</script>

<style lang="scss">
  .ai-mermaid-content {
    width: 100%;
    min-height: 0;
    padding: 8px 12px;
    background-color: #f5f7fa;
    border-radius: 2px;

    svg {
      max-width: 100%;
      height: auto;
    }
  }
</style>
