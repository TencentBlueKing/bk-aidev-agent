<template>
  <div class="demo-inspector">
    <div
      class="demo-inspector__tabs"
      role="tablist"
    >
      <button
        v-for="t in tabs"
        :key="t.key"
        type="button"
        role="tab"
        class="demo-inspector__tab"
        :aria-selected="tab === t.key"
        :class="{ 'is-on': tab === t.key }"
        @click="tab = t.key"
      >
        {{ t.label }}
        <span
          v-if="t.count !== null"
          class="demo-inspector__count"
          :class="{ 'is-pulse': pulse[t.key] }"
        >{{ t.count }}</span>
      </button>
      <div class="demo-inspector__aside">
        <template v-if="tab === 'code'">
          <span>高亮 = 当前步骤</span>
          <span class="demo-inspector__file">{{ file }}</span>
          <button
            type="button"
            class="demo-link"
            @click="copySource"
          >
            {{ copyText }}
          </button>
        </template>
        <button
          v-else-if="records.events.length || records.requests.length"
          type="button"
          class="demo-link"
          @click="runtime.recorder.clear(recipeId)"
        >
          清空
        </button>
      </div>
    </div>

    <div
      ref="bodyRef"
      class="demo-inspector__body"
    >
      <div
        v-show="tab === 'code'"
        ref="codeRef"
        class="demo-inspector__code"
      >
        <div
          v-if="highlighted"
          v-html="highlighted"
        />
        <pre v-else><code>{{ source }}</code></pre>
      </div>

      <template v-if="tab === 'events'">
        <div
          v-if="!records.events.length"
          class="demo-inspector__empty"
        >
          还没有事件。点击上方模拟页面里的按钮试试
        </div>
        <div
          v-for="e in records.events"
          :key="e.id"
          class="demo-event"
        >
          <span class="demo-event__time">{{ e.time }}</span>
          <span
            class="demo-kind"
            :class="`is-${e.kind}`"
          >{{ KIND_LABELS[e.kind] }}</span>
          <span class="demo-event__text">{{ e.text }}</span>
        </div>
      </template>

      <template v-if="tab === 'requests'">
        <div
          v-if="!records.requests.length"
          class="demo-inspector__empty"
        >
          {{
            state.fetchHooked
              ? '还没有请求。小鲸发出的每个请求都会出现在这里，可展开查看 Header 与 Body'
              : '请求记录不可用：未能接管 fetch，请使用浏览器 DevTools 的 Network 面板查看'
          }}
        </div>
        <div
          v-for="r in records.requests"
          :key="r.id"
          class="demo-request"
          :class="{ 'is-open': expanded.has(r.id) }"
        >
          <button
            type="button"
            class="demo-request__row"
            :aria-expanded="expanded.has(r.id)"
            @click="toggle(r.id)"
          >
            <span class="demo-request__arrow">›</span>
            <span
              class="demo-request__method"
              :class="`is-${r.method.toLowerCase()}`"
            >{{ r.method }}</span>
            <span class="demo-request__path">{{ r.path }}</span>
            <span
              v-if="r.sse"
              class="demo-tag"
            >SSE</span>
            <span
              v-if="r.injectedKeys.length"
              class="demo-tag is-inject"
            >注入 Header</span>
            <span
              v-if="r.status !== null && r.status >= 400"
              class="demo-tag is-error"
            >{{ r.status }}</span>
            <span class="demo-request__time">{{ r.time }}</span>
          </button>
          <div
            v-if="expanded.has(r.id)"
            class="demo-request__detail"
          >
            <div class="demo-request__label">自定义 Header（来自 requestOptions）</div>
            <div
              v-if="Object.keys(r.headers).length"
              class="demo-request__box"
            >
              <div
                v-for="(value, key) in r.headers"
                :key="key"
                :class="{ 'is-inject': r.injectedKeys.includes(String(key)) }"
              >
                {{ key }}: {{ value }}
                <span
                  v-if="r.injectedKeys.includes(String(key))"
                  class="demo-request__note"
                >← 本次注入</span>
              </div>
            </div>
            <div
              v-else
              class="demo-request__box"
            >
              无
            </div>
            <template v-if="r.query">
              <div class="demo-request__label">Query</div>
              <pre>{{ JSON.stringify(r.query, null, 2) }}</pre>
            </template>
            <template v-if="r.body !== null">
              <div class="demo-request__label">Body</div>
              <pre>{{ JSON.stringify(r.body, null, 2) }}</pre>
            </template>
          </div>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';

  import { highlightCode } from '../utils/shiki-vue-highlight';
  import { findStepRange } from './code-steps';
  import type { InspectorTab, TimelineKind } from './types';
  import { useDemoRuntime } from './use-demo-runtime';

  interface DemoInspectorProps {
    recipeId: string;
    source: string;
    file: string;
    lang?: 'typescript' | 'vue';
    /** 需要高亮为「已变化」的行（0 基） */
    changedLines?: number[];
  }

  const props = withDefaults(defineProps<DemoInspectorProps>(), { lang: 'typescript', changedLines: () => [] });

  const KIND_LABELS: Record<TimelineKind, string> = {
    call: '调用',
    event: '事件',
    resolve: '完成',
    stream: '流式',
    error: '错误',
    mount: '挂载',
  };
  const PULSE_MS = 600;

  const runtime = useDemoRuntime();
  const { state } = runtime;
  const records = computed(() => runtime.recorder.get(props.recipeId));
  const tab = computed<InspectorTab>({
    get: () => state.inspectorTab[props.recipeId] ?? 'code',
    set: value => runtime.openTab(props.recipeId, value),
  });
  const tabs = computed(() => [
    { key: 'code' as const, label: '代码', count: null },
    { key: 'events' as const, label: '事件', count: records.value.events.length },
    { key: 'requests' as const, label: '请求', count: records.value.requests.length },
  ]);

  const highlighted = ref('');
  const bodyRef = ref<HTMLElement>();
  const codeRef = ref<HTMLElement>();
  const expanded = reactive(new Set<number>());
  const pulse = reactive<Record<InspectorTab, boolean>>({ code: false, events: false, requests: false });
  const copyText = ref('复制');

  let highlightSeq = 0;
  const rehighlight = async () => {
    const seq = (highlightSeq += 1);
    try {
      const html = await highlightCode(props.source, props.lang);
      if (seq === highlightSeq) highlighted.value = html;
    } catch (e) {
      console.error('[DemoInspector] shiki highlight failed', e);
    }
  };

  onMounted(rehighlight);
  watch(() => [props.source, props.lang], rehighlight);

  const stepRange = computed(() => {
    const step = state.activeStep[props.recipeId];
    return step ? findStepRange(props.source, step) : null;
  });

  const applyHighlight = async () => {
    await nextTick();
    const root = codeRef.value;
    const body = bodyRef.value;
    if (!root || !body) return;
    const lines = root.querySelectorAll<HTMLElement>('.line');
    const range = stepRange.value;
    const changed = new Set(props.changedLines);
    let first: HTMLElement | undefined;
    lines.forEach((line, index) => {
      const on = !!range && index >= range[0] && index <= range[1];
      line.classList.toggle('is-step', on);
      line.classList.toggle('is-changed', changed.has(index));
      if ((on || changed.has(index)) && !first) first = line;
    });
    if (first && tab.value === 'code') {
      const offset = first.getBoundingClientRect().top - body.getBoundingClientRect().top + body.scrollTop;
      body.scrollTo({ top: Math.max(0, offset - 32), behavior: 'smooth' });
    }
  };

  watch([highlighted, stepRange, tab, () => props.changedLines], applyHighlight);

  const flash = (key: InspectorTab) => {
    pulse[key] = false;
    requestAnimationFrame(() => {
      pulse[key] = true;
      setTimeout(() => {
        pulse[key] = false;
      }, PULSE_MS);
    });
  };

  watch(
    () => records.value.events.length,
    async (next, prev) => {
      if (next <= prev) return;
      flash('events');
      if (tab.value === 'events') {
        await nextTick();
        bodyRef.value?.scrollTo({ top: bodyRef.value.scrollHeight });
      }
    },
  );
  watch(
    () => records.value.requests.length,
    (next, prev) => {
      if (next > prev) flash('requests');
    },
  );

  const toggle = (id: number) => {
    if (expanded.has(id)) expanded.delete(id);
    else expanded.add(id);
  };

  const copySource = async () => {
    try {
      await navigator.clipboard.writeText(props.source);
      copyText.value = '已复制';
    } catch {
      copyText.value = '复制失败';
    }
    setTimeout(() => {
      copyText.value = '复制';
    }, 1500);
  };
</script>
