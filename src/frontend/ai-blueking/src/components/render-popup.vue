<template>
  <div
    v-if="isIconVisible"
    ref="popupRef"
    :style="iconPosition"
    class="ai-blueking-render-popup"
    @mousedown.prevent
  >
    <div class="popup-content">
      <!-- AI图标按钮 -->
      <div
        v-if="!props.hideDefaultTrigger"
        class="popup-bkai-btn"
        @click="handleClick"
      >
        <img
          class="avatar"
          :src="avatar"
          alt="AI"
        />
        <span>{{ t('问问小鲸') }}</span>
      </div>

      <!-- 快捷按钮组 -->
      <div class="shortcut-buttons">
        <div
          v-for="(btn, index) in visibleShortcuts"
          :key="index"
          class="shortcut-btn"
          @click="handleShortcutClick(btn)"
        >
          <component
            :is="btn.iconRender ? btn.iconRender(h) : null"
            v-if="btn.iconRender"
          />
          <i
            v-else-if="btn.icon"
            :class="btn.icon"
          ></i>
          <span class="btn-text ai-blueking-tag-text">{{ btn.alias ?? btn.name }}</span>
        </div>
        <!-- 更多按钮 -->
        <div
          v-if="hiddenShortcuts.length > 0"
          class="shortcut-btn more-btn"
          @mouseenter="handleMoreEnter"
          @mouseleave="handleMoreLeave"
        >
          <span class="btn-text">更多</span>
          <i class="bkai-icon bkai-angle-down"></i>
          <!-- 更多菜单 -->
          <div
            v-if="showMoreMenu"
            class="more-menu"
            @mouseenter="handleMenuEnter"
            @mouseleave="handleMenuLeave"
          >
            <div
              v-for="(btn, index) in hiddenShortcuts"
              :key="index"
              class="more-menu-item"
              @click="handleShortcutClick(btn)"
            >
              <component
                :is="btn.iconRender ? btn.iconRender(h) : null"
                v-if="btn.iconRender"
              />
              <i
                v-else-if="btn.icon"
                :class="btn.icon"
              ></i>
              <span>{{ btn.alias ?? btn.name }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import type { IAgentInfo } from '@blueking/ai-ui-sdk/types';
  import { computed, h, ref, toRaw } from 'vue';

  import avatar from '../assets/images/avatar.png';
  import { usePopup } from '../composables/use-popup-props';
  import { useSelect } from '../composables/use-select-pop';
  import { t } from '../lang';
  import { type IShortcut } from '../types';

  interface IProps {
    shortcuts?: IShortcut[];
    conversationSettings?: IAgentInfo['conversationSettings'];
    shortcutLimit?: number;
    shortcutFilter?: (shortcut: IShortcut, selectedText: string) => boolean;
    hideDefaultTrigger?: boolean;
  }

  const props = withDefaults(defineProps<IProps>(), {
    shortcuts: () => [],
    shortcutLimit: 3,
    hideDefaultTrigger: false,
  });

  const { enablePopup } = usePopup();
  const { isIconVisible, iconPosition, popupRef, clearSelection, selectedText } =
    useSelect(enablePopup);

  // 定义快捷按钮数据
  const allShortcuts = computed<IShortcut[]>(() => {
    const shortcuts =
      props.shortcuts.length > 0
        ? props.shortcuts
        : (props.conversationSettings?.commands as IShortcut[]) || [];
    // 如果提供了过滤函数，则应用过滤
    if (typeof props.shortcutFilter === 'function') {
      return shortcuts.filter(item => !!props.shortcutFilter?.(toRaw(item), selectedText.value));
    }
    return shortcuts.filter(item => item.enableFillBack ?? true);
  });

  // 可见的快捷按钮
  const visibleShortcuts = computed(() => allShortcuts.value.slice(0, props.shortcutLimit));

  // 隐藏的快捷按钮
  const hiddenShortcuts = computed(() => allShortcuts.value.slice(props.shortcutLimit));

  // 控制更多菜单的显示
  const showMoreMenu = ref(false);
  let menuLeaveTimer: number | null = null;
  let moreLeaveTimer: number | null = null;

  const emit = defineEmits(['click', 'shortcut-click']);

  const handleClick = () => {
    emit('click');
    isIconVisible.value = false;
  };

  // 处理更多按钮的鼠标进入事件
  const handleMoreEnter = () => {
    if (moreLeaveTimer) {
      clearTimeout(moreLeaveTimer);
      moreLeaveTimer = null;
    }
    showMoreMenu.value = true;
  };

  // 处理更多按钮的鼠标离开事件
  const handleMoreLeave = () => {
    if (moreLeaveTimer) {
      window.clearTimeout(moreLeaveTimer);
      moreLeaveTimer = null;
    }
    moreLeaveTimer = window.setTimeout(() => {
      if (!menuLeaveTimer) {
        showMoreMenu.value = false;
      }
    }, 100);
  };

  // 处理菜单的鼠标进入事件
  const handleMenuEnter = () => {
    if (menuLeaveTimer) {
      clearTimeout(menuLeaveTimer);
      menuLeaveTimer = null;
    }
  };

  // 处理菜单的鼠标离开事件
  const handleMenuLeave = () => {
    if (menuLeaveTimer) {
      window.clearTimeout(menuLeaveTimer);
      menuLeaveTimer = null;
    }
    menuLeaveTimer = window.setTimeout(() => {
      showMoreMenu.value = false;
    }, 100);
  };

  const handleShortcutClick = (shortcut: IShortcut) => {
    try {
      emit('shortcut-click', {
        shortcut,
        source: 'popup',
      });
      clearSelection();
      isIconVisible.value = false;
    } catch (error) {
      console.error('处理快捷按钮点击事件时出错:', error);
    }
  };
</script>

<style lang="scss" scoped>
  .ai-blueking-render-popup {
    position: absolute;
    z-index: 10001;
    box-sizing: border-box;
    display: flex;
    align-items: center;
    height: 32px;
    padding: 6px 12px;
    pointer-events: auto;
    background: #fff;
    border-radius: 16px;
    box-shadow:
      0 2px 10px 0 #0000001a,
      0 0 4px 0 #1919291a;
  }

  .popup-content {
    display: flex;
    gap: 4px;
    align-items: center;
    pointer-events: auto;
  }

  .popup-bkai-btn {
    display: flex;
    flex-shrink: 0;
    gap: 4px;
    align-items: center;
    justify-content: center;
    width: 80px;
    height: 28px;
    padding: 0 6px;
    font-size: 12px;
    color: #313238;
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.2s ease;

    img {
      width: 16px;
      height: 16px;
    }

    &:hover {
      background: #f0f1f5;
    }

    i {
      font-size: 14px;
      transform: translate(1px, 0px);
    }
  }

  .shortcut-buttons {
    display: flex;
    gap: 4px;
    pointer-events: auto;
  }

  .shortcut-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    height: 28px;
    padding: 0 6px;
    font-size: 12px;
    font-weight: 400;
    color: #313238;
    white-space: nowrap;
    pointer-events: auto;
    cursor: pointer;
    user-select: none;
    background: #fff;
    border-radius: 4px;
    transition: all 0.2s ease;
    position: relative;

    .bkai-icon {
      color: #979ba5;
    }

    i {
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
    }

    .btn-text {
      font-weight: 400;
      line-height: 1;
    }

    &:hover {
      background: #f0f1f5;
    }
  }

  .more-btn {
    position: relative;

    .bkai-angle-down {
      transition: transform 0.2s ease-in-out;
      color: #979ba5;
    }

    &:hover {
      .bkai-angle-down {
        transform: rotate(180deg);
      }
    }
  }

  .more-menu {
    position: absolute;
    top: 100%;
    right: 0;
    z-index: 10002;
    min-width: 120px;
    padding: 4px;
    margin-top: 4px;
    background: #fff;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
    overflow: hidden;
  }

  .more-menu-item {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    font-size: 12px;
    color: #313238;
    cursor: pointer;
    white-space: nowrap;
    border-radius: 2px;
    transition: all 0.2s ease;

    &:hover {
      color: #3a84ff;
      background: #e1ecff;
    }

    i {
      font-size: 12px;
      color: #979ba5;
    }
  }
</style>
