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
          v-for="(btn, index) in shortcutButtons"
          class="shortcut-btn"
          :key="index"
          @click="handleShortcutClick(btn)"
        >
          <i
            v-if="btn.icon"
            class="bkai-icon"
            :class="btn.icon"
          ></i>
          <span class="btn-text ai-blueking-tag-text">{{ btn.label }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script lang="ts" setup>
  import { type ShortCut } from '@blueking/ai-ui-sdk';

  import avatar from '../assets/images/avatar.png';
  import { usePopup } from '../composables/use-popup-props';
  import { useSelect } from '../composables/use-select-pop';
  import { DEFAULT_SHORTCUTS } from '../config';
  import { t } from '../lang';

  interface IProps {
    shortcuts: ShortCut[];
  }

  const props = defineProps<IProps>();

  const { enablePopup } = usePopup();
  const { isIconVisible, iconPosition, popupRef, clearSelection } = useSelect(enablePopup);

  // 定义快捷按钮数据
  const shortcutButtons = props.shortcuts || DEFAULT_SHORTCUTS;

  const emit = defineEmits(['click', 'shortcut-click']);

  const handleClick = () => {
    emit('click');
    isIconVisible.value = false;
  };

  const handleShortcutClick = (shortcut: ShortCut) => {
    try {
      emit('shortcut-click', shortcut);
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
</style>
