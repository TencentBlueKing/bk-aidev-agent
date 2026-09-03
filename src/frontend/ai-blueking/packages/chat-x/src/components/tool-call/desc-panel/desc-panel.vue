<template>
  <div class="ai-toolcall-desc">
    <div class="desc-title">
      {{ title }}
      <span
        v-if="desc"
        class="desc-copy"
        :title="t('复制')"
        @click="handleCopy"
      >
        <CopyIcon />
      </span>
    </div>
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

  import { useClipboard } from '../../../composables/use-clipboard';
  import { CopyIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import HighlightKeyword from '../../highlight-keyword/highlight-keyword';

  const props = defineProps<{
    desc?: string;
    title: string;
  }>();

  const { copy } = useClipboard();

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

  /** 复制原始文本，保留 JSON 结构便于二次使用 */
  const handleCopy = () => {
    if (props.desc) {
      copy(props.desc);
    }
  };
</script>
<style lang="scss">
  .ai-toolcall-desc {
    display: flex;
    flex-direction: column;
    width: 100%;

    // 设计标注：输入输出内容区域限高 300px，超出滚动
    max-height: 300px;

    // 纵向留白交给标题与内容承担，避免标题吸顶时上方 padding 漏出滚动内容
    padding: 0 16px;
    overflow-y: auto;
    font-size: var(--ai-font-size, 12px);
    line-height: 20px;
    color: #4d4f56;
    background-color: #f5f7fa;
    border-radius: 2px;

    .desc-title {
      // 设计标注：标题吸顶不动
      position: sticky;
      top: 0;
      display: flex;
      gap: 4px;
      align-items: center;
      padding: 12px 0 4px;
      font-weight: bold;
      background-color: #f5f7fa;
    }

    .desc-copy {
      display: flex;
      visibility: hidden;
      align-items: center;
      margin-left: auto;
      color: #979ba5;
      cursor: pointer;

      &:hover {
        color: #3a84ff;
      }

      .ai-common-icon {
        width: 14px;
        height: 14px;
      }
    }

    &:hover .desc-copy {
      visibility: visible;
    }

    .desc-panel {
      display: flex;
      flex-direction: column;
      gap: 4px;
      padding-bottom: 12px;

      .desc-panel-item {
        display: flex;
        line-height: 20px;

        .desc-value {
          overflow: hidden;
          text-overflow: ellipsis;
        }
      }
    }
  }
</style>
