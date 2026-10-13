<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/page-context.ts"
    instance="embedded"
    kicker="配方 2"
    :source="source"
    title="把「正在查看的对象」交给小鲸"
    when="适用：用户在业务页选中了主机、告警、工单，希望提问时自动带上它"
  >
    <DemoStage
      app="蓝鲸配置平台"
      crumbs="主机列表"
    >
      <DemoEmbedFrame :aside-width="210">
        <template #aside>
          <div class="pc-hosts">
            <div class="pc-hosts__title">主机（点击切换当前查看）</div>
            <button
              v-for="host in HOSTS"
              :key="host.host"
              type="button"
              class="pc-host"
              :class="{ 'is-on': target.host === host.host }"
              @click="select(host)"
            >
              <span class="pc-host__ip">{{ host.host }}</span>
              <span class="pc-host__biz">业务 {{ host.bizId }} · {{ host.name }}</span>
            </button>
          </div>
        </template>
        <template #toolbar>
          <span class="pc-current">当前查看：<b>biz_id={{ target.bizId }} · {{ target.host }}</b></span>
          <bk-button
            size="small"
            theme="primary"
            @click="handleAsk"
          >
            <span class="demo-step-no">2</span>就这台主机提问
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
  import { askAboutTarget, createContextRequestOptions, type ViewingTarget } from './snippets/page-context';
  import source from './snippets/page-context.ts?raw';

  const RECIPE_ID = 'page-context';
  const HOSTS: (ViewingTarget & { name: string })[] = [
    { bizId: 2, host: '10.0.0.12', name: '蓝鲸监控' },
    { bizId: 2, host: '10.0.0.13', name: '蓝鲸监控' },
    { bizId: 5, host: '10.0.1.21', name: '作业平台' },
  ];

  const runtime = useDemoRuntime();
  const target = ref<ViewingTarget>({ bizId: HOSTS[0].bizId, host: HOSTS[0].host });
  const embedded = useEmbeddedInstance(RECIPE_ID, { requestOptions: createContextRequestOptions(target) });
  const feedback = ref<FeedbackState | null>(null);

  const select = (host: ViewingTarget) => {
    target.value = { bizId: host.bizId, host: host.host };
    runtime.selectStep(RECIPE_ID, '①');
    feedback.value = { kind: 'info', text: `已切到 ${host.host}，下一条消息会带上它。` };
  };

  const handleAsk = async () => {
    const result = await runtime.run<void, ChatBotExpose>(RECIPE_ID, '②', bot => askAboutTarget(bot, '这台主机最近有什么异常？'));
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: '已发送，Mock 回复的第一句会回显收到的上下文。',
      goto: 'requests',
      gotoLabel: '看 session_content/ 的 Body',
    }));
  };
</script>

<style scoped>
  .pc-hosts {
    display: flex;
    flex-direction: column;
    gap: 4px;
    height: 100%;
    padding: 10px;
    background: #fafbfd;
    border-right: 1px solid #f0f1f5;
  }

  .pc-hosts__title {
    margin-bottom: 4px;
    font-size: 12px;
    color: #979ba5;
  }

  .pc-host {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 8px 10px;
    text-align: left;
    cursor: pointer;
    background: #fff;
    border: 1px solid #f0f1f5;
    border-radius: 2px;
  }

  .pc-host.is-on {
    border-color: #3a84ff;
    box-shadow: inset 0 0 0 1px #3a84ff;
  }

  .pc-host__ip {
    font-family: var(--vp-font-family-mono);
    font-size: 12px;
    color: #313238;
  }

  .pc-host__biz {
    font-size: 11px;
    color: #979ba5;
  }

  .pc-current {
    font-size: 12px;
    color: #63656e;
  }

  .pc-current b {
    font-family: var(--vp-font-family-mono);
    font-weight: 500;
    color: #313238;
  }
</style>
