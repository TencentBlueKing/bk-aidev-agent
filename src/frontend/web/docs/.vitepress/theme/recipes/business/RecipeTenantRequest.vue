<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/tenant-request-options.ts"
    instance="embedded"
    kicker="配方 1"
    :source="source"
    title="按租户切换请求头与参数"
    when="适用：多租户 / 多环境平台，请求需要带上当前租户与最新的 token"
  >
    <DemoStage
      app="蓝鲸 PaaS"
      crumbs="多租户控制台"
    >
      <DemoEmbedFrame :nav="['应用列表', '租户管理', '访问控制']">
        <template #toolbar>
          <span class="rt-label">租户</span>
          <div
            class="rt-seg"
            role="radiogroup"
            aria-label="租户"
          >
            <button
              v-for="t in TENANTS"
              :key="t"
              type="button"
              role="radio"
              :aria-checked="tenant === t"
              :class="{ 'is-on': tenant === t }"
              @click="switchTenant(t)"
            >
              {{ t }}
            </button>
          </div>
          <bk-button
            size="small"
            @click="rotateToken"
          >
            轮换 token
          </bk-button>
          <code class="rt-token">{{ token }}</code>
          <span class="rt-sep" />
          <bk-button
            size="small"
            @click="handleReload"
          >
            <span class="demo-step-no">2</span>刷新会话列表
          </bk-button>
          <bk-button
            size="small"
            theme="primary"
            @click="handleAsk"
          >
            <span class="demo-step-no">3</span>发送消息
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
        />
      </DemoEmbedFrame>
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { ref } from 'vue';
  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

  import DemoEmbedFrame from '../../demo-kit/DemoEmbedFrame.vue';
  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { useEmbeddedInstance } from '../../demo-kit/use-embedded-instance';
  import { ask, createTenantRequestOptions, reloadSessions } from './snippets/tenant-request-options';
  import source from './snippets/tenant-request-options.ts?raw';

  const RECIPE_ID = 'tenant-request';
  const TENANTS = ['tenant-001', 'tenant-002'];

  const runtime = useDemoRuntime();
  const tenant = ref(TENANTS[0]);
  const token = ref('token-alpha');
  const embedded = useEmbeddedInstance(RECIPE_ID, { requestOptions: createTenantRequestOptions(tenant, token) });
  const feedback = ref<FeedbackState | null>(null);

  const changed = (text: string) => {
    runtime.selectStep(RECIPE_ID, '①');
    feedback.value = { kind: 'info', text, goto: 'requests', gotoLabel: '下一次请求后对比' };
  };

  const switchTenant = (next: string) => {
    tenant.value = next;
    changed(`已切到 ${next}，下一次请求起生效。`);
  };

  const rotateToken = () => {
    token.value = token.value === 'token-alpha' ? 'token-beta' : 'token-alpha';
    changed(`token 已换成 ${token.value}。`);
  };

  const handleReload = async () => {
    const result = await runtime.run<number, ChatBotExpose>(RECIPE_ID, '②', bot => reloadSessions(bot));
    feedback.value = resultFeedback(result, count => ({
      kind: 'ok',
      text: `已刷新，共 ${count ?? 0} 个会话。GET 请求的 tenant_id 在 Query 里。`,
      goto: 'requests',
      gotoLabel: '查看请求',
    }));
  };

  const handleAsk = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '③', bot => ask(bot, `${tenant.value} 下有哪些应用最近部署失败？`));
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: '已发送。POST 请求的 tenant_id 在 Body 里。',
      goto: 'requests',
      gotoLabel: '查看请求',
    }));
  };
</script>

<style scoped>
  .rt-label {
    font-size: 12px;
    color: #63656e;
  }

  .rt-seg {
    display: inline-flex;
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .rt-seg button {
    padding: 2px 10px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #fff;
    border: 0;
    border-right: 1px solid #dcdee5;
  }

  .rt-seg button:last-child {
    border-right: 0;
  }

  .rt-seg button.is-on {
    color: #fff;
    background: #3a84ff;
  }

  .rt-token {
    padding: 0 6px;
    font-size: 11px;
    color: #63656e;
    background: #f0f1f5;
    border-radius: 2px;
  }

  .rt-sep {
    width: 1px;
    height: 16px;
    background: #dcdee5;
  }
</style>
