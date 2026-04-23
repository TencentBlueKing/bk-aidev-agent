<template>
  <div
    ref="containerRef"
    class="shortcut-btns"
  >
    <template
      v-for="(shortcut, index) in shortcuts"
      :key="shortcut.key || shortcut.id"
    >
      <ShortcutBtn
        :ref="el => setItemRef(el, index)"
        :class="['shortcut-btns-item', { 'shortcut-btns-item-hidden': !visibleItems.includes(shortcut) }]"
        :shortcut="shortcut"
        @click="handleSelectShortcut(shortcut)"
      />
    </template>
    <Tippy
      v-if="hiddenShortcuts.length > 0"
      ref="moreMenuRef"
      :append-to="getBody"
      :arrow="false"
      interactive
      :offset="[0, 6]"
      theme="ai-chat-box-light light"
      trigger="manual"
      :z-index="SHORTCUT_MENU_Z_INDEX"
      @hidden="
        () => {
          moreMenuVisible = false;
        }
      "
    >
      <ShortcutBtn
        ref="moreBtnRef"
        class="shortcut-btns-item shortcut-btns-more"
        @click="handleToggleMoreMenu"
      >
        <MoreAgentIcon class="shortcut-btns-more-icon" />
        <span>{{ t('更多') }}</span>
      </ShortcutBtn>
      <template #content>
        <div class="shortcut-menu">
          <ShortcutBtn
            v-for="shortcut in hiddenShortcuts"
            :key="shortcut.id"
            mode="menu"
            :shortcut="shortcut"
            @click="handleSelectShortcut(shortcut)"
          />
        </div>
      </template>
    </Tippy>
  </div>
</template>
<script setup lang="ts">
  import type { ComponentPublicInstance } from 'vue';
  import { computed, shallowRef, useTemplateRef, watch } from 'vue';

  import { Tippy, useTippy } from 'vue-tippy';

  import { SHORTCUT_MENU_Z_INDEX } from '../../../common';
  import { useObserverVisibleList } from '../../../composables/use-observer-visible-list';
  import { MoreAgentIcon } from '../../../icons/shortcuts';
  import { t } from '../../../lang/lang';
  import ShortcutBtn from '../shortcut-btn/shortcut-btn.vue';

  import type { Shortcut } from '../../../types';

  import 'tippy.js/dist/tippy.css';
  // 改为惰性获取，避免在 SSR 阶段直接访问 document
  const getBody = () => document.body;
  const props = defineProps<{
    shortcuts: Shortcut[];
  }>();
  const emits = defineEmits<{
    (e: 'selectShortcut', shortcut: Shortcut): void;
  }>();
  const containerRef = useTemplateRef<HTMLElement>('containerRef');
  const itemRefs = shallowRef<(HTMLElement | null)[]>([]);
  const moreMenuRef = useTemplateRef<InstanceType<typeof Tippy> & ReturnType<typeof useTippy>>('moreMenuRef');
  const moreBtnRef = useTemplateRef<InstanceType<typeof ShortcutBtn>>('moreBtnRef');
  const GAP = 4; // 按钮之间的间距
  const menuItems = computed(() => props.shortcuts);
  const { visibleItems } = useObserverVisibleList<Shortcut>(containerRef, itemRefs, {
    items: menuItems,
    gap: GAP,
    moreItemRef: moreBtnRef,
  });

  const hiddenShortcuts = computed(() => props.shortcuts.filter(shortcut => !visibleItems.value.includes(shortcut)));
  const moreMenuVisible = shallowRef(false);

  /**
   * 设置按钮引用
   */
  const setItemRef = (el: ComponentPublicInstance | Element | null, index: number) => {
    if (el && '$el' in el) {
      itemRefs.value[index] = el.$el;
    } else {
      if (el && el instanceof HTMLElement) {
        itemRefs.value[index] = el;
      }
    }
  };

  watch(
    () => props.shortcuts,
    () => {
      itemRefs.value = new Array(props.shortcuts.length).fill(null);
    },
    { deep: true },
  );
  const handleToggleMoreMenu = () => {
    moreMenuVisible.value = !moreMenuVisible.value;
  };
  const handleSelectShortcut = (shortcut: Shortcut) => {
    moreMenuVisible.value = false;
    emits('selectShortcut', shortcut);
  };
  watch(moreMenuVisible, visible => {
    if (visible) {
      moreMenuRef.value?.show();
    } else {
      moreMenuRef.value?.hide();
    }
  });
</script>

<style lang="scss">
  @use '../../../styles/menu' as menu;
  @use '../../../styles/variables.scss' as variables;
  @use '../../../styles/border.scss' as border;

  .shortcut-btns {
    position: relative;
    display: flex;
    gap: 4px;
    align-items: center;
    width: 100%;
    min-width: variables.$chat-input-min-width;
    max-width: variables.$chat-input-max-width;
    overflow: hidden;
    font-size: 12px;
    color: #4d4f56;

    &-item {
      position: relative;
      display: flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: center;
      height: 24px;
      padding: 0 6px;
      white-space: nowrap;
      background: #fff;
      border-radius: 4px;

      &:hover {
        cursor: pointer;
        background: #f0f1f5;
      }

      &-hidden {
        position: absolute;
        visibility: hidden;
        pointer-events: none;
        opacity: 0;
      }
    }

    &-more {
      flex-shrink: 0;

      // width: 32px;
      padding: 0 6px;
      font-size: 12px;

      &-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 14px;
        color: #979ba5;
        transform: rotate(90deg);
      }
    }
  }

  .shortcut-menu {
    @include menu.ai-common-menu-style;
  }
</style>
