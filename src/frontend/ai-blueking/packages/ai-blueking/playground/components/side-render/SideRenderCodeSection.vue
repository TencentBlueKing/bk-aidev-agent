<template>
  <section
    class="side-render-code-section"
    :class="{ 'is-embedded': embedded }"
  >
    <header class="code-section-header">
      <h3 class="code-title">接入代码</h3>
      <p class="code-desc">按阅读顺序复制到业务项目，与左侧 Demo 场景一致。</p>
    </header>

    <div class="code-scenario-banner">
      <span class="code-scenario-banner__badge">{{ activeScenarioMeta.badge }}</span>
      <span class="code-scenario-banner__title">{{ activeScenarioMeta.title }}</span>
      <span class="code-scenario-banner__files">
        阅读顺序：
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
        <article
          v-for="block in codeBlocks"
          :key="block.title"
          class="code-block"
        >
          <header class="code-block-header">
            <h4 class="code-block-title">{{ block.title }}</h4>
            <span
              v-if="block.fileHint"
              class="code-block-file"
            >
              {{ block.fileHint }}
            </span>
          </header>
          <p
            v-if="block.desc"
            class="code-block-desc"
          >
            {{ block.desc }}
          </p>
          <pre class="guide-code"><code>{{ block.code }}</code></pre>
        </article>
      </div>
    </Transition>
  </section>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  import { getSideRenderCodeBlocks } from './side-render-code-examples';
  import { getSideRenderScenarioById, type SideRenderScenarioId } from './side-render-scenarios';

  const props = withDefaults(
    defineProps<{
      activeScenario: SideRenderScenarioId;
      /** 嵌入右栏文档流时减轻外层卡片样式 */
      embedded?: boolean;
    }>(),
    {
      embedded: false,
    },
  );

  const activeScenarioMeta = computed(() => getSideRenderScenarioById(props.activeScenario));

  const codeBlocks = computed(() => getSideRenderCodeBlocks(props.activeScenario));

  const recommendedFiles = computed(() => {
    if (props.activeScenario === 'custom-fetch') {
      return [
        'YourPage.vue',
        'AIBlueking.vue（可选）',
        'use-side-render-custom-tab-change.ts',
        'use-side-render-handlers.ts',
        'CustomTabContent.vue',
      ];
    }
    return ['YourPage.vue', 'AIBlueking.vue（可选）', 'use-side-render-handlers.ts', 'CustomTabContent.vue'];
  });
</script>

<style scoped>
  .side-render-code-section {
    padding: 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .side-render-code-section.is-embedded {
    padding: 16px;
    margin: 0;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .code-section-header {
    margin-bottom: 12px;
  }

  .code-title {
    margin: 0 0 4px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .code-desc {
    margin: 0;
    font-size: 12px;
    line-height: 20px;
    color: #979ba5;
  }

  .code-scenario-banner {
    display: flex;
    flex-wrap: wrap;
    gap: 8px 12px;
    align-items: center;
    padding: 10px 12px;
    margin-bottom: 14px;
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
    line-height: 20px;
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

  .code-blocks {
    display: flex;
    flex-direction: column;
    gap: 20px;
  }

  .code-block {
    padding-top: 4px;
    border-top: 1px solid #f0f1f5;

    &:first-child {
      padding-top: 0;
      border-top: none;
    }
  }

  .code-block-header {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: baseline;
    margin-bottom: 4px;
  }

  .code-block-title {
    margin: 0;
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
    padding: 12px 14px;
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
