<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/panel-layout.ts"
    :floating-config="initialConfig"
    kicker="配方 2"
    :source="source"
    title="让面板避开业务内容"
    when="适用：页面右侧有重要操作区，或需要更宽的面板阅读长回复"
  >
    <DemoStage
      app="作业平台"
      crumbs="作业执行详情"
    >
      <div class="demo-card">
        <div class="pl-layout">
          <div class="pl-main">作业步骤列表</div>
          <div class="pl-side">
            执行结果
            <span>小鲸默认停靠在这一侧</span>
          </div>
        </div>
        <div class="demo-actions">
          <bk-button
            v-for="preset in PRESETS"
            :key="preset.step"
            :theme="current === preset.step ? 'primary' : undefined"
            @click="apply(preset)"
          >
            <span class="demo-step-no">{{ preset.no }}</span>{{ preset.label }}
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
  import type { FeedbackState, FloatingConfig } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { dockLeft, dockRight, widePanel, type PanelBox } from './snippets/panel-layout';
  import source from './snippets/panel-layout.ts?raw';

  interface Preset {
    step: '①' | '②' | '③';
    no: number;
    label: string;
    dock: 'left' | 'right';
    box: () => PanelBox;
    done: string;
  }

  const RECIPE_ID = 'panel-layout';

  /** 文档站左侧导航的右边缘；窄屏无侧栏时为 0 */
  const sidebarRight = (): number => Math.round(document.querySelector('.VPSidebar')?.getBoundingClientRect().right ?? 0);

  const PRESETS: Preset[] = [
    { step: '①', no: 1, label: '贴在右侧', dock: 'right', box: () => dockRight(), done: '已按右侧布局重新挂载。' },
    {
      step: '②',
      no: 2,
      label: '贴在左侧导航之后',
      dock: 'left',
      box: () => dockLeft(sidebarRight()),
      done: '面板已贴在左侧导航之后，正文改为让出左侧空间。',
    },
    { step: '③', no: 3, label: '宽面板 640', dock: 'right', box: widePanel, done: '已按 640 宽重新挂载，正文同步让出更宽的空间。' },
  ];

  const runtime = useDemoRuntime();
  const feedback = ref<FeedbackState | null>(null);
  const current = ref<Preset['step'] | null>(null);

  const toConfig = (preset: Preset, panel: PanelBox): FloatingConfig => ({
    props: { ...panel },
    key: `layout:${preset.step}:${panel.defaultLeft}:${panel.defaultWidth}`,
  });

  /** 首次渲染时无需 DOM：给一个占位配置，点击时按当前视口重新计算 */
  const initialConfig: FloatingConfig = { props: {}, key: 'layout:initial' };

  const apply = async (preset: Preset) => {
    const panel = preset.box();
    runtime.updateFloatingConfig(RECIPE_ID, toConfig(preset, panel));
    const result = await runtime.run(RECIPE_ID, preset.step, ai => ai.show());
    if (result.ok) {
      current.value = preset.step;
      runtime.setFloatingLayout({ dock: preset.dock, width: panel.defaultWidth, left: panel.defaultLeft });
    }
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: preset.done }));
  };
</script>

<style scoped>
  .pl-layout {
    display: grid;
    grid-template-columns: 1fr 200px;
    gap: 12px;
    height: 110px;
  }

  .pl-main,
  .pl-side {
    display: flex;
    flex-direction: column;
    gap: 4px;
    justify-content: center;
    padding: 12px;
    font-size: 13px;
    color: #63656e;
    background: #fafbfd;
    border: 1px dashed #c9d4e5;
    border-radius: 2px;
  }

  .pl-side span {
    font-size: 12px;
    color: #979ba5;
  }
</style>
