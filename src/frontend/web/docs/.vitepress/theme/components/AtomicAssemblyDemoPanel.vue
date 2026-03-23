<template>
  <DemoCodeGroup
    first-label="在线演示"
    second-label="源码 (Vue)"
    group-suffix="atomic"
  >
    <AtomicAssemblyDemo />
    <template #second>
      <div class="atomic-demo-source-toolbar">
        <span class="atomic-demo-source-file">AtomicAssemblyDemo.vue</span>
        <button
          type="button"
          class="atomic-demo-source-copy"
          @click="copySource"
        >
          复制源码
        </button>
      </div>
      <div
        v-if="highlightError"
        class="atomic-demo-source-fallback"
      >
        <pre><code>{{ source }}</code></pre>
      </div>
      <div
        v-else-if="!highlightedHtml"
        class="atomic-demo-source-loading"
      >
        正在加载语法高亮…
      </div>
      <div
        v-else
        class="atomic-demo-source-shiki"
        v-html="highlightedHtml"
      />
    </template>
  </DemoCodeGroup>
</template>

<script setup lang="ts">
  import { onMounted, ref } from "vue"
  import { Message as BkMessage } from "bkui-vue"

  import DemoCodeGroup from "./DemoCodeGroup.vue"
  import AtomicAssemblyDemo from "./AtomicAssemblyDemo.vue"
  import source from "./AtomicAssemblyDemo.vue?raw"
  import { highlightVueSfc } from "../utils/shiki-vue-highlight"

  const highlightedHtml = ref("")
  const highlightError = ref(false)

  onMounted(() => {
    void highlightVueSfc(source)
      .then((html) => {
        highlightedHtml.value = html
      })
      .catch((e) => {
        console.error("[AtomicAssemblyDemoPanel] shiki highlight failed", e)
        highlightError.value = true
      })
  })

  const copySource = async () => {
    try {
      await navigator.clipboard.writeText(source)
      BkMessage({ theme: "success", message: "已复制到剪贴板" })
    } catch {
      BkMessage({ theme: "warning", message: "复制失败，请切换到「源码」页签后手动选择复制" })
    }
  }
</script>

<style scoped>
  .atomic-demo-source-toolbar {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 8px;
    padding: 10px 16px;
    background: var(--vp-code-tab-bg);
    border-bottom: 1px solid var(--vp-code-tab-divider);
  }

  .atomic-demo-source-file {
    font-size: 12px;
    font-family: var(--vp-font-family-mono);
    color: var(--vp-c-text-2);
  }

  .atomic-demo-source-copy {
    padding: 4px 12px;
    font-size: 12px;
    border-radius: 6px;
    border: 1px solid var(--vp-c-divider);
    background: var(--vp-c-bg);
    color: var(--vp-c-text-1);
    cursor: pointer;
  }

  .atomic-demo-source-copy:hover {
    border-color: var(--vp-c-brand-1);
    color: var(--vp-c-brand-1);
  }

  .atomic-demo-source-loading {
    padding: 24px 20px;
    font-size: 13px;
    color: var(--vp-c-text-2);
  }

  .atomic-demo-source-fallback {
    padding: 16px 20px;
    max-height: min(560px, 70vh);
    overflow: auto;
  }

  .atomic-demo-source-fallback pre {
    margin: 0;
    font-size: 12px;
    line-height: 1.55;
  }

  .atomic-demo-source-shiki :deep(pre.shiki) {
    max-height: min(560px, 70vh);
  }
</style>
