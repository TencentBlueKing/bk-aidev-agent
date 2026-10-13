<template>
  <div class="cte">
    <section class="cte__editor">
      <header class="cte__file">
        request.ts<span
          v-if="lastLanguage"
          class="cte__badge"
        >已插入 {{ lastLanguage }} 代码</span>
      </header>
      <textarea
        v-model="code"
        aria-label="编辑器"
        class="cte__textarea"
        spellcheck="false"
      />
    </section>
    <section class="cte__chat">
      <ChatBot
        ref="chatBot"
        v-bind="$attrs"
        height="100%"
      >
        <!-- ① 代码块头部插槽：language 为代码语言，token 为该代码块的 markdown-it Token 数组 -->
        <template #codeHeader="{ language, token }">
          <button
            class="cte__insert"
            type="button"
            @click="insert(language, codeOf(token))"
          >
            插入到编辑器
          </button>
        </template>
      </ChatBot>
    </section>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

  // url、requestOptions 等其余属性与事件透传给 ChatBot
  defineOptions({ inheritAttrs: false });

  const emit = defineEmits<{ insert: [language: string] }>();

  const chatBot = ref<ChatBotExpose | null>(null);
  const code = ref('// 在右侧让小鲸写一段代码，点击代码块头部的「插入到编辑器」\n');
  const lastLanguage = ref('');

  /** 代码原文在 type 为 fence（或 code_block）的那个 token 上 */
  const codeOf = (tokens: { type: string; content: string }[]): string =>
    tokens.find(t => t.type === 'fence' || t.type === 'code_block')?.content ?? '';

  // ② 插入到编辑器：真实业务里替换为 Monaco / CodeMirror 的插入 API
  const insert = (language: string, content: string) => {
    code.value = `${code.value.trimEnd()}\n\n${content.trimEnd()}\n`;
    lastLanguage.value = language || 'text';
    emit('insert', lastLanguage.value);
  };

  defineExpose({ chatBot });
</script>

<style scoped>
  .cte {
    display: grid;
    grid-template-rows: minmax(0, 1fr);
    grid-template-columns: 1fr 1fr;
    height: 520px;
    overflow: hidden;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px rgb(0 0 0 / 6%);
  }

  .cte__editor {
    display: flex;
    flex-direction: column;
    min-height: 0;
    background: #1e2433;
  }

  .cte__file {
    display: flex;
    gap: 8px;
    align-items: center;
    height: 34px;
    padding: 0 12px;
    font-family: var(--vp-font-family-mono);
    font-size: 12px;
    color: #c4c6cc;
    border-bottom: 1px solid #2c3446;
  }

  .cte__badge {
    padding: 0 6px;
    font-family: var(--vp-font-family-base);
    font-size: 11px;
    color: #2dcb56;
    background: rgb(45 203 86 / 12%);
    border-radius: 2px;
  }

  .cte__textarea {
    flex: 1;
    padding: 10px 12px;
    font-family: var(--vp-font-family-mono);
    font-size: 12px;
    line-height: 1.7;
    color: #e6e8ee;
    resize: none;
    background: transparent;
    border: 0;
    outline: none;
  }

  .cte__chat {
    min-width: 0;
    min-height: 0;
    overflow: hidden;
    border-left: 1px solid #f0f1f5;
  }

  .cte__insert {
    padding: 0 8px;
    font-size: 12px;
    line-height: 20px;
    color: #3a84ff;
    cursor: pointer;
    background: #fff;
    border: 1px solid #a3c5fd;
    border-radius: 2px;
  }
</style>
