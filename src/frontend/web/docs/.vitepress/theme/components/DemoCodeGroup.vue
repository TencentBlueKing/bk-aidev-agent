<template>
  <!--
    DOM 与 VitePress ::: code-group 一致，复用 vp-code-group.css 与全局 Tab 切换逻辑（composables/codeGroups）。
  -->
  <div class="demo-code-group-root vp-code-group vp-adaptive-theme">
    <div class="tabs">
      <input
        :id="tabIds[0]"
        type="radio"
        :name="groupName"
        checked
      >
      <label
        :for="tabIds[0]"
        :data-title="firstLabel"
      >{{ firstLabel }}</label>
      <input
        :id="tabIds[1]"
        type="radio"
        :name="groupName"
      >
      <label
        :for="tabIds[1]"
        :data-title="secondLabel"
      >{{ secondLabel }}</label>
    </div>
    <div class="blocks">
      <div class="vp-block active">
        <slot />
      </div>
      <div class="language-vue vp-adaptive-theme demo-code-group__second-block">
        <slot name="second" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  const props = withDefaults(
    defineProps<{
      firstLabel?: string
      secondLabel?: string
      /** 同一页多个分组时传入，避免 radio name 冲突 */
      groupSuffix?: string
    }>(),
    {
      firstLabel: "在线演示",
      secondLabel: "源码",
      groupSuffix: "",
    },
  )

  const safeSuffix = props.groupSuffix.replace(/[^a-zA-Z0-9_-]/g, "") || "x"
  const uid = `${Math.random().toString(36).slice(2, 10)}-${safeSuffix}`
  const groupName = `demo-cg-${uid}`
  const tabIds = [`tab-${uid}-0`, `tab-${uid}-1`] as const
</script>

<style scoped>
  .demo-code-group__second-block {
    position: relative;
    margin: 0 !important;
    padding: 0 !important;
  }

  /* 内边距交给 .vp-doc [class*='language-'] pre/code，避免压过 Shiki 行内布局 */
  .demo-code-group__second-block :deep(pre.shiki) {
    margin: 0;
    border-radius: 0 0 8px 8px;
    max-height: min(560px, 70vh);
    overflow: auto;
  }
</style>
