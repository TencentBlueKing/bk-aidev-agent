<template>
  <div
    class="markdown-content"
    v-html="parsedContent"
  ></div>
</template>

<script setup lang="ts">
  import { ref, onMounted } from 'vue';

  import hljs from 'highlight.js';
  import { Marked } from 'marked';
  import { markedHighlight } from 'marked-highlight';

  import 'highlight.js/lib/languages/javascript';
  import 'highlight.js/lib/languages/scss';
  import 'highlight.js/lib/languages/typescript';
  // 导入需要的语言支持
  import 'highlight.js/lib/languages/xml';

  import 'highlight.js/styles/atom-one-dark.css';

  // 注册 vue 语言
  hljs.registerAliases('vue', { languageName: 'xml' });

  // 配置 marked
  const marked = new Marked(
    markedHighlight({
      langPrefix: 'hljs language-',
      emptyLangClass: 'hljs',
      highlight(code, lang) {
        const language = hljs.getLanguage(lang) ? lang : 'plaintext';
        return hljs.highlight(code, { language }).value;
      },
    }),
  );

  const props = defineProps<{
    content: string;
  }>();

  const parsedContent = ref('');

  onMounted(async () => {
    parsedContent.value = await marked.parse(props.content);
  });
</script>

<style lang="scss">
  .markdown-content {
    h1 {
      margin-bottom: 32px;
      font-size: 32px;
      font-weight: 600;
      color: #1a1a1a;
    }

    h2 {
      padding-bottom: 8px;
      margin: 32px 0 16px;
      font-size: 24px;
      font-weight: 600;
      color: #2a2a2a;
      border-bottom: 1px solid #eee;
    }

    h3 {
      margin: 24px 0 16px;
      font-size: 20px;
      font-weight: 600;
      color: #333;
    }

    p {
      margin: 16px 0;
      line-height: 1.8;
      color: #444;
    }

    ul,
    ol {
      padding-left: 24px;
      margin: 16px 0;

      li {
        margin: 8px 0;
        line-height: 1.6;
        color: #444;
      }
    }

    code {
      padding: 2px 6px;
      font-family: 'Fira Code', Consolas, monospace;
      font-size: 13px;
      background: #f5f7fa;
      border-radius: 4px;
    }

    pre {
      padding: 16px;
      margin: 16px 0;
      overflow-x: auto;
      background: #282c34;
      border-radius: 8px;

      code {
        padding: 0;
        color: #abb2bf;
        background: transparent;
      }
    }

    blockquote {
      padding: 12px 24px;
      margin: 16px 0;
      color: #666;
      background: #f8f9fa;
      border-left: 4px solid #1482ff;
      border-radius: 4px;

      p {
        margin: 8px 0;
      }
    }

    table {
      width: 100%;
      margin: 16px 0;
      border-collapse: collapse;

      th,
      td {
        padding: 12px;
        text-align: left;
        border: 1px solid #eee;
      }

      th {
        font-weight: 600;
        background: #f5f7fa;
      }

      tr:nth-child(even) {
        background: #f8f9fa;
      }
    }

    hr {
      margin: 24px 0;
      border: none;
      border-top: 1px solid #eee;
    }

    img {
      max-width: 100%;
      border-radius: 4px;
    }

    a {
      color: #1482ff;
      text-decoration: none;
      transition: color 0.2s;

      &:hover {
        color: #0066e5;
      }
    }
  }
</style>
