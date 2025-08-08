import { ref, onMounted, onBeforeUnmount, watch, nextTick, computed, type Ref } from 'vue';

import { useTooltip, type TooltipOptions } from './use-tippy';

export interface OverflowItem {
  id: string;
  name: string;
  icon?: string;
  [key: string]: any;
}

export function useOverflowHandler<T extends OverflowItem>(
  containerRef: Ref<HTMLElement | null>,
  items: Ref<T[]>,
  moreButtonRef: Ref<HTMLElement | null> = ref(null),
  options: {
    theme?: string;
    placement?: string;
    trigger?: string;
    interactive?: boolean;
    allowHTML?: boolean;
    arrow?: boolean;
    offset?: [number, number];
    onItemClick?: (item: T) => void;
  } = {}
) {
  const visibleItems = ref<T[]>([]);
  const hiddenItems = ref<T[]>([]);

  const {
    theme = 'ai-blueking-light light',
    placement = 'bottom',
    trigger = 'mouseenter',
    interactive = true,
    allowHTML = true,
    arrow = true,
    offset = [0, 4],
    onItemClick,
  } = options;

  const { createTooltip, destroyAll } = useTooltip({
    theme,
    placement: placement as any,
    trigger,
    interactive,
    allowHTML,
    arrow,
    offset,
  } as TooltipOptions);

  // 生成下拉菜单的HTML内容
  const dropdownContent = computed(() => {
    if (hiddenItems.value.length === 0) return '';

    const itemsHtml = hiddenItems.value
      .map(
        item =>
          `<div class="tippy-menu-item" data-item-id="${item.id}">
        ${item.icon ? `<i class="${item.icon}"></i>` : ''}
        <span>${item.name}</span>
      </div>`
      )
      .join('');

    return `<div class="tippy-dropdown-menu">${itemsHtml}</div>`;
  });

  // 核心计算逻辑
  const calculateVisibleItems = async () => {
    const container = containerRef.value;
    if (!container) return;

    // 1. 临时将所有项都设为可见，以便测量
    visibleItems.value = [...items.value];
    hiddenItems.value = [];

    // 2. 等待 DOM 更新完成
    await nextTick();

    const containerWidth = container.clientWidth;
    const itemNodes = Array.from(container.children) as HTMLElement[];

    // 获取容器的 gap 值
    const computedStyle = window.getComputedStyle(container);
    const gap = parseFloat(computedStyle.gap) || 0;

    // 3. 检查是否需要折叠
    let totalWidth = 0;
    itemNodes.forEach((node, index) => {
      totalWidth += node.getBoundingClientRect().width;
      // 添加 gap（除了最后一个元素）
      if (index < itemNodes.length - 1) {
        totalWidth += gap;
      }
    });

    if (totalWidth <= containerWidth) {
      return;
    }

    // 4. 计算分割点
    const moreButtonWidth = moreButtonRef.value?.offsetWidth || 70;
    const availableWidth = containerWidth - moreButtonWidth;

    let currentWidth = 0;
    let breakIndex = -1;

    for (let i = 0; i < itemNodes.length; i++) {
      const node = itemNodes[i];
      currentWidth += node.getBoundingClientRect().width;
      // 添加 gap（除了最后一个元素）
      if (i < itemNodes.length - 1) {
        currentWidth += gap;
      }
      if (currentWidth > availableWidth) {
        breakIndex = i;
        break;
      }
    }

    if (breakIndex === -1) {
      breakIndex = items.value.length;
    }

    // 5. 重新分配 items
    visibleItems.value = items.value.slice(0, breakIndex);
    hiddenItems.value = items.value.slice(breakIndex);
  };

  // 监听 items 变化
  watch(
    () => items.value,
    () => {
      requestAnimationFrame(calculateVisibleItems);
    },
    { deep: true, immediate: true }
  );

  // 监听 hiddenItems 变化，创建/更新 tooltip
  watch(
    () => hiddenItems.value,
    newHiddenItems => {
      nextTick(() => {
        if (newHiddenItems.length > 0 && moreButtonRef.value) {
          destroyAll();

          createTooltip(moreButtonRef.value, dropdownContent.value, {
            onShow: () => {
              setTimeout(() => {
                const menuItems = document.querySelectorAll('.tippy-menu-item');
                menuItems.forEach(item => {
                  item.addEventListener('click', handleMenuItemClick);
                });
              }, 0);
            },
            onHide: () => {
              const menuItems = document.querySelectorAll('.tippy-menu-item');
              menuItems.forEach(item => {
                item.removeEventListener('click', handleMenuItemClick);
              });
            },
          });
        } else {
          destroyAll();
        }
      });
    },
    { immediate: true }
  );

  // 处理菜单项点击
  const handleMenuItemClick = (event: Event) => {
    const target = event.currentTarget as HTMLElement;
    const itemId = target.dataset.itemId;
    const item = hiddenItems.value.find(i => i.id === itemId);
    if (item && onItemClick) {
      onItemClick(item as T);
    }
  };

  let resizeObserver: ResizeObserver | null = null;
  onMounted(() => {
    if (containerRef.value) {
      resizeObserver = new ResizeObserver(() => {
        requestAnimationFrame(calculateVisibleItems);
      });
      resizeObserver.observe(containerRef.value);
    }
  });

  onBeforeUnmount(() => {
    if (resizeObserver && containerRef.value) {
      resizeObserver.unobserve(containerRef.value);
    }
    destroyAll();
  });

  return {
    visibleItems,
    hiddenItems,
    calculateVisibleItems,
  };
}
