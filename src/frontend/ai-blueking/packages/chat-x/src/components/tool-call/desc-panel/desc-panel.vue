<template>
  <div class="toolcall-desc">
    <div class="desc-title">{{ title }}</div>
    <div class="desc-panel">
      <template v-if="typeof data === 'object'">
        <div
          v-for="(value, key) in data"
          :key="key"
          class="desc-panel-item"
        >
          <span class="desc-label"><HighlightKeyword :text="key" />:</span>
          <span
            v-overflow-tips="{
              ...commonTippyOptions,
              text: typeof value === 'object' && value ? JSON.stringify(value) : value,
              appendTo: 'parent',
            }"
            class="desc-value"
          >
            <HighlightKeyword
              style="word-break: break-all"
              :text="typeof value === 'object' && value ? JSON.stringify(value) : value"
            />
          </span>
        </div>
      </template>
      <template v-else><HighlightKeyword :text="data" /></template>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { useCommonTippyInject } from '../../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../../directives';
  import HighlightKeyword from '../../highlight-keyword/highlight-keyword';

  const props = defineProps<{
    desc?: string;
    title: string;
  }>();
  const commonTippyOptions = useCommonTippyInject();
  const data = computed<Record<string, string>>(() => {
    try {
      return JSON.parse(props.desc || '');
    } catch {
      return props.desc;
    }
  });
</script>
<style lang="scss">
  .toolcall-desc {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 100%;
    padding: 12px;
    background-color: #f5f7fa;

    .desc-title {
      margin-bottom: 6px;
      font-size: 12px;
      font-weight: bold;
      color: #313238;
    }

    .desc-panel {
      display: flex;
      flex-direction: column;
      gap: 4px;

      .desc-panel-item {
        display: flex;
        gap: 4px;
        align-items: center;
        line-height: 20px;

        .desc-label {
          color: #313238;
        }

        .desc-value {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }
      }
    }
  }
</style>
