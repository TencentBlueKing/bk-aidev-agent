<template>
  <DemoRecipe
    :id="RECIPE_ID"
    :changed-lines="changedLines"
    file="由当前配置生成"
    :floating-config="toConfig(mode)"
    kicker="配方 2"
    lang="vue"
    :source="template"
    title="同一个面板的三种渲染模式"
    when="适用：同一套小鲸既要给用户对话，又要在测试页或分享页里复用"
  >
    <DemoStage
      app="AIDev 平台"
      crumbs="智能体调试"
    >
      <div class="demo-card">
        <div
          class="rm-modes"
          role="radiogroup"
          aria-label="renderMode"
        >
          <button
            v-for="m in MODES"
            :key="m.value"
            type="button"
            role="radio"
            class="rm-mode"
            :aria-checked="mode === m.value"
            :class="{ 'is-on': mode === m.value }"
            @click="select(m.value)"
          >
            <span class="rm-mode__title">{{ m.label }}<code>{{ m.value }}</code></span>
            <span class="rm-mode__desc">{{ m.desc }}</span>
          </button>
        </div>
        <div class="demo-actions">
          <bk-button
            theme="primary"
            @click="handleOpen"
          >
            按此模式打开
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
  import { computed, ref, watch } from 'vue';

  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState, FloatingConfig } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { diffLines } from '../../demo-kit/code-steps';
  import { buildRenderModeTemplate, type DemoRenderMode } from './header-template';

  const RECIPE_ID = 'render-mode';
  const MODES: { value: DemoRenderMode; label: string; desc: string }[] = [
    { value: 'chat', label: '对话', desc: '默认模式，完整的对话与菜单' },
    { value: 'test', label: '测试', desc: '用于调试页：头部菜单不显示「分享」' },
    { value: 'share', label: '分享', desc: '用于分享页：隐藏输入区，只读查看对话' },
  ];

  const runtime = useDemoRuntime();
  const mode = ref<DemoRenderMode>('chat');
  const template = computed(() => buildRenderModeTemplate(mode.value));
  const changedLines = ref<number[]>([]);
  const feedback = ref<FeedbackState | null>(null);

  const toConfig = (m: DemoRenderMode): FloatingConfig => ({
    key: `render:${m}`,
    props: { renderMode: m, dropdownMenuConfig: { showRename: true, showAutoGenerate: true, showShare: true } },
  });

  watch(template, (next, prev) => {
    changedLines.value = diffLines(prev, next);
  });

  const select = (next: DemoRenderMode) => {
    mode.value = next;
    runtime.updateFloatingConfig(RECIPE_ID, toConfig(next));
  };

  const handleOpen = async () => {
    runtime.updateFloatingConfig(RECIPE_ID, toConfig(mode.value));
    const result = await runtime.run(RECIPE_ID, 'open', ai => ai.show());
    const desc = MODES.find(m => m.value === mode.value)?.desc ?? '';
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: `已按「${mode.value}」打开：${desc}。` }));
  };
</script>

<style scoped>
  .rm-modes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }

  .rm-mode {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 10px 12px;
    text-align: left;
    cursor: pointer;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .rm-mode.is-on {
    border-color: #3a84ff;
    box-shadow: inset 0 0 0 1px #3a84ff;
  }

  .rm-mode__title {
    display: flex;
    gap: 6px;
    align-items: center;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .rm-mode__title code {
    font-size: 11px;
    font-weight: 400;
    color: #979ba5;
  }

  .rm-mode__desc {
    font-size: 12px;
    line-height: 1.5;
    color: #979ba5;
  }

  @media (max-width: 720px) {
    .rm-modes {
      grid-template-columns: 1fr;
    }
  }
</style>
