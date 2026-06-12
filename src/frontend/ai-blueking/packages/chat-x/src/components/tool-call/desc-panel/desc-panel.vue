<template>
  <div class="toolcall-desc">
    <div class="desc-title">{{ title }}</div>
    <div class="desc-panel">
      <!-- null 的 typeof 为 object，需排除，避免 v-for 异常；键/值统一转字符串以满足 HighlightKeyword -->
      <template v-if="data !== null && typeof data === 'object'">
        <div
          v-for="(value, key) in data"
          :key="key"
          class="desc-panel-item"
        >
          <span class="desc-label"><HighlightKeyword :text="String(key)" />:</span>
          <span class="desc-value">
            <HighlightKeyword
              style="word-break: break-all"
              :text="formatHighlightSegment(value)"
            />
          </span>
        </div>
      </template>
      <template v-else
        ><HighlightKeyword
          :style="{ wordBreak: 'break-all' }"
          :text="formatHighlightSegment(data)"
      /></template>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import HighlightKeyword from '../../highlight-keyword/highlight-keyword';

  const props = defineProps<{
    desc?: string;
    title: string;
  }>();

  /** JSON 解析后的标量 / 嵌套对象均转为可展示的字符串，供 HighlightKeyword（String prop）使用 */
  const formatHighlightSegment = (value: unknown): string => {
    if (value === undefined || value === null) return '';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };

  const data = computed(() => {
    try {
      return JSON.parse(props.desc || '') as unknown;
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
      font-size: var(--ai-font-size, 12px);
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

        // align-items: center;
        line-height: 20px;

        .desc-label {
          color: #313238;
        }

        .desc-value {
          overflow: hidden;
          text-overflow: ellipsis;

          // white-space: nowrap;
        }
      }
    }
  }
</style>
