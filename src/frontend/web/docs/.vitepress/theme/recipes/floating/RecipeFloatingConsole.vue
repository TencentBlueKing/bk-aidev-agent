<template>
  <DemoRecipe
    :id="RECIPE_ID"
    :changed-lines="changedLines"
    file="由当前配置生成"
    :floating-config="initialConfig"
    kicker="配方 1"
    lang="vue"
    :source="template"
    title="调一调浮窗的外观与交互"
    when="适用：确定悬浮球、拖拽、尺寸、划词这些开关在你的产品里怎么配"
  >
    <DemoStage
      app="作业平台"
      crumbs="作业执行详情"
    >
      <div class="demo-card">
        <div class="fc-grid">
          <div class="fc-ctl">
            <span class="fc-label">可拖拽</span>
            <button
              type="button"
              role="switch"
              class="fc-switch"
              :aria-checked="config.draggable"
              :class="{ 'is-on': config.draggable }"
              @click="config.draggable = !config.draggable"
            />
            <code class="fc-hint">draggable</code>
          </div>
          <div class="fc-ctl">
            <span class="fc-label">悬浮球</span>
            <button
              type="button"
              role="switch"
              class="fc-switch"
              :aria-checked="config.showNimbus"
              :class="{ 'is-on': config.showNimbus }"
              @click="config.showNimbus = !config.showNimbus"
            />
            <code class="fc-hint">hide-nimbus</code>
          </div>
          <div class="fc-ctl">
            <span class="fc-label">悬浮球尺寸</span>
            <div
              class="fc-radio"
              role="radiogroup"
              aria-label="悬浮球尺寸"
            >
              <button
                v-for="size in SIZES"
                :key="size.value"
                type="button"
                role="radio"
                :aria-checked="config.nimbusSize === size.value"
                :class="{ 'is-on': config.nimbusSize === size.value }"
                @click="config.nimbusSize = size.value"
              >
                {{ size.label }}
              </button>
            </div>
          </div>
          <div class="fc-ctl">
            <span class="fc-label">默认宽度</span>
            <input
              v-model.number="config.defaultWidth"
              aria-label="默认宽度"
              max="640"
              min="360"
              step="20"
              type="range"
            >
            <code class="fc-hint">{{ config.defaultWidth }}px</code>
          </div>
          <div class="fc-ctl">
            <span class="fc-label">划词弹窗</span>
            <button
              type="button"
              role="switch"
              class="fc-switch"
              :aria-checked="config.enablePopup"
              :class="{ 'is-on': config.enablePopup }"
              @click="config.enablePopup = !config.enablePopup"
            />
            <code class="fc-hint">enable-popup</code>
          </div>
          <div class="fc-ctl">
            <span class="fc-label">前端快捷指令</span>
            <button
              type="button"
              role="switch"
              class="fc-switch"
              :aria-checked="config.frontendShortcuts"
              :class="{ 'is-on': config.frontendShortcuts }"
              @click="config.frontendShortcuts = !config.frontendShortcuts"
            />
            <code class="fc-hint">shortcuts</code>
          </div>
        </div>
      </div>
      <div class="fc-article">
        <div class="fc-article__label">执行日志（开启「划词弹窗」后，选中这段文字试试）</div>
        步骤 3「分发配置文件」在 12 台主机上执行失败，返回码 255：目标路径 /data/conf 无写权限。重试 2 次后仍失败，作业已暂停等待人工处理。
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
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';

  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import {
    DEFAULT_CONSOLE_CONFIG,
    buildFloatingTemplate,
    diffLines,
    toFloatingConfig,
    type FloatingConsoleConfig,
  } from './console-template';

  const RECIPE_ID = 'floating-console';
  const PUSH_DELAY_MS = 300;
  const SIZES: { value: FloatingConsoleConfig['nimbusSize']; label: string }[] = [
    { value: 'small', label: '小' },
    { value: 'normal', label: '中' },
    { value: 'large', label: '大' },
  ];

  const runtime = useDemoRuntime();
  const config = reactive<FloatingConsoleConfig>({ ...DEFAULT_CONSOLE_CONFIG });
  const initialConfig = toFloatingConfig(config);
  const template = computed(() => buildFloatingTemplate(config));
  const changedLines = ref<number[]>([]);
  const feedback = ref<FeedbackState | null>(null);
  let timer: ReturnType<typeof setTimeout> | undefined;

  const pushConfig = () => runtime.updateFloatingConfig(RECIPE_ID, toFloatingConfig(config));

  watch(template, (next, prev) => {
    changedLines.value = diffLines(prev, next);
  });

  watch(
    () => ({ ...config }),
    () => {
      clearTimeout(timer);
      timer = setTimeout(pushConfig, PUSH_DELAY_MS);
    },
  );

  onBeforeUnmount(() => clearTimeout(timer));

  const handleOpen = async () => {
    clearTimeout(timer);
    pushConfig();
    const result = await runtime.run(RECIPE_ID, 'open', ai => ai.show());
    feedback.value = resultFeedback(result, () => ({
      kind: 'ok',
      text: '已打开。继续调整上面的开关，右侧小鲸会按新配置重新挂载。',
    }));
  };
</script>

<style scoped>
  .fc-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px 24px;
  }

  .fc-ctl {
    display: flex;
    gap: 10px;
    align-items: center;
    font-size: 13px;
    color: #63656e;
  }

  .fc-label {
    flex: 0 0 84px;
    color: #313238;
  }

  .fc-hint {
    padding: 0;
    font-size: 11px;
    color: #979ba5;
    background: none;
  }

  .fc-switch {
    position: relative;
    flex-shrink: 0;
    width: 34px;
    height: 18px;
    padding: 0;
    cursor: pointer;
    background: #c4c6cc;
    border: 0;
    border-radius: 9px;
    transition: background 0.15s;
  }

  .fc-switch::after {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 14px;
    height: 14px;
    content: '';
    background: #fff;
    border-radius: 50%;
    transition: left 0.15s;
  }

  .fc-switch.is-on {
    background: #3a84ff;
  }

  .fc-switch.is-on::after {
    left: 18px;
  }

  .fc-radio {
    display: inline-flex;
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .fc-radio button {
    padding: 2px 12px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #fff;
    border: 0;
    border-right: 1px solid #dcdee5;
  }

  .fc-radio button:last-child {
    border-right: 0;
  }

  .fc-radio button.is-on {
    color: #fff;
    background: #3a84ff;
  }

  .fc-ctl input[type='range'] {
    width: 140px;
  }

  .fc-article {
    padding: 12px 14px;
    margin-top: 12px;
    line-height: 1.8;
    background: #fff;
    border: 1px dashed #c9d4e5;
    border-radius: 2px;
  }

  .fc-article__label {
    margin-bottom: 4px;
    font-size: 12px;
    color: #979ba5;
  }

  @media (max-width: 720px) {
    .fc-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
