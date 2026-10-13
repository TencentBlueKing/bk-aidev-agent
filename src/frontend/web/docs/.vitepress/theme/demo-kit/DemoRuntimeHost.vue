<template>
  <div
    v-if="component && runtime.hasFloating.value"
    class="demo-runtime-host"
    @focusin.capture="runtime.markActive(state.floatingOwner)"
    @pointerdown.capture="runtime.markActive(state.floatingOwner)"
  >
    <component
      :is="component"
      :key="`${state.instanceKey}-${state.floatingKey}`"
      ref="aiRef"
      :default-height="panelBox.height"
      :default-left="panelBox.left"
      :default-top="panelBox.top"
      :default-width="PANEL_WIDTH"
      :enable-popup="false"
      :request-options="floatingRequestOptions"
      :url="runtime.apiUrl.value"
      v-bind="state.floatingProps"
      @close="emitEvent('close')"
      @new-chat-created="(session: unknown) => emitEvent('new-chat-created', session)"
      @receive-end="emitEvent('receive-end')"
      @receive-start="emitEvent('receive-start')"
      @rename="(newName: string) => emitEvent('rename', newName)"
      @sdk-error="(payload: unknown) => emitEvent('sdk-error', payload)"
      @send-message="(message: string) => emitEvent('send-message', message)"
      @session-initialized="emitEvent('session-initialized')"
      @shortcut-click="(data: unknown) => emitEvent('shortcut-click', data)"
      @show="emitEvent('show')"
      @stop="emitEvent('stop')"
    >
      <template
        v-for="(render, name) in state.floatingSlots"
        :key="name"
        #[name]="scope"
      >
        <DemoSlotRender
          :render="render"
          :scope="scope"
        />
      </template>
    </component>
  </div>
</template>

<script setup lang="ts">
  import { markRaw, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch, watchEffect, type Component } from 'vue';
  import type { AIBluekingExpose } from '@blueking/ai-blueking';

  import type { FloatingSlotRender } from './types';
  import { FLOATING_INSTANCE, PANEL_WIDTH, useDemoRuntime, type DemoComponentEvent } from './use-demo-runtime';

  /** 把配方提供的插槽渲染函数挂到 AIBlueking 的动态插槽上 */
  const DemoSlotRender = (props: { render: FloatingSlotRender; scope?: Record<string, unknown> }) =>
    props.render(props.scope ?? {});
  DemoSlotRender.props = ['render', 'scope'];

  /** 面板打开时正文让位用的 class，样式见 demo-kit.css */
  const PANEL_OPEN_CLASS = 'demo-panel-open';
  const PANEL_LEFT_CLASS = 'demo-panel-left';
  const NAV_HEIGHT = 64;
  const GAP = 12;

  const runtime = useDemoRuntime();
  const { state } = runtime;
  const floatingRequestOptions = runtime.requestOptionsFor(FLOATING_INSTANCE);
  const component = shallowRef<Component>();
  const aiRef = ref<AIBluekingExpose | null>(null);
  const panelBox = reactive({ left: 0, top: NAV_HEIGHT + GAP, height: 640 });

  const emitEvent = (name: DemoComponentEvent, payload?: unknown) =>
    runtime.handleComponentEvent(FLOATING_INSTANCE, name, payload);

  const measurePanel = () => {
    panelBox.left = Math.max(GAP, window.innerWidth - state.floatingWidth - GAP);
    panelBox.top = NAV_HEIGHT + GAP;
    panelBox.height = Math.max(420, window.innerHeight - panelBox.top - GAP);
  };

  const activate = async () => {
    if (component.value) return;
    try {
      const [mod] = await Promise.all([import('@blueking/ai-blueking'), runtime.ensureComponentStyles()]);
      component.value = markRaw(mod.default);
    } catch (e) {
      runtime.logEvent('error', `小鲸组件加载失败，请刷新页面重试：${e instanceof Error ? e.message : String(e)}`);
    }
  };

  const clearPageClasses = () => {
    document.documentElement.classList.remove(PANEL_OPEN_CLASS, PANEL_LEFT_CLASS);
  };

  watch(aiRef, expose => runtime.attach(FLOATING_INSTANCE, expose ?? undefined));

  onMounted(() => {
    watch(
      () => runtime.hasFloating.value,
      on => {
        if (on) {
          measurePanel();
          void activate();
        } else {
          runtime.attach(FLOATING_INSTANCE, undefined);
          clearPageClasses();
        }
      },
      { immediate: true },
    );
    // 重新挂载时按当前宽度重新计算默认位置
    watch(() => state.floatingKey, measurePanel);
    watchEffect(() => {
      const open = runtime.instanceState(FLOATING_INSTANCE).panelOpen;
      const root = document.documentElement;
      root.classList.toggle(PANEL_OPEN_CLASS, open);
      root.classList.toggle(PANEL_LEFT_CLASS, open && state.floatingDock === 'left');
      root.style.setProperty('--demo-panel-width', `${state.floatingWidth}px`);
      root.style.setProperty('--demo-panel-left-inset', `${state.floatingLeft + state.floatingWidth + 24}px`);
    });
  });

  onBeforeUnmount(clearPageClasses);
</script>
