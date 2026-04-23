<template>
  <Teleport to="body">
    <transition name="ai-fade">
      <div
        v-if="visible"
        ref="popoverRef"
        class="ai-selection-popover"
        :style="{
          left: `${position.x}px`,
          top: `${position.y}px`,
          zIndex: SELECTION_Z_INDEX,
          '--selection-z-index': SELECTION_Z_INDEX,
        }"
        @mousedown.stop
      >
        <div class="ai-selection-popover-content">
          <slot :shortcuts="shortcuts">
            <template
              v-for="(shortcut, index) in shortcuts.slice(0, maxShortcutCount)"
              :key="shortcut.id"
            >
              <ShortcutBtn
                v-if="index < maxShortcutCount"
                :shortcut="shortcut"
                @click="handleSelectShortcut(shortcut)"
              />
            </template>
            <template v-if="shortcuts.length > maxShortcutCount">
              <div
                class="ai-divider"
                style="margin: 0 4px"
              />
              <Tippy
                ref="moreMenuRef"
                :arrow="false"
                interactive
                :offset="[0, 6]"
                theme="ai-chat-box-light light"
                trigger="manual"
                @hidden="
                  () => {
                    moreMenuVisible = false;
                  }
                "
                @show="
                  () => {
                    moreMenuVisible = true;
                  }
                "
              >
                <ShortcutBtn
                  style="width: 28px"
                  @click="handleShowMoreMenu"
                >
                  <CollapsedIcon class="shortcut-btn-more-icon" />
                </ShortcutBtn>

                <template #content>
                  <div
                    v-if="moreMenuVisible"
                    class="shortcut-menu"
                  >
                    <ShortcutBtn
                      v-for="shortcut in shortcuts.slice(maxShortcutCount)"
                      :key="shortcut.id"
                      mode="menu"
                      :shortcut="shortcut"
                      @click="handleSelectShortcut(shortcut)"
                    />
                  </div>
                </template>
              </Tippy>
            </template>
          </slot>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<script setup lang="ts">
  import { nextTick, onMounted, onUnmounted, shallowRef, useTemplateRef } from 'vue';

  import { Tippy, useTippy } from 'vue-tippy';

  import { DEFAULT_SHORTCUTS, SELECTION_Z_INDEX } from '../../common';
  import { CollapsedIcon } from '../../icons/messages';
  import ShortcutBtn from '../ai-shortcut/shortcut-btn/shortcut-btn.vue';

  import type { Shortcut } from '../../types';

  import 'tippy.js/dist/tippy.css';

  const props = withDefaults(
    defineProps<{
      excludeSelectors?: string[]; // 排除的选择器数组，选区在这些选择器内部时不显示弹窗
      maxShortcutCount?: number; // 最多显示的快捷指令数量 默认3
      offset?: number; // 垂直间距
      shortcuts?: Shortcut[]; // 快捷指令 默认使用 问问小鲸
    }>(),
    {
      offset: 10,
      shortcuts: () => DEFAULT_SHORTCUTS,
      maxShortcutCount: 3,
      excludeSelectors: () => [],
    },
  );

  const visible = defineModel<boolean>('visible', { required: true });

  const emits = defineEmits<{
    (e: 'selectShortcut', shortcut: Shortcut, text: string): void;
    (e: 'selectionChange', text: string): void;
  }>();

  const popoverRef = useTemplateRef<HTMLElement>('popoverRef');
  const moreMenuRef = useTemplateRef<InstanceType<typeof Tippy> & ReturnType<typeof useTippy>>('moreMenuRef');

  const position = shallowRef({ x: 0, y: 0 });
  const selectedText = shallowRef('');
  const selectedSelection = shallowRef<null | Selection>(null);
  const moreMenuVisible = shallowRef(false);

  /**
   * 递归查找 Shadow DOM 中的选区
   */
  const getSelectionInShadowDOM = (element: Element | null): Selection | undefined => {
    if (element?.shadowRoot instanceof ShadowRoot) {
      try {
        const shadowRootWithSelection = element.shadowRoot as ShadowRoot & { getSelection?: () => null | Selection };
        if (typeof shadowRootWithSelection.getSelection === 'function') {
          const shadowSelection = shadowRootWithSelection.getSelection();
          if (shadowSelection && !shadowSelection.isCollapsed && shadowSelection.toString().trim()) {
            return shadowSelection;
          }
        }
      } catch {
        closePopover();
        return;
      }
      // 递归查找 ShadowRoot 内的嵌套 Shadow DOM
      try {
        const walker = document.createTreeWalker(element.shadowRoot, NodeFilter.SHOW_ELEMENT, null);
        let node: Node | null = walker.nextNode();
        while (node) {
          if (node instanceof Element) {
            const nestedSelection = getSelectionInShadowDOM(node);
            if (nestedSelection) return nestedSelection;
          }
          node = walker.nextNode();
        }
      } catch {
        closePopover();
      }
    }
  };

  const selectionChange = async () => {
    selectedSelection.value = window.getSelection();
    // 如果文档选区无效，尝试从 Shadow DOM 中查找
    if (!selectedSelection.value) {
      const activeEl = document.activeElement;
      if (activeEl) {
        const shadowSelection = getSelectionInShadowDOM(activeEl);
        if (shadowSelection) {
          selectedSelection.value = shadowSelection;
        }
      }
    }
    const text = selectedSelection.value?.toString()?.trim();
    if (!text) {
      closePopover();
      return;
    }

    // 检查选区是否在需要排除的容器内
    // 如果传入了 excludeSelectors，且选区在这些选择器内部，则不显示划词选择弹窗
    if (props.excludeSelectors.length > 0 && selectedSelection.value?.rangeCount) {
      try {
        const range = selectedSelection.value.getRangeAt(0);
        const container = range.commonAncestorContainer;
        let node: Node | null = container.nodeType === Node.TEXT_NODE ? container.parentNode : container;
        while (node && node !== document.body) {
          if (node instanceof Element) {
            // 检查是否在任何一个排除选择器内部
            for (const selector of props.excludeSelectors) {
              const matchedElement = node.closest(selector);
              if (matchedElement) {
                // 选区在排除区域内，不显示弹窗
                closePopover();
                return;
              }
            }
          }
          node = node.parentNode;
        }
      } catch {
        // 忽略错误，继续执行
      }
    }

    if (text !== selectedText.value) {
      emits('selectionChange', text);
    }
    selectedText.value = text;
    // 获取选区坐标 (Rect)
    // 注意：getBoundingClientRect() 返回的是相对于视口的坐标
    // 无论是普通 DOM 还是 Shadow DOM，都统一返回视口坐标
    let rect: DOMRect | null = null;
    try {
      if (selectedSelection.value?.rangeCount) {
        const range = selectedSelection.value?.getRangeAt(0);
        const clientRects = range?.getClientRects();
        if (clientRects.length > 0) {
          rect = range.getBoundingClientRect();
        }
      }
    } catch {
      closePopover();
      return;
    }

    // 特殊情况：Input / Textarea
    // 原生 Range 在 Input/Textarea 中通常无法获取准确坐标
    // 降级策略：使用输入框整体坐标
    const activeEl = document.activeElement;
    if (!rect || (rect.width === 0 && rect.height === 0)) {
      const isInput = activeEl instanceof HTMLInputElement || activeEl instanceof HTMLTextAreaElement;
      if (isInput) {
        rect = activeEl.getBoundingClientRect();
      } else {
        // 无法获取有效坐标，不显示
        closePopover();
        return;
      }
    }
    // 计算弹窗位置
    visible.value = true;
    await nextTick();
    const popoverRect = popoverRef.value!.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    const padding = 8; // 距离视口边缘的最小距离
    // 计算水平位置（尽量居中）
    const selectionCenterX = rect.left + rect.width / 2;
    let left = selectionCenterX - popoverRect.width / 2;

    // // 水平边界处理：确保弹窗不超出视口，尽量保持居中
    if (left < padding) {
      // 左边界超出，贴左边
      left = padding;
    } else if (left + popoverRect.width > viewportWidth - padding) {
      // 右边界超出，贴右边
      left = viewportWidth - popoverRect.width - padding;
    }

    // 计算垂直位置（优先上方，空间不足则下方）
    let top: number;
    const spaceAbove = rect.top; // 上方可用空间
    const spaceBelow = viewportHeight - rect.bottom; // 下方可用空间
    const requiredSpace = popoverRect.height + props.offset;

    // 判断上方是否有足够空间
    if (spaceAbove >= requiredSpace) {
      top = rect.top - popoverRect.height - props.offset;
    } else if (spaceBelow >= requiredSpace) {
      top = rect.bottom + props.offset;
    } else {
      if (spaceAbove >= spaceBelow) {
        top = Math.max(padding, rect.top - popoverRect.height - props.offset);
      } else {
        top = Math.min(viewportHeight - popoverRect.height - padding, rect.bottom + props.offset);
      }
    }
    position.value = { x: left, y: top };
  };

  const closePopover = () => {
    if (!visible.value) return;
    selectedSelection.value?.removeAllRanges();
    visible.value = false;
  };

  const handleSelectShortcut = (shortcut: Shortcut) => {
    closePopover();
    emits('selectShortcut', shortcut, selectedText.value);
  };

  // 防抖/延迟处理
  let timer: null | number = null;

  const debounceHandleSelection = (delay: number) => {
    if (timer) clearTimeout(timer);
    timer = window.setTimeout(() => {
      selectionChange();
    }, delay);
  };
  const handleMouseUp = () => {
    // 鼠标松开，立即响应 (20ms 主要是为了等待原生 selection 对象更新)
    // 且能覆盖掉 selectionchange 的延时任务，确保鼠标操作的即时性
    debounceHandleSelection(200);
  };
  const handleSelectionChange = () => {
    debounceHandleSelection(300);
  };
  const handleClickOutside = (e: MouseEvent) => {
    if (visible.value && popoverRef.value?.contains(e.target as HTMLElement)) {
      return;
    }
    closePopover();
  };
  const handleScroll = (e: Event) => {
    if (!selectedSelection.value || !visible.value) return;
    if (e.target instanceof HTMLElement && e.target.contains(selectedSelection.value?.anchorNode as Node)) {
      closePopover();
    }
  };
  const handleShowMoreMenu = () => {
    moreMenuRef.value?.show();
  };

  onMounted(() => {
    document.addEventListener('selectionchange', handleSelectionChange);
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('mousedown', handleClickOutside);
    document.addEventListener('scroll', handleScroll, true);
    window.addEventListener('resize', closePopover);
    window.addEventListener('blur', closePopover);
  });

  onUnmounted(() => {
    document.removeEventListener('selectionchange', handleSelectionChange);
    document.removeEventListener('mouseup', handleMouseUp);
    document.removeEventListener('mousedown', handleClickOutside);
    document.removeEventListener('scroll', handleScroll, true);
    window.removeEventListener('resize', closePopover);
    window.removeEventListener('blur', closePopover);
  });
</script>

<style lang="scss">
  @use '../../styles/menu' as menu;

  .ai-selection-popover {
    position: fixed;
    z-index: var(--selection-z-index);
    height: 32px;
    padding: 0 12px;
    pointer-events: auto;
    user-select: none;
    background: #fff;
    border-radius: 16px;
    box-shadow:
      0 2px 10px 0 #0000001a,
      0 0 4px 0 #1919291a;

    &-content {
      display: flex;
      gap: 4px;
      align-items: center;
      height: 100%;

      .shortcut-btn {
        &-more-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 10px;
          height: 10px;
          font-size: 10px;
          color: #979ba5;
          transform: rotate(90deg);
        }
      }

      .shortcut-menu {
        @include menu.ai-common-menu-style;
      }
    }
  }

  /* 动画 */
  .ai-fade-enter-active,
  .ai-fade-leave-active {
    transition:
      opacity 0.2s ease,
      transform 0.2s ease;
  }

  .ai-fade-enter-from,
  .ai-fade-leave-to {
    opacity: 0;
    transform: translateY(4px);
  }
</style>
