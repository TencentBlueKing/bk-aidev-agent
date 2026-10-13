<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/alert-diagnosis.ts"
    kicker="配方 2"
    :source="source"
    title="从告警卡片一键让小鲸诊断"
    when="适用：页面上已有告警、日志等上下文，希望用户带着它提问"
  >
    <DemoStage
      app="蓝鲸监控"
      crumbs="告警中心 / 告警详情"
    >
      <div class="demo-card">
        <div class="r2-head">
          <bk-tag theme="danger">
            致命
          </bk-tag>
          <span class="r2-title">{{ ALERT.title }}</span>
        </div>
        <div class="r2-meta">告警 #1024 · 主机 {{ ALERT.host }} · 业务 蓝鲸监控 · 已持续 15 分钟</div>
        <pre
          ref="logRef"
          class="r2-log"
        >{{ LOG }}</pre>
        <div class="r2-hint">可以先用鼠标划选几行日志，再点「引用」</div>
        <div class="demo-actions">
          <bk-button @click="handleCite">
            <span class="demo-step-no">1</span>{{ selectedLines ? `引用选中的 ${selectedLines} 行并打开` : '引用日志并打开' }}
          </bk-button>
          <bk-button
            theme="primary"
            @click="handleAsk"
          >
            <span class="demo-step-no">2</span>让小鲸诊断
          </bk-button>
          <bk-button
            :disabled="!floating.generating"
            theme="danger"
            outline
            @click="handleStop"
          >
            <span class="demo-step-no">3</span>停止生成
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
  import { computed, onBeforeUnmount, onMounted, ref } from 'vue';

  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { FLOATING_INSTANCE, useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { askAboutAlert, citeLogAndOpen, stopAnswer, type Alert } from './snippets/alert-diagnosis';
  import source from './snippets/alert-diagnosis.ts?raw';

  const RECIPE_ID = 'alert';
  const ALERT: Alert = { title: 'CPU 使用率 97%', host: '10.0.0.12' };
  const LOG = [
    '[16:31:02] WARN  GC pause 1.8s (G1 Old Generation)',
    '[16:31:09] WARN  GC pause 2.1s (G1 Old Generation)',
    "[16:31:15] ERROR ThreadPool 'alarm-dispatcher' queue full (1000/1000)",
    '[16:31:21] WARN  GC pause 2.6s (G1 Old Generation)',
  ].join('\n');

  const runtime = useDemoRuntime();
  const floating = computed(() => runtime.instanceState(FLOATING_INSTANCE));
  const feedback = ref<FeedbackState | null>(null);
  const logRef = ref<HTMLElement>();
  const selectedText = ref('');
  const selectedLines = ref(0);

  const onSelectionChange = () => {
    const selection = document.getSelection();
    const inLog = !!selection && !selection.isCollapsed && !!logRef.value?.contains(selection.anchorNode);
    selectedText.value = inLog && selection ? selection.toString().trim() : '';
    selectedLines.value = selectedText.value ? selectedText.value.split('\n').length : 0;
  };

  onMounted(() => document.addEventListener('selectionchange', onSelectionChange));
  onBeforeUnmount(() => document.removeEventListener('selectionchange', onSelectionChange));

  const handleCite = async () => {
    const text = selectedText.value || LOG;
    const result = await runtime.run(RECIPE_ID, '①', ai => citeLogAndOpen(ai, text));
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已带上引用打开面板，在右侧补充问题即可。' }));
  };

  const handleAsk = async () => {
    feedback.value = null;
    const result = await runtime.run(RECIPE_ID, '②', ai => askAboutAlert(ai, ALERT));
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: '已发送，回复生成中，可以试试「停止生成」。',
      goto: 'events',
      gotoLabel: '查看事件',
    }));
  };

  const handleStop = async () => {
    const result = await runtime.run(RECIPE_ID, '③', ai => stopAnswer(ai));
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: '已停止生成。',
      goto: 'requests',
      gotoLabel: '查看 stop 请求',
    }));
  };
</script>

<style scoped>
  .r2-head {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .r2-title {
    font-size: 14px;
    font-weight: 600;
  }

  .r2-meta {
    margin: 6px 0 10px;
    font-size: 12px;
    color: #979ba5;
  }

  .r2-log {
    padding: 10px 12px;
    margin: 0;
    font-family: var(--vp-font-family-mono);
    font-size: 12px;
    line-height: 1.7;
    color: #c4c6cc;
    white-space: pre-wrap;
    user-select: text;
    background: #1e2433;
    border-radius: 2px;
  }

  .r2-log::selection {
    color: #fff;
    background: rgb(58 132 255 / 55%);
  }

  .r2-hint {
    margin-top: 6px;
    font-size: 12px;
    color: #979ba5;
  }
</style>
