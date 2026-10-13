<template>
  <div
    class="demo-embed-frame"
    :style="{ height: `${height}px`, gridTemplateColumns: asideWidth > 0 ? `${asideWidth}px 1fr` : '1fr' }"
  >
    <aside
      v-if="asideWidth > 0"
      class="demo-embed-frame__aside"
    >
      <slot name="aside">
        <nav
          class="demo-embed-frame__nav"
          aria-hidden="true"
        >
          <span
            v-for="(item, index) in nav"
            :key="item"
            :class="{ 'is-on': index === 0 }"
          >{{ item }}</span>
        </nav>
      </slot>
    </aside>
    <div class="demo-embed-frame__main">
      <div
        v-if="$slots.toolbar"
        class="demo-embed-frame__toolbar"
      >
        <slot name="toolbar" />
      </div>
      <div class="demo-embed-frame__chat">
        <slot />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  interface DemoEmbedFrameProps {
    /** 左侧菜单项（未提供 aside 插槽时显示，第一项高亮） */
    nav?: string[];
    height?: number;
    /** 左栏宽度；为 0 时不渲染左栏 */
    asideWidth?: number;
  }

  withDefaults(defineProps<DemoEmbedFrameProps>(), { nav: () => [], height: 560, asideWidth: 120 });
</script>

<style scoped>
  .demo-embed-frame {
    display: grid;
    grid-template-rows: minmax(0, 1fr);
    overflow: hidden;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 1px 2px rgb(0 0 0 / 6%);
  }

  .demo-embed-frame__aside {
    min-height: 0;
    overflow: auto;
  }

  .demo-embed-frame__nav {
    display: flex;
    flex-direction: column;
    gap: 2px;
    height: 100%;
    padding: 10px 8px;
    font-size: 12px;
    color: #96a2b9;
    background: #182132;
  }

  .demo-embed-frame__nav span {
    padding: 6px 10px;
    border-radius: 2px;
  }

  .demo-embed-frame__nav .is-on {
    color: #fff;
    background: #3a84ff;
  }

  .demo-embed-frame__main {
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
  }

  .demo-embed-frame__toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    padding: 10px 12px;
    border-bottom: 1px solid #f0f1f5;
  }

  .demo-embed-frame__chat {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }
</style>
