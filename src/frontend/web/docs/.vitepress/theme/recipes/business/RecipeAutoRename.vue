<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/rename-listener.ts"
    instance="embedded"
    kicker="配方 1"
    :source="source"
    title="首条消息后自动命名"
    when="适用：业务自己维护会话列表，需要和小鲸的会话名称保持同步"
  >
    <DemoStage
      app="AI 运维工作台"
      crumbs="会话"
    >
      <DemoEmbedFrame :aside-width="210">
        <template #aside>
          <div class="ar-book">
            <div class="ar-book__title">业务侧会话名表（由 @rename 更新）</div>
            <div
              v-for="(name, code) in book.names.value"
              :key="code"
              class="ar-book__row"
              :class="{ 'is-current': code === currentCode }"
            >
              <span class="ar-book__name">{{ name }}</span>
              <span class="ar-book__code">{{ code }}</span>
            </div>
            <div
              v-if="!Object.keys(book.names.value).length"
              class="ar-book__empty"
            >
              还没有收到 @rename。发送第一条消息试试。
            </div>
          </div>
        </template>
        <template #toolbar>
          <bk-button
            size="small"
            theme="primary"
            @click="handleSend(FIRST)"
          >
            <span class="demo-step-no">2</span>发送第一条消息
          </bk-button>
          <bk-button
            size="small"
            @click="handleSend(SECOND)"
          >
            <span class="demo-step-no">2</span>再发一条
          </bk-button>
          <bk-button
            size="small"
            @click="handleNewSession"
          >
            <span class="demo-step-no">3</span>新开会话
          </bk-button>
          <DemoFeedback
            :feedback="feedback"
            :recipe-id="RECIPE_ID"
          />
        </template>
        <ChatBot
          :key="embedded.key.value"
          :ref="embedded.bindRef"
          height="100%"
          :request-options="embedded.requestOptions"
          :url="embedded.url.value"
          v-bind="embedded.listeners"
          @rename="onRename"
        />
      </DemoEmbedFrame>
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

  import DemoEmbedFrame from '../../demo-kit/DemoEmbedFrame.vue';
  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { useEmbeddedInstance } from '../../demo-kit/use-embedded-instance';
  import { createSessionNameBook, send, startNewSession } from './snippets/rename-listener';
  import source from './snippets/rename-listener.ts?raw';

  const RECIPE_ID = 'auto-rename';
  const FIRST = '帮我看看 10.0.0.12 的磁盘为什么满了';
  const SECOND = '清理哪些目录比较安全？';

  const runtime = useDemoRuntime();
  const embedded = useEmbeddedInstance(RECIPE_ID);
  const book = createSessionNameBook();
  const feedback = ref<FeedbackState | null>(null);

  const currentCode = computed(
    () => runtime.getInstance<ChatBotExpose>(`embedded:${RECIPE_ID}`)?.getChatHelper()?.session.current.value?.sessionCode ?? '',
  );

  const onRename = (newName: string, sessionCode: string) => {
    book.onRename(newName, sessionCode);
    runtime.selectStep(RECIPE_ID, '①');
  };

  const handleSend = async (text: string) => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '②', bot => send(bot, text));
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: text === FIRST ? '已发送，留意左侧名称表与事件页签的 @rename。' : '已发送：同一会话的后续消息不再触发 @rename。',
      goto: 'events',
      gotoLabel: '查看事件',
    }));
  };

  const handleNewSession = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '③', bot => startNewSession(bot));
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已新开会话，再发第一条消息会再次命名。' }));
  };
</script>

<style scoped>
  .ar-book {
    display: flex;
    flex-direction: column;
    gap: 4px;
    height: 100%;
    padding: 10px;
    background: #fafbfd;
    border-right: 1px solid #f0f1f5;
  }

  .ar-book__title {
    margin-bottom: 4px;
    font-size: 12px;
    color: #979ba5;
  }

  .ar-book__row {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 10px;
    background: #fff;
    border: 1px solid #f0f1f5;
    border-radius: 2px;
  }

  .ar-book__row.is-current {
    border-color: #3a84ff;
  }

  .ar-book__name {
    font-size: 13px;
    color: #313238;
  }

  .ar-book__code {
    overflow: hidden;
    font-family: var(--vp-font-family-mono);
    font-size: 11px;
    color: #979ba5;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .ar-book__empty {
    font-size: 12px;
    line-height: 1.6;
    color: #979ba5;
  }
</style>
