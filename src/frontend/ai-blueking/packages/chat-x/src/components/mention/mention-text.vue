<template>
  <div class="ai-mention-text">
    <template
      v-for="(line, lineIndex) in doc"
      :key="lineIndex"
    >
      <br v-if="lineIndex > 0" />
      <template
        v-for="(node, nodeIndex) in line"
        :key="nodeIndex"
      >
        <span v-if="node.type === 'text'">{{ node.text }}</span>
        <MentionTag
          v-else
          :description="node.data.description"
          :icon="node.data.icon"
          :label="node.data.label"
          :type="node.data.type"
          :value="node.data.value"
        />
      </template>
    </template>
  </div>
</template>
<script setup lang="ts">
  import MentionTag from './mention-tag.vue';

  import type { TagSchema } from '../../types/input';

  defineProps<{
    /** 发送时随消息一起保存的编辑器文档，用于把已选资源原样回显 */
    doc: TagSchema;
  }>();
</script>
<style lang="scss">
  .ai-mention-text {
    width: fit-content;

    // 行间换行由 <br> 承担，这里保证行内连续空格与纯文本分支表现一致
    word-break: break-all;
    white-space: pre-wrap;
  }
</style>
