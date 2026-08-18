<template>
  <BkButton
    outline
    size="small"
    theme="primary"
    @click="visible = true"
  >
    {{ buttonText }}
  </BkButton>

  <BkDialog
    v-model:is-show="visible"
    header-align="left"
    :title="title"
    width="840"
  >
    <template #footer>
      <BkButton
        theme="primary"
        @click="visible = false"
      >
        关闭
      </BkButton>
    </template>
    <div class="source-guide">
      <div
        class="source-guide-tabs"
        role="tablist"
      >
        <button
          v-for="section in sections"
          :key="section.id"
          class="source-guide-tab"
          :class="{ 'is-active': activeId === section.id }"
          type="button"
          @click="activeId = section.id"
        >
          {{ section.label }}
        </button>
      </div>

      <div
        v-if="activeSection"
        class="source-guide-body"
      >
        <ul
          v-if="activeSection.notes?.length"
          class="source-guide-notes"
        >
          <li
            v-for="(note, index) in activeSection.notes"
            :key="index"
          >
            {{ note }}
          </li>
        </ul>

        <article
          v-for="block in activeSection.blocks"
          :key="block.title"
          class="source-guide-block"
        >
          <header class="source-guide-block-header">
            <div>
              <h4>{{ block.title }}</h4>
              <p
                v-if="block.desc"
                class="source-guide-block-desc"
              >
                {{ block.desc }}
              </p>
            </div>
            <div class="source-guide-block-actions">
              <span
                v-if="block.fileHint"
                class="source-guide-file"
              >
                {{ block.fileHint }}
              </span>
              <BkButton
                v-if="block.code"
                size="small"
                @click="copyCode(block.code)"
              >
                {{ copiedKey === block.title ? '已复制' : '复制' }}
              </BkButton>
            </div>
          </header>
          <pre
            v-if="block.code"
            class="source-guide-code"
          ><code>{{ block.code }}</code></pre>
        </article>
      </div>
    </div>
  </BkDialog>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';

  import { Button as BkButton, Dialog as BkDialog, Message } from 'bkui-vue';
  import 'bkui-vue/lib/button/button.css';
  import 'bkui-vue/lib/dialog/dialog.css';
  import 'bkui-vue/lib/message/message.css';

  import type { SourceGuideSection } from './source-guide';

  const props = withDefaults(
    defineProps<{
      buttonText?: string;
      sections: SourceGuideSection[];
      title?: string;
    }>(),
    {
      buttonText: '查看源码',
      title: '接入说明与源码',
    },
  );

  const visible = ref(false);
  const activeId = ref(props.sections[0]?.id ?? '');
  const copiedKey = ref('');

  const activeSection = computed(
    () => props.sections.find(section => section.id === activeId.value) ?? props.sections[0],
  );

  const copyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      copiedKey.value = activeSection.value?.blocks?.find(block => block.code === code)?.title ?? '';
      Message({ theme: 'success', message: '已复制到剪贴板' });
      window.setTimeout(() => {
        copiedKey.value = '';
      }, 1600);
    } catch {
      Message({ theme: 'error', message: '复制失败，请手动选择代码' });
    }
  };
</script>

<style scoped>
  .source-guide-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 16px;
  }

  .source-guide-tab {
    height: 28px;
    padding: 0 12px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #f5f7fa;
    border: 1px solid transparent;
    border-radius: 14px;
  }

  .source-guide-tab.is-active {
    font-weight: 600;
    color: #3a84ff;
    background: #e1ecff;
  }

  .source-guide-body {
    max-height: 62vh;
    overflow: auto;
  }

  .source-guide-notes {
    padding-left: 18px;
    margin: 0;
    font-size: 13px;
    line-height: 22px;
    color: #4d4f56;
  }

  .source-guide-notes li + li {
    margin-top: 8px;
  }

  .source-guide-notes + .source-guide-block {
    margin-top: 16px;
  }

  .source-guide-block + .source-guide-block {
    margin-top: 16px;
  }

  .source-guide-block-header {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .source-guide-block-header h4 {
    margin: 0 0 4px;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .source-guide-block-desc {
    margin: 0;
    font-size: 12px;
    line-height: 18px;
    color: #979ba5;
  }

  .source-guide-block-actions {
    display: flex;
    flex-shrink: 0;
    gap: 8px;
    align-items: center;
  }

  .source-guide-file {
    font-size: 11px;
    color: #979ba5;
  }

  .source-guide-code {
    display: block;
    padding: 12px 14px;
    margin: 0;
    overflow: auto;
    font-size: 12px;
    line-height: 18px;
    color: #313238;
    white-space: pre;
    background: #f5f7fa;
    border-radius: 4px;
  }
</style>
