<template>
  <div class="code-content-wrapper">
    <div class="code-content-header">
      <span class="code-header-language">{{ language }}</span>
      <slot
        name="header"
        v-bind="{
          language,
          token,
        }"
      ></slot>
      <ToolBtn
        id="copy"
        description="复制"
        name="复制"
        @click="handleCopyCode"
      />
    </div>
    <pre class="hljs-pre"><code
      ref="codeRef"
      :class="codeClass"
    ><!-- 已完成的行（高亮显示） --><template
        v-for="(line, index) in completedLines"
        :key="`completed-${index}`"
      ><span class="code-line" v-html="line.html" />{{ '\n' }}</template><!-- 当前正在输入的行 --><span
        v-if="currentLineText"
        class="code-line current-line"
      v-html="currentLineHtml"
    /></code></pre>
  </div>
</template>

<script setup lang="ts">
  import { type VNode, computed, nextTick, shallowRef, useTemplateRef, watch } from 'vue';

  import hljs from 'highlight.js';

  import { MarkdownLanguageMap } from '../../../common';
  import { useClipboard } from '../../../composables';
  import ToolBtn from '../../ai-buttons/tool-btn/tool-btn.vue';

  import type { Token } from '../../../markdown-it';

  import 'highlight.js/styles/github-dark.css';

  interface HighlightedLine {
    // 原始代码内容
    content: string;
    // 高亮后的 HTML
    html: string;
  }
  defineSlots<{
    header: (props: { language: string; token: Token[] }) => null | undefined | VNode;
  }>();
  const props = defineProps<{
    token: Token[];
  }>();

  const emit = defineEmits<{
    (e: 'mounted', payload: { el: HTMLElement | null }): void;
  }>();

  const codeRef = useTemplateRef<HTMLElement>('codeRef');
  const language = shallowRef<string>('');
  const { copy } = useClipboard();

  // 已完成的行（不包含最后一行），高亮显示
  const completedLines = shallowRef<HighlightedLine[]>([]);

  // 当前正在输入的行（最后一行）
  const currentLineText = shallowRef<string>('');
  const currentLineHtml = shallowRef<string>('');

  // 高亮结果缓存
  const lineHighlightCache = new Map<string, string>();
  const MAX_CACHE_SIZE = 500;

  /**
   * 从 token 数组中提取代码内容和语言
   */
  const extractCodeInfo = (tokens: Token[]): { content: string; language: string } => {
    for (const token of tokens) {
      if (token.type === 'fence' || token.type === 'code_block') {
        return {
          content: token.content || '',
          language: token.info?.trim() || '',
        };
      }
    }
    return { content: '', language: '' };
  };

  /**
   * 解析语言标识
   */
  const resolveLanguage = (lang: string): null | string => {
    const mappedLang = MarkdownLanguageMap[lang as keyof typeof MarkdownLanguageMap] || lang;
    if (hljs.getLanguage(mappedLang)) {
      return mappedLang;
    }

    const extension = lang.match(/\.\w+$/)?.[0];
    if (extension) {
      const extLang = extension.slice(1);
      if (hljs.getLanguage(extLang)) {
        return extLang;
      }
    }

    return null;
  };

  /**
   * 高亮单行代码
   */
  const highlightLine = (line: string, languageName: null | string): string => {
    if (!line) {
      return '';
    }

    const cacheKey = `${languageName || ''}:${line}`;
    const cached = lineHighlightCache.get(cacheKey);
    if (cached !== undefined) {
      return cached;
    }

    let result: string;

    if (languageName) {
      try {
        result = hljs.highlight(line, {
          language: languageName,
          ignoreIllegals: true,
        }).value;
      } catch {
        result = escapeHtml(line);
      }
    } else {
      result = escapeHtml(line);
    }

    lineHighlightCache.set(cacheKey, result);

    // 清理过大的缓存
    if (lineHighlightCache.size > MAX_CACHE_SIZE) {
      const keysToDelete = Array.from(lineHighlightCache.keys()).slice(0, Math.floor(MAX_CACHE_SIZE / 2));
      keysToDelete.forEach(key => lineHighlightCache.delete(key));
    }

    return result;
  };

  /**
   * 转义 HTML 特殊字符
   */
  const escapeHtml = (text: string): string => {
    return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  };

  /**
   * 处理代码内容
   * 策略：已完成的行高亮显示，最后一行直接显示文本（打字效果）
   */
  const processContent = (content: string, language: string) => {
    const languageName = resolveLanguage(language);

    // 按换行符分割
    const lines = content.split('\n');

    if (lines.length === 1) {
      completedLines.value = [];
      const text = lines[0] ?? '';
      currentLineText.value = text;
      currentLineHtml.value = text ? highlightLine(text, languageName) : '';
      return;
    }

    // 多行情况：除最后一行外都是已完成的行
    const completed = lines.slice(0, -1);
    const current = lines[lines.length - 1] ?? '';

    // 增量更新已完成的行
    const existingCompleted = completedLines.value;
    const newCompleted: HighlightedLine[] = [];

    for (let i = 0; i < completed.length; i++) {
      const lineContent = completed[i] ?? '';
      const existing = existingCompleted[i];

      // 复用未变化的行
      if (existing && existing.content === lineContent) {
        newCompleted.push(existing);
      } else {
        // 新行或变化的行，进行高亮
        newCompleted.push({
          content: lineContent,
          html: highlightLine(lineContent, languageName),
        });
      }
    }

    completedLines.value = newCompleted;
    currentLineText.value = current;
    currentLineHtml.value = current ? highlightLine(current, languageName) : '';
  };

  /**
   * 计算 code 元素的 class
   */
  const codeClass = computed(() => {
    const { language } = extractCodeInfo(props.token);
    const classes = ['hljs'];

    if (language) {
      classes.push(`language-${language}`);
    }

    return classes.join(' ');
  });

  // 监听 token 变化
  watch(
    () => props.token,
    tokens => {
      const { content, language: languageName } = extractCodeInfo(tokens);
      language.value = languageName;
      processContent(content, languageName);

      nextTick(() => {
        emit('mounted', {
          get el() {
            return codeRef.value;
          },
        });
      });
    },
    {
      immediate: true,
      deep: true,
    },
  );
  const handleCopyCode = () => {
    const code = codeRef.value?.innerText;
    if (code) {
      copy(code);
    }
  };
</script>

<style lang="scss">
  .code-content-wrapper {
    width: 100%;
    margin-bottom: 12px;

    .code-content-header {
      display: flex;
      align-items: center;
      height: 40px;
      padding: 0 12px;
      color: #c4c6cc;
      background-color: #2f333d;
      border: 1px solid #1a1a1a;
      border-radius: 6px;
      border-bottom-right-radius: 0;
      border-bottom-left-radius: 0;
      box-shadow: 0 2px 4px 0 #00000029;

      .code-header-language {
        margin-right: auto;
        font-size: var(--ai-font-size, 12px);
        color: #999;
      }
    }
  }

  .ai-message-container .code-content-wrapper {
    .hljs-pre {
      padding: 8px 16px;
      margin: 0;
      overflow-x: auto;
      background-color: #282c34;
      border-radius: 6px;
      border-top-left-radius: 0;
      border-top-right-radius: 0;

      code {
        display: block;
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

    .code-line {
      display: inline;
    }
  }
</style>
