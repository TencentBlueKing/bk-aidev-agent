<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/open-and-ready.ts"
    kicker="配方 1"
    :source="source"
    title="从业务页工具栏打开小鲸"
    when="适用：在业务页提供「问小鲸」入口，打开后读取会话、切换历史会话或使用临时会话"
  >
    <DemoStage
      app="蓝鲸配置平台"
      crumbs="资源 / 主机列表"
    >
      <div class="demo-card">
        <div class="r1-toolbar">
          <div class="r1-title">
            主机列表<span class="r1-count">共 3 台</span>
          </div>
        </div>
        <div class="r1-hosts">
          <div class="r1-row is-head">
            <span>内网 IP</span><span>业务</span><span>状态</span>
          </div>
          <div
            v-for="host in HOSTS"
            :key="host.ip"
            class="r1-row"
          >
            <span class="r1-ip">{{ host.ip }}</span><span>{{ host.biz }}</span>
            <span><i
              class="r1-dot"
              :class="host.ok ? 'is-ok' : 'is-bad'"
            />{{ host.ok ? '正常' : '告警中' }}</span>
          </div>
        </div>
        <div class="demo-actions">
          <bk-button
            theme="primary"
            @click="handleOpen"
          >
            <span class="demo-step-no">1</span>问小鲸
          </bk-button>
          <bk-button
            :disabled="state.backendMode === 'real'"
            :title="state.backendMode === 'real' ? '预置会话仅存在于 Mock 中' : ''"
            @click="handleOpenSession"
          >
            <span class="demo-step-no">2</span>打开「上周容量评估」会话
          </bk-button>
          <bk-button @click="handleTemporary">
            <span class="demo-step-no">3</span>临时会话打开
          </bk-button>
          <bk-button @click="handleClose">
            <span class="demo-step-no">4</span>关闭
          </bk-button>
          <DemoFeedback
            :feedback="feedback"
            :recipe-id="RECIPE_ID"
          />
        </div>
      </div>
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { closePanel, openPanel, openSession, openTemporary } from './snippets/open-and-ready';
  import source from './snippets/open-and-ready.ts?raw';

  const RECIPE_ID = 'open-ready';
  /** Mock 预置的历史会话，见 src/mock-fixtures.ts */
  const SEED_SESSION_CODE = 'demo_capacity_review';
  const HOSTS = [
    { ip: '10.0.0.11', biz: '蓝鲸监控', ok: true },
    { ip: '10.0.0.12', biz: '蓝鲸监控', ok: false },
    { ip: '10.0.0.13', biz: '作业平台', ok: true },
  ];

  const runtime = useDemoRuntime();
  const { state } = runtime;
  const feedback = ref<FeedbackState | null>(null);

  const handleOpen = async () => {
    const result = await runtime.run(RECIPE_ID, '①', ai => openPanel(ai));
    feedback.value = resultFeedback(result, name => ({
      kind: 'ok',
      text: `已就绪，当前会话「${name || '未命名'}」。`,
      goto: 'events',
      gotoLabel: '看 show() 何时 resolve',
    }));
  };

  const handleOpenSession = async () => {
    const result = await runtime.run(RECIPE_ID, '②', ai => openSession(ai, SEED_SESSION_CODE));
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: '已切换到历史会话，右侧可以看到上周的对话。',
      goto: 'requests',
      gotoLabel: '查看加载了哪些接口',
    }));
  };

  const handleTemporary = async () => {
    const result = await runtime.run(RECIPE_ID, '③', ai => openTemporary(ai));
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: '已以临时会话打开，不会出现在历史列表中。',
      goto: 'requests',
      gotoLabel: '查看 is_temporary',
    }));
  };

  const handleClose = async () => {
    const result = await runtime.run(RECIPE_ID, '④', ai => closePanel(ai));
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已关闭，悬浮球仍可重新打开。' }));
  };
</script>

<style scoped>
  .r1-toolbar {
    display: flex;
    align-items: center;
    margin-bottom: 10px;
  }

  .r1-title {
    font-size: 14px;
    font-weight: 600;
  }

  .r1-count {
    margin-left: 8px;
    font-size: 12px;
    font-weight: 400;
    color: #979ba5;
  }

  .r1-hosts {
    border: 1px solid #f0f1f5;
  }

  .r1-row {
    display: grid;
    grid-template-columns: 1.2fr 1fr 1fr;
    padding: 6px 12px;
    font-size: 12px;
    border-top: 1px solid #f0f1f5;
  }

  .r1-row.is-head {
    color: #63656e;
    background: #fafbfd;
    border-top: 0;
  }

  .r1-ip {
    font-family: var(--vp-font-family-mono);
  }

  .r1-dot {
    display: inline-block;
    width: 6px;
    height: 6px;
    margin-right: 6px;
    vertical-align: 1px;
    border-radius: 50%;
  }

  .r1-dot.is-ok {
    background: #2dcb56;
  }

  .r1-dot.is-bad {
    background: #ea3636;
  }
</style>
