<template>
  <!-- 高亮结果由 highlight.js 生成，未识别语言时走 escapeHtml 兜底，无注入风险 -->
  <pre class="ai-artifact-code-preview"><code class="hljs" v-html="html" /></pre>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import hljs from 'highlight.js';

  import 'highlight.js/styles/github-dark.css';

  /** highlight.js 自身别名表未覆盖的扩展名，需显式指定语言 */
  const HLJS_LANGUAGE_ALIAS: Record<string, string> = {
    cfg: 'ini',
    conf: 'ini',
    dockerignore: 'plaintext',
    editorconfig: 'ini',
    env: 'ini',
    gitignore: 'plaintext',
    jsonc: 'json',
    jsx: 'javascript',
    tsx: 'typescript',
    vue: 'xml',
    zsh: 'bash',
  };

  /** 超大文本跳过高亮，避免同步解析长时间阻塞主线程 */
  const MAX_HIGHLIGHT_LENGTH = 300_000;

  const props = defineProps<{
    content: string;
    // 归一化后的扩展名，用于定位 highlight.js 语言
    extension: string;
  }>();

  const escapeHtml = (text: string): string =>
    text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

  const resolveLanguage = (extension: string): string => {
    const alias = HLJS_LANGUAGE_ALIAS[extension];
    if (alias) {
      return alias;
    }
    return hljs.getLanguage(extension) ? extension : 'plaintext';
  };

  const html = computed(() => {
    const { content } = props;
    if (!content) {
      return '';
    }

    const language = resolveLanguage(props.extension);
    if (language === 'plaintext' || content.length > MAX_HIGHLIGHT_LENGTH) {
      return escapeHtml(content);
    }

    try {
      return hljs.highlight(content, { language, ignoreIllegals: true }).value;
    } catch {
      return escapeHtml(content);
    }
  });
</script>
<style lang="scss">
  .ai-artifact-code-preview {
    width: 100%;
    height: 100%;
    padding: 12px 16px;
    margin: 0;
    overflow: auto;
    background-color: #282c34;
    border-radius: 4px;

    code {
      display: block;
      min-height: 100%;
      padding: 0;
      overflow: visible;
      font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;
      font-size: 13px;
      line-height: 1.5;
      color: #abb2bf;
      white-space: pre;
      background: transparent;
    }
  }
</style>
