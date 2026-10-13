<template>
  <DemoRecipe
    :id="RECIPE_ID"
    :changed-lines="changedLines"
    file="由当前配置生成"
    :floating-config="toConfig(config)"
    kicker="配方 1"
    lang="vue"
    :source="template"
    title="在面板头部加标签和工具按钮"
    when="适用：标注环境 / 版本，或给小鲸加业务专属的工具按钮（导出、反馈等）"
  >
    <DemoStage
      app="蓝鲸监控"
      crumbs="告警中心"
    >
      <div class="demo-card">
        <div class="hs-grid">
          <div class="hs-ctl">
            <span class="hs-label">#headerLeft</span>
            <div
              class="hs-radio"
              role="radiogroup"
              aria-label="headerLeft 标签"
            >
              <button
                v-for="tag in TAGS"
                :key="tag.value"
                type="button"
                role="radio"
                :aria-checked="config.leftTag === tag.value"
                :class="{ 'is-on': config.leftTag === tag.value }"
                @click="config.leftTag = tag.value"
              >
                {{ tag.label }}
              </button>
            </div>
          </div>
          <label class="hs-ctl">
            <span class="hs-label">#headerActions</span>
            <input
              v-model="config.customAction"
              type="checkbox"
            >
            自定义「导出对话」图标
          </label>
          <label class="hs-ctl">
            <span class="hs-label">showHistoryIcon</span>
            <input
              v-model="config.showHistoryIcon"
              type="checkbox"
            >
            显示内置历史会话图标
          </label>
        </div>
        <div class="demo-actions">
          <bk-button
            theme="primary"
            @click="handleOpen"
          >
            打开小鲸看效果
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
  import { computed, h, onBeforeUnmount, reactive, ref, watch } from 'vue';

  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState, FloatingConfig } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { diffLines } from '../../demo-kit/code-steps';
  import { DEFAULT_HEADER_CONFIG, buildHeaderTemplate, type HeaderLeftTag, type HeaderSlotConfig } from './header-template';

  const RECIPE_ID = 'header-slots';
  const PUSH_DELAY_MS = 300;
  const TAGS: { value: HeaderLeftTag; label: string }[] = [
    { value: '', label: '无' },
    { value: '测试环境', label: '测试环境' },
    { value: 'Pro', label: 'Pro' },
  ];

  const runtime = useDemoRuntime();
  const config = reactive<HeaderSlotConfig>({ ...DEFAULT_HEADER_CONFIG });
  const template = computed(() => buildHeaderTemplate(config));
  const changedLines = ref<number[]>([]);
  const feedback = ref<FeedbackState | null>(null);
  let timer: ReturnType<typeof setTimeout> | undefined;

  const onExport = () => {
    runtime.logEvent('event', '#headerActions「导出对话」被点击', RECIPE_ID);
    feedback.value = { kind: 'ok', text: '收到 #headerActions 的点击：这里接业务自己的导出逻辑。' };
  };

  const DownloadIcon = () =>
    h('svg', { width: 16, height: 16, viewBox: '0 0 16 16', fill: 'none' }, [
      h('path', { d: 'M8 2.5v7m0 0L5 6.5m3 3 3-3M3 12.5h10', stroke: 'currentColor', 'stroke-width': 1.5, 'stroke-linecap': 'round' }),
    ]);

  const toConfig = (c: HeaderSlotConfig): FloatingConfig => ({
    key: `header:${JSON.stringify(c)}`,
    props: { showHistoryIcon: c.showHistoryIcon },
    slots: {
      ...(c.leftTag ? { headerLeft: () => h('span', { class: 'demo-header-tag' }, c.leftTag) } : {}),
      ...(c.customAction
        ? { headerActions: () => h('i', { class: 'bkai-icon demo-header-action', title: '导出对话', onClick: onExport }, [h(DownloadIcon)]) }
        : {}),
    },
  });

  watch(template, (next, prev) => {
    changedLines.value = diffLines(prev, next);
  });

  watch(
    () => ({ ...config }),
    () => {
      clearTimeout(timer);
      timer = setTimeout(() => runtime.updateFloatingConfig(RECIPE_ID, toConfig(config)), PUSH_DELAY_MS);
    },
  );

  onBeforeUnmount(() => clearTimeout(timer));

  const handleOpen = async () => {
    clearTimeout(timer);
    runtime.updateFloatingConfig(RECIPE_ID, toConfig(config));
    const result = await runtime.run(RECIPE_ID, 'open', ai => ai.show());
    feedback.value = resultFeedback(result, () => ({ kind: 'ok', text: '已打开，看右侧面板头部；继续调整开关会按新配置重新挂载。' }));
  };
</script>

<style scoped>
  .hs-grid {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .hs-ctl {
    display: flex;
    gap: 10px;
    align-items: center;
    font-size: 13px;
    color: #63656e;
  }

  .hs-label {
    flex: 0 0 120px;
    font-family: var(--vp-font-family-mono);
    font-size: 12px;
    color: #313238;
  }

  .hs-radio {
    display: inline-flex;
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .hs-radio button {
    padding: 2px 12px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #fff;
    border: 0;
    border-right: 1px solid #dcdee5;
  }

  .hs-radio button:last-child {
    border-right: 0;
  }

  .hs-radio button.is-on {
    color: #fff;
    background: #3a84ff;
  }
</style>

<style>
  /* 插槽内容渲染在浮窗面板中（teleport 到 body），不能用 scoped */
  .demo-header-tag {
    display: inline-flex;
    align-items: center;
    height: 18px;
    padding: 0 6px;
    margin-left: 6px;
    font-size: 11px;
    color: #b45309;
    background: #fff3e1;
    border-radius: 2px;
  }

  .demo-header-action {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }
</style>
