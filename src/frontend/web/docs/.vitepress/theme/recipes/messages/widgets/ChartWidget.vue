<template>
  <figure class="cw">
    <figcaption class="cw__title">{{ title }}</figcaption>
    <svg
      class="cw__svg"
      :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
      role="img"
      :aria-label="title"
    >
      <g
        v-for="(bar, index) in bars"
        :key="bar.label"
      >
        <rect
          :x="bar.x"
          :y="bar.y"
          :width="barWidth"
          :height="bar.h"
          rx="2"
          :class="{ 'is-peak': index === peakIndex }"
        />
        <text
          class="cw__value"
          :x="bar.x + barWidth / 2"
          :y="bar.y - 4"
        >{{ bar.value }}</text>
        <text
          class="cw__label"
          :x="bar.x + barWidth / 2"
          :y="HEIGHT - 4"
        >{{ bar.label }}</text>
      </g>
    </svg>
  </figure>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  /** 自定义块 JSON：{ type: 'chart', title, data: { labels, values } } */
  interface ChartData {
    title?: string;
    data?: { labels?: string[]; values?: number[] };
  }

  const props = defineProps<{ data: ChartData }>();

  const WIDTH = 360;
  const HEIGHT = 150;
  const PLOT_TOP = 18;
  const PLOT_BOTTOM = HEIGHT - 20;

  const title = computed(() => props.data.title ?? '图表');
  const labels = computed(() => props.data.data?.labels ?? []);
  const values = computed(() => props.data.data?.values ?? []);
  const barWidth = computed(() => Math.min(36, (WIDTH / Math.max(1, values.value.length)) * 0.6));
  const peakIndex = computed(() => values.value.indexOf(Math.max(...values.value)));

  const bars = computed(() => {
    const max = Math.max(1, ...values.value);
    const step = WIDTH / Math.max(1, values.value.length);
    return values.value.map((value, index) => {
      const h = ((PLOT_BOTTOM - PLOT_TOP) * value) / max;
      return { label: labels.value[index] ?? String(index + 1), value, x: step * index + (step - barWidth.value) / 2, y: PLOT_BOTTOM - h, h };
    });
  });
</script>

<style scoped>
  .cw {
    padding: 10px 12px;
    margin: 0;
    background: #fafbfd;
    border: 1px solid #eaebf0;
    border-radius: 6px;
  }

  .cw__title {
    margin-bottom: 6px;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .cw__svg {
    width: 100%;
    max-width: 420px;
  }

  rect {
    fill: #a3c5fd;
  }

  rect.is-peak {
    fill: #3a84ff;
  }

  .cw__value,
  .cw__label {
    font-size: 10px;
    text-anchor: middle;
    fill: #63656e;
  }

  .cw__label {
    fill: #979ba5;
  }
</style>
