<template>
  <div class="ai-model-description-card">
    <div class="ai-model-description-card-header">
      <div class="ai-model-description-card-name">
        {{ model.llm_name }}
      </div>
      <!-- 没有描述时按设计稿用「--」占位 -->
      <div class="ai-model-description-card-desc">
        {{ description || '--' }}
      </div>
    </div>
    <div
      v-if="reasoningOptions.length"
      class="ai-model-description-card-reasoning"
    >
      <span class="ai-model-description-card-reasoning-label">
        {{ t('思考深度') }}
      </span>
      <ReasoningEffortSlider
        :disabled="model.disabled"
        :effort="effort"
        :options="reasoningOptions"
        @change="emit('change', $event)"
        @dragging="emit('dragging', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  import { t } from '../../../lang/lang';
  import { getReasoningOptions } from './reasoning-effort';
  import ReasoningEffortSlider from './reasoning-effort-slider.vue';

  import type { IModelOption, ReasoningEffort } from './types';

  const props = defineProps<{
    /** 当前生效档位（由调用方按「当前模型取 v-model、其余取 default_effort」解析好） */
    effort?: ReasoningEffort;
    /** 卡片对应的模型 */
    model: IModelOption;
  }>();
  const emit = defineEmits<{
    (e: 'change', effort: ReasoningEffort): void;
    (e: 'dragging', dragging: boolean): void;
  }>();

  const description = computed(() => props.model.description?.trim());
  const reasoningOptions = computed(() => getReasoningOptions(props.model));
</script>

<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  // 尺寸、间距与配色取自 Figma「模型选择」思考深度气泡
  .ai-model-description-card {
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-sizing: border-box;
    width: 300px;
    padding: 12px 16px;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height, 20px);
    background: #fff;
    border-radius: 4px;

    &-header {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }

    &-name {
      overflow: hidden;
      font-weight: 700;
      color: variables.$color-title;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    // 描述最多 3 行，超出省略
    &-desc {
      display: -webkit-box;
      overflow: hidden;
      color: variables.$color-text-secondary;
      word-break: break-all;
      -webkit-line-clamp: 3;
      -webkit-box-orient: vertical;
    }

    &-reasoning {
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: space-between;
      padding-top: 12px;

      // 分割线色 Neutral/7 #eaebf0，variables 中无对应变量
      border-top: 1px solid #eaebf0;

      &-label {
        flex: 0 0 auto;
        color: variables.$color-text-secondary;
        white-space: nowrap;
      }
    }
  }
</style>
