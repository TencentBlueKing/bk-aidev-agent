/**
 * Playground 展示用示例代码。
 * 必须与 CustomMessageRenderer 同目录：Vite/rolldown 会扫描模板字符串里的 import，
 * 相对路径需相对本文件可解析，否则依赖预构建会失败。
 */
export const codeExample = `<template>
  <ChatBot :url="apiUrl">
    <!-- 使用 #message 插槽自定义消息渲染 -->
    <template #message="{ message }">
      <CustomMessageRenderer :message="message" />
    </template>
  </ChatBot>
</template>

<script setup>
import { ChatBot } from '@blueking/ai-blueking';
import CustomMessageRenderer from './CustomMessageRenderer.vue';
<\/script>

<!-- CustomMessageRenderer.vue 核心逻辑 -->
<script setup>
import { computed } from 'vue';
import { MessageRender } from '@blueking/chat-x';
import { parseCustomBlocks } from '@blueking/ai-blueking';
import ChartWidget from './ChartWidget.vue';
import IframeWidget from './IframeWidget.vue';
import FormWidget from './FormWidget.vue';

const props = defineProps({ message: Object });
const blocks = computed(() => parseCustomBlocks(props.message.content || ''));
<\/script>

<template>
  <template v-for="(block, i) in blocks" :key="i">
    <!-- 普通文本用 MessageRender 渲染 -->
    <MessageRender
      v-if="block.type === 'text'"
      :message="{ ...message, content: block.content }"
    />
    <!-- 自定义组件分发渲染 -->
    <ChartWidget v-else-if="block.data.type === 'chart'" :data="block.data" />
    <IframeWidget v-else-if="block.data.type === 'iframe'" :data="block.data" />
    <FormWidget v-else-if="block.data.type === 'form'" :data="block.data" />
  </template>
</template>`;
