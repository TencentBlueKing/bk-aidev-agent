<template>
  <div class="preview-section">
    <h3>预览区域</h3>
    <div class="preview-props">
      <h4>当前组件配置</h4>
      <div
        class="markdown-content"
        v-html="codePreview"
      ></div>
    </div>
    <slot></slot>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  import hljs from 'highlight.js';
  import { Marked } from 'marked';
  import { markedHighlight } from 'marked-highlight';

  import 'highlight.js/lib/languages/javascript';
  import 'highlight.js/lib/languages/typescript';
  import 'highlight.js/lib/languages/xml';

  import 'highlight.js/styles/atom-one-dark.css';

  const props = defineProps<{
    config: Record<string, any>;
  }>();

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

  // 生成代码预览
  const codePreview = computed(() => {
    const code = `\`\`\`json
${JSON.stringify(props.config, null, 2)}
\`\`\``;
    return marked.parse(code);
  });
</script>

<style lang="scss" scoped>
  .preview-section {
    margin-bottom: 32px;

    h3 {
      margin-bottom: 16px;
      font-size: 18px;
      color: #333;
    }

    .preview-props {
      padding: 20px;
      margin-bottom: 20px;
      background: #f8f9fa;
      border: 1px solid #e9ecef;
      border-radius: 8px;

      h4 {
        margin-bottom: 16px;
        font-size: 16px;
        color: #333;
      }

      :deep(.markdown-content) {
        height: 300px;
        overflow-y: auto;
        border-radius: 8px;

        pre {
          padding: 16px;
          margin: 0;
          overflow-x: auto;
          background: #282c34;
          border-radius: 8px;

          code {
            padding: 0;
            font-family: 'Fira Code', Consolas, Monaco, 'Andale Mono', monospace;
            font-size: 14px;
            line-height: 1.5;
            color: #abb2bf;
            word-break: break-all;
            white-space: pre-wrap;
            background: transparent;

            .hljs {
              &-keyword {
                color: #c678dd;
              }

              &-string {
                color: #98c379;
              }

              &-comment {
                color: #5c6370;
              }

              &-number {
                color: #d19a66;
              }

              &-literal {
                color: #56b6c2;
              }

              &-function {
                color: #61afef;
              }

              &-params {
                color: #abb2bf;
              }

              &-class {
                color: #e5c07b;
              }

              &-tag {
                color: #e06c75;
              }

              &-attr {
                color: #d19a66;
              }
            }
          }
        }
      }
    }
  }
</style>
