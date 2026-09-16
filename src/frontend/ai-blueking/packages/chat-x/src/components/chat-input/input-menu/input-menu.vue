<template>
  <Tippy
    ref="tippyRef"
    tag="div"
    v-bind="innerTippyProps"
  >
    <slot />
    <template #content>
      <InputMenuPanel
        v-if="visible"
        :flat-items="flatItems"
        :groups="groups"
        @close="emit('close')"
        @select="emit('select', $event)"
        @toggle-group="emit('toggleGroup', $event)"
      />
    </template>
  </Tippy>
</template>
<script setup lang="ts">
  import { computed, useTemplateRef, watch } from 'vue';

  import { type TippyOptions, Tippy } from 'vue-tippy';

  import { EDITOR_MENU_Z_INDEX } from '../../../common';
  import InputMenuPanel from './input-menu-panel.vue';

  import type { AITippyProps, IInputMenuGroup, IInputMenuItem } from '../../../types';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<{
    /** 当前可见且可选中的条目，顺序与面板一致 */
    flatItems: IInputMenuItem[];
    groups: IInputMenuGroup[];
    /** 透传给 tippy 的额外配置（全屏时由上层覆盖 appendTo） */
    tippyOptions?: AITippyProps;
    /** 菜单是否展开；由触发态与是否有条目共同决定 */
    visible: boolean;
  }>();
  const emit = defineEmits<{
    (e: 'select', item: IInputMenuItem): void;
    (e: 'toggleGroup', key: string): void;
    (e: 'close'): void;
  }>();

  const tippyRef = useTemplateRef<{ hide?: () => void; show?: () => void }>('tippyRef');

  type PopperModifier = NonNullable<NonNullable<TippyOptions['popperOptions']>['modifiers']>[number];
  /**
   * 让浮层宽度跟随输入框。
   * 设计稿：菜单与框体等宽、不跟随光标。
   */
  const SAME_WIDTH_MODIFIER: PopperModifier = {
    name: 'sameWidth',
    enabled: true,
    phase: 'beforeWrite',
    requires: ['computeStyles'],
    fn: ({ state }) => {
      state.styles.popper.width = `${state.rects.reference.width}px`;
    },
    effect: ({ state }) => {
      state.elements.popper.style.width = `${state.elements.reference.getBoundingClientRect().width}px`;
    },
  };

  const innerTippyProps = computed(
    () =>
      ({
        appendTo: () => document.body,
        arrow: false,
        duration: 0,
        hideOnClick: false,
        interactive: true,
        maxWidth: 'none',
        offset: [0, 8],
        placement: 'top',
        popperOptions: { modifiers: [SAME_WIDTH_MODIFIER] },
        theme: 'ai-input-menu',
        trigger: 'manual',
        zIndex: EDITOR_MENU_Z_INDEX,
        ...(props.tippyOptions || {}),
        // hideOnClick 为 false 时点输入框不会关菜单；外部点击仍走该钩子（与 mention-tippy 同一套路）
        onClickOutside: () => emit('close'),
      }) as InstanceType<typeof Tippy>['$props'],
  );

  // vue-tippy 的 Tippy 组件没有 visible prop，用手动 trigger + show/hide 对齐 isMenuVisible
  const syncVisible = () => {
    if (props.visible) {
      tippyRef.value?.show?.();
      return;
    }
    tippyRef.value?.hide?.();
  };
  watch(() => props.visible, syncVisible, { flush: 'post', immediate: true });
</script>
<style lang="scss">
  // 浮层容器去默认内边距与背景，边框/圆角/阴影由面板自身绘制
  .tippy-box[data-theme~='ai-input-menu'] {
    background: white;

    .tippy-content {
      padding: 0;
      background: transparent;
    }
  }
</style>
