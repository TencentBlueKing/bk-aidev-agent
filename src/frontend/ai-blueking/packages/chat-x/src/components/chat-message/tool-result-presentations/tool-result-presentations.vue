<template>
  <section
    v-for="{ id, view } in cards"
    :key="id"
    class="observation-result"
    :data-result-type="view.type"
  >
    <template v-if="view.type === 'metric_series'">
      <header>
        <strong>指标趋势</strong>
        <span v-if="view.series.length">{{ view.series.length }} 条时序</span>
      </header>
      <MetricSeriesChart
        v-for="[unit, series] in groupByUnit(view.series)"
        :key="unit"
        :series="series"
        :unit="unit"
      />
      <p
        v-if="!view.series.length"
        class="result-note"
      >
        {{ view.partial ? '本批次没有可展示的指标数据' : '所选时间范围内无指标数据' }}
      </p>
      <p
        v-if="view.sampled || view.partial"
        class="result-note"
      >
        已显示部分时序或采样点<span v-if="view.total_series > view.series.length"
          >，本批次共 {{ view.total_series }} 条时序</span
        >
      </p>
    </template>

    <template v-else>
      <header>
        <strong>日志明细</strong>
        <span v-if="view.total !== null">匹配 {{ view.total }} 条 · 已展示 {{ view.rows.length }} 条</span>
        <span v-else>已展示 {{ view.rows.length }} 条</span>
      </header>
      <ul
        v-if="view.rows.length"
        class="log-list"
      >
        <li
          v-for="(row, index) in view.rows"
          :key="index"
        >
          <div
            v-if="row.timestamp || row.level || row.source"
            class="log-meta"
          >
            <time v-if="row.timestamp">{{ logTime.format(row.timestamp) }}</time>
            <span v-if="row.level">{{ row.level }}</span>
            <span v-if="row.source">{{ row.source }}</span>
          </div>
          <pre>{{ row.text }}<span v-if="row.clipped">…</span></pre>
        </li>
      </ul>
      <p
        v-else
        class="result-note"
      >
        {{ view.total === 0 && !view.partial ? '所选时间范围内没有匹配日志' : '本批次没有返回日志行' }}
      </p>
    </template>
  </section>
</template>

<script setup lang="ts">
  import { defineAsyncComponent } from 'vue';

  import { injectGlobalConfig } from '../../../composables/use-global-config';

  import type { MetricSeries, ObservationCard } from './presentation';

  const MetricSeriesChart = defineAsyncComponent(() => import('./metric-series-chart.vue'));
  defineProps<{ cards: ObservationCard[] }>();
  const config = injectGlobalConfig();
  const logTime = new Intl.DateTimeFormat('zh-CN', {
    timeZone: config?.timezone?.value,
    dateStyle: 'short',
    timeStyle: 'medium',
  });

  const groupByUnit = (series: MetricSeries[]) => {
    const groups = new Map<string, MetricSeries[]>();
    for (const item of series) {
      const group = groups.get(item.unit);
      if (group) group.push(item);
      else groups.set(item.unit, [item]);
    }
    return groups;
  };
</script>

<style scoped>
  .observation-result {
    box-sizing: border-box;
    min-width: 0;
    max-width: 100%;
    padding: 12px;
    margin: 8px 0;
    background: #fff;
    border: 1px solid #dce2eb;
    border-radius: 6px;
  }

  header,
  .log-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 4px 8px;
    align-items: baseline;
  }

  header {
    justify-content: space-between;
    color: #313238;
  }

  header span,
  .log-meta,
  .result-note {
    font-size: 12px;
    color: #63656e;
  }

  .result-note {
    margin: 8px 0 0;
  }

  .log-meta {
    overflow-wrap: anywhere;
  }

  .log-list {
    display: grid;
    gap: 6px;
    padding: 0;
    margin: 8px 0 0;
    list-style: none;
  }

  .log-list li {
    min-width: 0;
    padding: 8px;
    background: #f5f7fa;
    border-radius: 4px;
  }

  pre {
    margin: 4px 0 0;
    font-size: 12px;
    line-height: 1.5;
    overflow-wrap: anywhere;
    white-space: pre-wrap;
  }
</style>
