<template>
  <!-- 用户消息不解析自定义块，交给默认的 MessageRender -->
  <MessageRender
    v-if="message.role !== MessageRole.Assistant"
    :message="message"
  />
  <div
    v-else
    class="cmr"
  >
    <!-- ② 文本块交给默认的 MessageRender（保留 Markdown、代码高亮），自定义块按 data.type 分发到业务组件 -->
    <template
      v-for="(block, index) in blocks"
      :key="index"
    >
      <MessageRender
        v-if="block.type === 'text'"
        :message="{ ...message, content: block.content }"
      />
      <ChartWidget
        v-else-if="block.data.type === 'chart'"
        :data="block.data"
      />
      <FormWidget
        v-else-if="block.data.type === 'form'"
        :data="block.data"
        @submit="payload => emit('form-submit', payload)"
      />
      <IframeWidget
        v-else-if="block.data.type === 'iframe'"
        :data="block.data"
      />
      <div
        v-else
        class="cmr__unknown"
      >
        未知组件类型：{{ String(block.data.type) }}
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';
  import { MessageRender, MessageRole, type Message } from '@blueking/chat-x';
  import { parseCustomBlocks } from '@blueking/ai-blueking';

  import ChartWidget from './widgets/ChartWidget.vue';
  import FormWidget from './widgets/FormWidget.vue';
  import IframeWidget from './widgets/IframeWidget.vue';
  import type { FormSubmit } from './widgets/types';

  const props = defineProps<{ message: Message }>();

  // ① 把回复拆成「文本块」与「```custom-component 块」：模型按约定输出 JSON 即可
  const blocks = computed(() => parseCustomBlocks(props.message.content ?? ''));

  // ③ 表单的结果交还给页面：页面再决定是否回传给智能体
  const emit = defineEmits<{ 'form-submit': [payload: FormSubmit] }>();
</script>

<style scoped>
  .cmr {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .cmr__unknown {
    padding: 10px 12px;
    font-size: 12px;
    color: #ea3636;
    background: #fff5f5;
    border: 1px solid #fedddd;
    border-radius: 6px;
  }
</style>
