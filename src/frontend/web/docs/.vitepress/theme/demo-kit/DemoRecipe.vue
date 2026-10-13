<template>
  <section
    :id="`recipe-${id}`"
    class="demo-recipe"
    @focusin.capture="runtime.markActive(id)"
    @pointerdown.capture="runtime.markActive(id)"
  >
    <header class="demo-recipe__head">
      <div class="demo-recipe__text">
        <div class="demo-recipe__kicker">
          {{ kicker }}<span
            v-if="instanceLabel"
            class="demo-recipe__instance"
          >{{ instanceLabel }}</span>
        </div>
        <div class="demo-recipe__title">{{ title }}</div>
        <div class="demo-recipe__when">{{ when }}</div>
      </div>
      <DemoStatusBar
        v-if="instance !== 'none'"
        :instance-id="runtime.instanceIdOf(id)"
        :kind="instance"
      />
    </header>
    <div class="demo-recipe__stage">
      <slot />
    </div>
    <DemoInspector
      :changed-lines="changedLines"
      :file="file"
      :lang="lang"
      :recipe-id="id"
      :source="source"
    />
  </section>
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount } from 'vue';

  import DemoInspector from './DemoInspector.vue';
  import DemoStatusBar from './DemoStatusBar.vue';
  import type { FloatingConfig, InstanceKind } from './types';
  import { useDemoRuntime } from './use-demo-runtime';

  interface DemoRecipeProps {
    /** 页面内唯一，用于归档事件与请求 */
    id: string;
    kicker: string;
    title: string;
    /** 适用场景一句话 */
    when: string;
    /** 片段源码（?raw 或生成的源码），与实际执行的代码相同 */
    source: string;
    /** 展示用文件名 */
    file: string;
    lang?: 'typescript' | 'vue';
    /** 需要高亮为「已变化」的行（0 基） */
    changedLines?: number[];
    instance?: InstanceKind;
    /** 浮窗配方的专属配置；不传则使用页面默认配置 */
    floatingConfig?: FloatingConfig;
  }

  const props = withDefaults(defineProps<DemoRecipeProps>(), {
    lang: 'typescript',
    changedLines: () => [],
    instance: 'floating',
    floatingConfig: undefined,
  });
  const runtime = useDemoRuntime();

  const instanceLabel = computed(() => {
    if (props.instance === 'embedded') return '舞台内实例';
    if (props.instance === 'floating') return props.floatingConfig ? '自带配置 · 改动后重新挂载' : '默认配置';
    return '';
  });

  // 在 setup 中同步注册，保证子组件（检查器）渲染前记录已就绪
  runtime.register(props.id, { instance: props.instance, floatingConfig: props.floatingConfig });
  onBeforeUnmount(() => runtime.unregister(props.id));
</script>
