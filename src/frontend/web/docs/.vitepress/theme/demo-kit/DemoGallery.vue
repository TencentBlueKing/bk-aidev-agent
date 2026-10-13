<template>
  <div class="demo-gallery">
    <div class="demo-gallery__picks">
      <a
        v-for="entry in picks"
        :key="entry.id"
        class="demo-gallery__pick"
        :href="withBase(entry.link)"
      >
        <div
          class="demo-gallery__ill"
          :class="`is-${entry.pick?.illustration}`"
          aria-hidden="true"
        >
          <i
            v-for="n in entry.pick?.illustration === 'atomic' ? 6 : 0"
            :key="n"
          />
        </div>
        <div class="demo-gallery__pick-title">{{ entry.title }}</div>
        <p>{{ entry.summary }}</p>
        <div class="demo-gallery__when">{{ entry.pick?.when }}</div>
      </a>
    </div>

    <div
      class="demo-gallery__filter"
      role="radiogroup"
      aria-label="按集成形态筛选"
    >
      <span>按集成形态筛选</span>
      <button
        v-for="f in FILTERS"
        :key="f"
        type="button"
        role="radio"
        class="demo-gallery__chip"
        :aria-checked="filter === f"
        :class="{ 'is-on': filter === f }"
        @click="filter = f"
      >
        {{ f }}
      </button>
    </div>

    <p
      v-if="!groups.length"
      class="demo-gallery__empty"
    >
      「{{ filter }}」形态的更多示例正在整理中，可以先看上面的集成形态示例。
    </p>
    <template
      v-for="group in groups"
      :key="group.id"
    >
      <div class="demo-gallery__group">
        {{ group.title }}<span v-if="group.subtitle">{{ group.subtitle }}</span>
      </div>
      <div class="demo-gallery__cards">
        <a
          v-for="entry in group.entries"
          :key="entry.id"
          class="demo-gallery__card"
          :href="withBase(entry.link)"
        >
          <span class="demo-gallery__card-head">
            {{ entry.title }}<span class="demo-gallery__count">{{ entry.recipes }} 个配方</span>
          </span>
          <span class="demo-gallery__summary">{{ entry.summary }}</span>
          <span class="demo-gallery__tags">
            <span
              v-for="mode in entry.modes"
              :key="mode"
              class="demo-gallery__tag is-mode"
            >{{ mode }}</span>
            <span
              v-if="entry.mockReady"
              class="demo-gallery__tag is-mock"
            >Mock 可用</span>
          </span>
        </a>
      </div>
    </template>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';
  import { withBase } from 'vitepress';

  import { DEMO_GROUPS, listGalleryEntries, type DemoMode } from '../../demos-catalog';

  type Filter = '全部' | DemoMode;

  const FILTERS: Filter[] = ['全部', '浮窗', '嵌入', '原子'];

  const filter = ref<Filter>('全部');
  const entries = listGalleryEntries();
  const picks = entries.filter(e => e.group === 'integration');

  const groups = computed(() =>
    DEMO_GROUPS.filter(g => g.id !== 'start' && g.id !== 'integration')
      .map(g => ({
        ...g,
        entries: entries.filter(
          e => e.group === g.id && (filter.value === '全部' || e.modes.includes(filter.value as DemoMode)),
        ),
      }))
      .filter(g => g.entries.length > 0),
  );
</script>

<style scoped>
  .demo-gallery__picks {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 20px 0 8px;
  }

  .demo-gallery__pick {
    display: block;
    padding: 18px;
    color: inherit;
    text-decoration: none;
    background: var(--vp-c-bg);
    border: 1px solid var(--vp-c-divider);
    border-radius: 12px;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .demo-gallery__pick:hover {
    border-color: var(--vp-c-brand-2, #4a9eff);
    box-shadow: 0 6px 20px rgb(20 130 255 / 8%);
  }

  .demo-gallery__pick p {
    margin: 0;
    font-size: 13px;
    line-height: 1.6;
    color: var(--vp-c-text-2);
  }

  .demo-gallery__pick-title {
    margin-bottom: 4px;
    font-size: 16px;
    font-weight: 600;
    color: var(--vp-c-text-1);
  }

  .demo-gallery__when {
    margin-top: 10px;
    font-size: 12px;
    color: var(--vp-c-text-3);
  }

  .demo-gallery__ill {
    position: relative;
    height: 86px;
    margin-bottom: 14px;
    overflow: hidden;
    background: #f5f7fa;
    border: 1px solid #e6e8ee;
    border-radius: 8px;
  }

  .demo-gallery__ill.is-floating::before {
    position: absolute;
    top: 12px;
    left: 10px;
    width: 44%;
    height: 8px;
    content: '';
    background: #dfe3ea;
    border-radius: 4px;
    box-shadow: 0 16px 0 #e8ebf0, 0 32px 0 #e8ebf0, 0 48px 0 #e8ebf0;
  }

  .demo-gallery__ill.is-floating::after {
    position: absolute;
    top: 8px;
    right: 8px;
    bottom: 8px;
    width: 34%;
    content: '';
    background: #fff;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgb(0 0 0 / 12%);
  }

  .demo-gallery__ill.is-embedded::before {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    width: 22%;
    content: '';
    background: #182132;
  }

  .demo-gallery__ill.is-embedded::after {
    position: absolute;
    top: 8px;
    right: 8px;
    bottom: 8px;
    left: 28%;
    content: '';
    background: #fff;
    border: 1px solid #e3e6ec;
    border-radius: 4px;
  }

  .demo-gallery__ill.is-atomic {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 6px;
    padding: 10px;
  }

  .demo-gallery__ill.is-atomic i {
    background: #fff;
    border: 1px dashed #b9c3d3;
    border-radius: 4px;
  }

  .demo-gallery__filter {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-top: 26px;
    font-size: 13px;
    color: var(--vp-c-text-2);
  }

  .demo-gallery__chip {
    padding: 4px 12px;
    font-size: 13px;
    color: var(--vp-c-text-2);
    cursor: pointer;
    background: var(--vp-c-bg);
    border: 1px solid var(--vp-c-divider);
    border-radius: 999px;
  }

  .demo-gallery__chip.is-on {
    color: #fff;
    background: var(--vp-c-brand-1, var(--vp-c-brand));
    border-color: var(--vp-c-brand-1, var(--vp-c-brand));
  }

  .demo-gallery__empty {
    margin: 24px 0 0;
    font-size: 13px;
    color: var(--vp-c-text-3);
  }

  .demo-gallery__group {
    display: flex;
    gap: 10px;
    align-items: baseline;
    margin: 30px 0 12px;
    font-size: 16px;
    font-weight: 600;
    color: var(--vp-c-text-1);
  }

  .demo-gallery__group span {
    font-size: 13px;
    font-weight: 400;
    color: var(--vp-c-text-3);
  }

  .demo-gallery__cards {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }

  .demo-gallery__card {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 14px 16px;
    color: inherit;
    text-decoration: none;
    background: var(--vp-c-bg);
    border: 1px solid var(--vp-c-divider);
    border-radius: 10px;
  }

  .demo-gallery__card:hover {
    border-color: var(--vp-c-brand-2, #4a9eff);
  }

  .demo-gallery__card-head {
    display: flex;
    gap: 8px;
    align-items: center;
    font-size: 15px;
    font-weight: 600;
    color: var(--vp-c-text-1);
  }

  .demo-gallery__count {
    margin-left: auto;
    font-size: 12px;
    font-weight: 400;
    color: var(--vp-c-text-3);
  }

  .demo-gallery__summary {
    font-size: 13px;
    line-height: 1.6;
    color: var(--vp-c-text-2);
  }

  .demo-gallery__tags {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }

  .demo-gallery__tag {
    padding: 0 7px;
    font-size: 11.5px;
    line-height: 20px;
    border-radius: 4px;
  }

  .demo-gallery__tag.is-mode {
    color: #0a6ad9;
    background: #e1efff;
  }

  .demo-gallery__tag.is-mock {
    color: #15803d;
    background: #dcfce7;
  }

  @media (max-width: 760px) {
    .demo-gallery__picks,
    .demo-gallery__cards {
      grid-template-columns: 1fr;
    }
  }
</style>
