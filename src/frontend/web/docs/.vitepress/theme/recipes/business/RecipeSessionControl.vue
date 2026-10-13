<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/session-control.ts"
    kicker="配方 2"
    :source="source"
    title="从工单页新建、改名、切换会话"
    when="适用：按业务对象（工单、告警）组织会话，需要编程式管理会话"
  >
    <DemoStage
      app="服务台"
      crumbs="工单 #8821"
    >
      <div class="demo-card">
        <div class="sc-ticket">
          <span class="sc-ticket__no">#8821</span>
          <span>10.0.0.12 磁盘使用率 95%，影响告警写入</span>
        </div>
        <div class="sc-row">
          <span class="sc-label">会话名称</span>
          <input
            v-model="name"
            aria-label="会话名称"
            class="sc-input"
          >
        </div>
        <div class="demo-actions">
          <bk-button
            theme="primary"
            @click="handleCreate"
          >
            <span class="demo-step-no">1</span>新建工单会话
          </bk-button>
          <bk-button @click="handleRename">
            <span class="demo-step-no">2</span>改名为上面的名称
          </bk-button>
          <bk-button
            :disabled="runtime.state.backendMode === 'real'"
            :title="runtime.state.backendMode === 'real' ? '预置会话仅存在于 Mock 中' : ''"
            @click="handleSwitch"
          >
            <span class="demo-step-no">3</span>切回「上周容量评估」
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
  import { createNamedSession, renameCurrent, switchTo } from './snippets/session-control';
  import source from './snippets/session-control.ts?raw';

  const RECIPE_ID = 'session-control';
  /** Mock 预置的历史会话，见 src/mock-fixtures.ts */
  const SEED_SESSION_CODE = 'demo_capacity_review';

  const runtime = useDemoRuntime();
  const name = ref('工单 #8821 · 磁盘告警排查');
  const feedback = ref<FeedbackState | null>(null);

  const handleCreate = async () => {
    const result = await runtime.run(RECIPE_ID, '①', ai => createNamedSession(ai, '工单 #8821 排查'));
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已新建并切换到工单会话。', goto: 'events', gotoLabel: '查看事件' }));
  };

  const handleRename = async () => {
    const result = await runtime.run(RECIPE_ID, '②', ai => renameCurrent(ai, name.value.trim() || '未命名会话'));
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已改名，右侧小鲸的标题同步更新；updateSessionName 不触发 @rename，业务需自行同步。', goto: 'requests', gotoLabel: '查看 PUT 请求' }));
  };

  const handleSwitch = async () => {
    const result = await runtime.run(RECIPE_ID, '③', ai => switchTo(ai, SEED_SESSION_CODE));
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已切回历史会话。' }));
  };
</script>

<style scoped>
  .sc-ticket {
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 14px;
    font-weight: 600;
  }

  .sc-ticket__no {
    padding: 0 6px;
    font-family: var(--vp-font-family-mono);
    font-size: 12px;
    font-weight: 500;
    color: #3a84ff;
    background: #e1ecff;
    border-radius: 2px;
  }

  .sc-row {
    display: flex;
    gap: 10px;
    align-items: center;
    margin-top: 12px;
  }

  .sc-label {
    font-size: 12px;
    color: #63656e;
  }

  .sc-input {
    flex: 1;
    max-width: 320px;
    height: 30px;
    padding: 0 10px;
    font-size: 13px;
    color: #313238;
    border: 1px solid #c4c6cc;
    border-radius: 2px;
    outline: none;
  }

  .sc-input:focus {
    border-color: #3a84ff;
  }
</style>
