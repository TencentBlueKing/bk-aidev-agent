<template>
  <div
    ref="host"
    :aria-label="ariaLabel"
    class="series-chart"
    role="img"
  />
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

  import { LineChart } from 'echarts/charts';
  import { GridComponent, LegendComponent, MarkLineComponent, TooltipComponent } from 'echarts/components';
  import { type EChartsType, init, use } from 'echarts/core';
  import { CanvasRenderer } from 'echarts/renderers';

  import { injectGlobalConfig } from '../../../composables/use-global-config';

  import type { MetricSeries } from './presentation';

  use([CanvasRenderer, LineChart, GridComponent, LegendComponent, MarkLineComponent, TooltipComponent]);

  const props = defineProps<{
    endTime?: number;
    series: MetricSeries[];
    startTime?: number;
    timezone?: string;
    triggerTime?: number;
    unit: string;
  }>();
  const host = ref<HTMLElement | null>(null);
  const ariaLabel = computed(() => `指标趋势图：${props.series.map(series => series.name).join('、')}`);
  const config = injectGlobalConfig();
  const time = computed(
    () =>
      new Intl.DateTimeFormat('zh-CN', {
        timeZone: props.timezone ?? config?.timezone?.value,
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
      }),
  );
  let chart: EChartsType | undefined;
  let observer: ResizeObserver | undefined;

  const draw = () => {
    if (!host.value || !host.value.clientWidth) return;
    chart ??= init(host.value);
    chart.setOption(
      {
        animation: false,
        grid: { left: 46, right: 12, top: props.series.length > 1 ? 40 : 18, bottom: 30 },
        tooltip: { trigger: 'axis', renderMode: 'richText', confine: true },
        legend: { show: props.series.length > 1, type: 'scroll' },
        xAxis: {
          type: 'time',
          min: props.startTime,
          max: props.endTime,
          splitNumber: 3,
          axisLabel: { formatter: (value: number) => time.value.format(value), hideOverlap: true },
        },
        yAxis: { type: 'value', name: props.unit, scale: true },
        series: props.series.map((series, index) => ({
          name: series.name,
          type: 'line',
          data: series.points,
          showSymbol: series.points.length <= 2,
          connectNulls: false,
          ...(props.triggerTime && index === 0
            ? {
                markLine: {
                  silent: true,
                  symbol: 'none',
                  label: { formatter: '告警触发', position: 'insideEndTop' },
                  lineStyle: { type: 'dashed', color: '#e58a14' },
                  data: [{ xAxis: props.triggerTime }],
                },
              }
            : {}),
        })),
      },
      { notMerge: true },
    );
  };

  onMounted(() => {
    draw();
    observer = new ResizeObserver(() => {
      if (chart) chart.resize();
      else draw();
    });
    if (host.value) observer.observe(host.value);
  });
  onBeforeUnmount(() => {
    observer?.disconnect();
    chart?.dispose();
  });
  watch(() => [props.series, props.unit, props.triggerTime, props.startTime, props.endTime, time.value], draw);
</script>

<style scoped>
  .series-chart {
    width: 100%;
    height: 204px;
  }
</style>
