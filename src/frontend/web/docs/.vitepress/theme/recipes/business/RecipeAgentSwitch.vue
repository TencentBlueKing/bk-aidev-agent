<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/agent-switch.ts"
    instance="embedded"
    kicker="配方 2"
    :source="source"
    title="在两个智能体之间切换 url"
    when="适用：同一页面按场景切换不同的 AIDev 智能体，或切换测试 / 正式环境"
  >
    <DemoStage
      app="AI 工作台"
      crumbs="对话"
    >
      <DemoEmbedFrame :nav="['对话', '知识库', '设置']">
        <template #toolbar>
          <span class="as-title">{{ agentName || '加载中…' }}</span>
          <div
            class="as-seg"
            role="radiogroup"
            aria-label="智能体"
          >
            <button
              v-for="p in PROFILES"
              :key="p.id"
              type="button"
              role="radio"
              :aria-checked="profile === p.id"
              :class="{ 'is-on': profile === p.id }"
              :disabled="runtime.state.backendMode === 'real'"
              :title="runtime.state.backendMode === 'real' ? '真实智能体模式下没有第二个智能体可切换' : p.path"
              @click="handleSwitch(p.id)"
            >
              {{ p.label }}
            </button>
          </div>
          <code class="as-url">{{ agentUrl }}</code>
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
          @agent-info-loaded="onAgentInfoLoaded"
        />
      </DemoEmbedFrame>
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { computed, nextTick, ref } from 'vue';
  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

  import DemoEmbedFrame from '../../demo-kit/DemoEmbedFrame.vue';
  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { useEmbeddedInstance } from '../../demo-kit/use-embedded-instance';
  import { waitAgentName } from './snippets/agent-switch';
  import source from './snippets/agent-switch.ts?raw';

  type ProfileId = 'default' | 'data';
  type ChatHelper = NonNullable<ReturnType<ChatBotExpose['getChatHelper']>>;

  const RECIPE_ID = 'agent-switch';
  /** Mock 的两套智能体：默认档案与 ~data/ 前缀档案，见 src/mock-fixtures.ts */
  const PROFILES: { id: ProfileId; label: string; path: string }[] = [
    { id: 'default', label: '运维助手', path: '' },
    { id: 'data', label: '数据助手', path: '~data/' },
  ];

  const runtime = useDemoRuntime();
  const profile = ref<ProfileId>('default');
  const agentName = ref('');
  const agentUrl = computed(
    () => `${runtime.apiUrl.value}${runtime.state.backendMode === 'mock' ? (PROFILES.find(p => p.id === profile.value)?.path ?? '') : ''}`,
  );
  const embedded = useEmbeddedInstance(RECIPE_ID, { url: agentUrl });
  const feedback = ref<FeedbackState | null>(null);

  const onAgentInfoLoaded = (helper: ChatHelper) => {
    agentName.value = helper.agent.info.value?.agentName ?? '';
  };

  const handleSwitch = async (next: ProfileId) => {
    if (next === profile.value) return;
    profile.value = next;
    agentName.value = '';
    await nextTick();
    const result = await runtime.run<string | undefined, ChatBotExpose>(RECIPE_ID, '①', bot => waitAgentName(bot));
    if (result.ok && result.value) agentName.value = result.value;
    feedback.value = resultFeedback(result, name => ({
      kind: 'ok',
      text: `已切换到「${name ?? '未知智能体'}」，实例已重建。`,
      goto: 'requests',
      gotoLabel: '看新的请求前缀',
    }));
  };
</script>

<style scoped>
  .as-title {
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .as-seg {
    display: inline-flex;
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .as-seg button {
    padding: 2px 12px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #fff;
    border: 0;
    border-right: 1px solid #dcdee5;
  }

  .as-seg button:last-child {
    border-right: 0;
  }

  .as-seg button.is-on {
    color: #fff;
    background: #3a84ff;
  }

  .as-seg button:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .as-url {
    padding: 0 6px;
    font-size: 11px;
    color: #63656e;
    background: #f0f1f5;
    border-radius: 2px;
  }
</style>
