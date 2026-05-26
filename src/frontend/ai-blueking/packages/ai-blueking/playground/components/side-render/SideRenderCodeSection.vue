<template>
  <div class="side-render-code-section">
    <div class="code-section-header">
      <div>
        <div class="code-title">接入代码（可复制到业务项目）</div>
        <p class="code-desc">
          与页面顶部选中的场景一致，便于对照上方 demo 理解。
        </p>
      </div>
    </div>

    <div class="code-scenario-banner">
      <span class="code-scenario-banner__badge">{{ activeScenarioMeta.badge }}</span>
      <span class="code-scenario-banner__title">{{ activeScenarioMeta.title }}</span>
      <span class="code-scenario-banner__files">
        推荐文件：
        <code
          v-for="file in recommendedFiles"
          :key="file"
        >
          {{ file }}
        </code>
      </span>
    </div>

    <Transition
      name="code-fade"
      mode="out-in"
    >
      <div
        :key="props.activeScenario"
        class="code-blocks"
      >
        <div
          v-for="block in codeBlocks"
          :key="block.title"
          class="code-block"
        >
          <div class="code-block-title">
            {{ block.title }}
            <span
              v-if="block.fileHint"
              class="code-block-file"
            >
              {{ block.fileHint }}
            </span>
          </div>
          <p
            v-if="block.desc"
            class="code-block-desc"
          >
            {{ block.desc }}
          </p>
          <pre class="guide-code"><code>{{ block.code }}</code></pre>
        </div>
      </div>
    </Transition>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  import { getSideRenderCodeBlocks } from './side-render-code-examples';
  import { getSideRenderScenarioById, type SideRenderScenarioId } from './side-render-scenarios';

  const props = defineProps<{
    activeScenario: SideRenderScenarioId;
  }>();

  const activeScenarioMeta = computed(() => getSideRenderScenarioById(props.activeScenario));

  const codeBlocks = computed(() => getSideRenderCodeBlocks(props.activeScenario));

  const recommendedFiles = computed(() => {
    if (props.activeScenario === 'custom-fetch') {
      return [
        'CustomTabContent.vue',
        'use-side-render-handlers.ts',
        'use-side-render-custom-tab-change.ts',
        'YourPage.vue',
      ];
    }
    return ['CustomTabContent.vue', 'use-side-render-handlers.ts', 'YourPage.vue'];
  });
</script>

<style scoped>
  .side-render-code-section {
    padding: 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .code-section-header {
    display: flex;
    flex-wrap: wrap;
    gap: 12px 16px;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .code-title {
    margin-bottom: 4px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .code-desc {
    margin: 0;
    font-size: 13px;
    line-height: 20px;
    color: #63656e;

    strong {
      font-weight: 600;
      color: #313238;
    }
  }

  .code-scenario-banner {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 12px;
    align-items: center;
    padding: 10px 12px;
    margin-bottom: 16px;
    background: #f5f7fa;
    border-radius: 4px;
  }

  .code-scenario-banner__badge {
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
    color: #3a84ff;
    background: #e1ecff;
    border-radius: 10px;
  }

  .code-scenario-banner__title {
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .code-scenario-banner__files {
    flex: 1 1 100%;
    font-size: 12px;
    color: #979ba5;

    code {
      margin-right: 6px;
      padding: 1px 6px;
      font-size: 11px;
      color: #3a84ff;
      background: #fff;
      border-radius: 2px;
    }
  }

  .code-block {
    margin-bottom: 16px;

    &:last-child {
      margin-bottom: 0;
    }
  }

  .code-block-title {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: baseline;
    margin-bottom: 4px;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .code-block-file {
    font-size: 11px;
    font-weight: 500;
    color: #979ba5;
  }

  .code-block-desc {
    margin: 0 0 8px;
    font-size: 12px;
    line-height: 18px;
    color: #979ba5;
  }

  .guide-code {
    display: block;
    padding: 12px 16px;
    overflow-x: auto;
    font-size: 12px;
    line-height: 18px;
    color: #313238;
    background: #f5f7fa;
    border-radius: 4px;
  }

  .code-fade-enter-active,
  .code-fade-leave-active {
    transition: opacity 0.15s ease;
  }

  .code-fade-enter-from,
  .code-fade-leave-to {
    opacity: 0;
  }
</style>
