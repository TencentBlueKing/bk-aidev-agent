<template>
  <div
    ref="headerRef"
    class="header drag-handle"
    :class="{ draggable: props.draggable }"
  >
    <div class="left-section">
      <div class="logo">
        <img
          :src="logo"
          alt="logo"
        />
      </div>
      <div
        class="title"
        :class="{ 'title-with-tooltip': showRenameTooltip }"
      >
        {{ displayTitle }}

        <!-- 重命名 tooltip 直接绑定在 title 上 -->
        <div
          v-if="showRenameTooltip"
          class="rename-tooltip"
        >
          <div class="rename-content">
            <bk-input
              ref="renameInputRef"
              v-model="renameInputValue"
              class="rename-input"
              :placeholder="t('请输入新的会话名称')"
              @keyup="handleRenameKeyup"
            />
            <div class="rename-buttons">
              <i
                class="bkai-icon bkai-check-1 rename-btn confirm-btn"
                @click="handleRenameConfirm"
              ></i>
              <i
                class="bkai-icon bkai-close rename-btn cancel-btn"
                @click="handleRenameCancel"
              ></i>
            </div>
          </div>
        </div>
      </div>
      <span
        ref="moreIconRef"
        class="bkai-icon bkai-more"
        @click="handleMoreIconClick"
      ></span>
    </div>
    <div class="right-section">
      <i
        v-if="props.showNewChatIcon && props.enableChatSession !== false"
        v-bk-tooltips="{ content: t('新增会话'), boundary: 'parent' }"
        class="bkai-icon bkai-xinzengliaotian"
        @click="handleNewChat"
      ></i>
      <i
        v-if="props.showHistoryIcon && props.enableChatSession !== false"
        ref="historyIconRef"
        v-bk-tooltips="{ content: t('历史会话'), boundary: 'parent' }"
        class="bkai-icon bkai-history"
        @click="handleHistoryClick"
      ></i>
      <i
        v-if="props.chatGroup?.enabled"
        v-bk-tooltips="{ content: t('转人工'), boundary: 'parent' }"
        class="bkai-icon bkai-zhushou"
        @click="handleHelpClick"
      ></i>
      <i
        ref="compressionRef"
        class="bkai-icon"
        :class="compressionIcon"
        @click="emit('toggle-compression')"
      ></i>
      <i
        ref="closeRef"
        class="bkai-icon bkai-close-line-2"
        @click="emit('close')"
      ></i>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { bkTooltips, Input as BkInput, Message } from 'bkui-vue';
  import { computed, ref, onMounted, watch, onBeforeUnmount } from 'vue';

  import logo from '../assets/images/avatar.png';
  import { useHistoryPanel } from '../composables/use-history-panel';
  import { useInjectSessionStore } from '../composables/use-session-store';
  import { useTooltip } from '../composables/use-tippy';
  import { t } from '../lang';
  import type { SessionStore } from '../store/sessionStore';

  import HistoryPanel from './history-panel.vue';

  const props = withDefaults(
    defineProps<{
      title: string;
      isCompressionHeight: boolean;
      draggable: boolean;
      showHistoryIcon: boolean;
      showNewChatIcon?: boolean;
      enableChatSession?: boolean;
      chatGroup?: {
        enabled: boolean;
        staff: string[];
      };
      hasSessionContents?: boolean;
    }>(),
    {
      title: '',
      isCompressionHeight: false,
      draggable: true,
      showHistoryIcon: true,
      showNewChatIcon: true,
      enableChatSession: true,
      chatGroup: () => ({
        enabled: false,
        staff: [],
      }),
    }
  );

  const emit =
    defineEmits<
      (
        e: 'close' | 'toggle-compression' | 'new-chat' | 'auto-generate-name' | 'help-click',
        sessionCode?: string
      ) => void
    >();

  const vBkTooltips = bkTooltips;

  // 注入会话存储实例
  const sessionStore = useInjectSessionStore() as SessionStore;

  // 历史面板相关的 refs
  const historyIconRef = ref<HTMLElement | null>(null);

  // 更多图标相关的 refs
  const moreIconRef = ref<HTMLElement | null>(null);

  // 重命名相关的 refs 和状态
  const showRenameTooltip = ref(false);
  const renameInputValue = ref('');
  const renameInputRef = ref<InstanceType<typeof BkInput> | null>(null);

  // 使用历史面板 composable
  const { handleTriggerClick: handleHistoryClick } = useHistoryPanel({
    triggerRef: historyIconRef,
    panelComponent: HistoryPanel,
    panelProps: {
      sessionStore: sessionStore,
    },
    tippyOptions: {
      placement: 'bottom-end',
      offset: [0, 8],
      appendTo: () =>
        (document.querySelector('.ai-blueking-container-wrapper') as HTMLElement) || document.body,
    },
  });

  const displayTitle = computed(() => {
    // 如果关闭会话管理 title 为智能体名本身
    if (!props.enableChatSession) {
      return sessionStore.agentInfo.value?.agentName;
    }

    return (
      props.title ||
      `${sessionStore.agentInfo.value?.agentName || ''}-${(sessionStore.currentSession.value as { sessionName?: string })?.sessionName || ''}`
    );
  });

  const compressionIcon = computed(() => {
    return props.isCompressionHeight ? 'bkai-morenchicun' : 'bkai-yasuo';
  });

  const compressionTooltip = computed(() => {
    return props.isCompressionHeight ? t('恢复默认尺寸') : t('缩小高度');
  });

  const headerRef = ref<HTMLElement | null>(null);
  const compressionRef = ref<HTMLElement | null>(null);
  const closeRef = ref<HTMLElement | null>(null);

  // 下拉菜单内容
  const dropdownMenuContent = computed(() => {
    const isDisabled = !props.hasSessionContents;
    const disabledClass = isDisabled ? 'disabled' : '';
    const tooltipAttr = isDisabled ? `data-tippy-content="${t('请先发起会话')}"` : '';

    return `
      <div class="tippy-dropdown-menu">
        <div class="tippy-menu-item" data-action="rename">
          <i class="bkai-icon bkai-bianji"></i>
          <span>${t('重命名')}</span>
        </div>
        <div class="tippy-menu-item ${disabledClass}" data-action="auto-generate" ${tooltipAttr}>
          <i class="bkai-icon bkai-auto-refresh-line"></i>
          <span>${t('自动生成命名')}</span>
        </div>
        <div class="tippy-menu-item" data-action="share">
          <i class="bkai-icon bkai-fenxiang"></i>
          <span>${t('分享会话')}</span>
        </div>
      </div>
    `;
  });

  const { createTooltip, destroyAll } = useTooltip({
    arrow: true,
    delay: [0, 0],
  });

  // 更多图标的 tippy 实例
  let moreIconTippy: ReturnType<typeof createTooltip> | null = null;

  // 初始化 tooltip
  const initTooltips = () => {
    destroyAll(); // 先清除所有已存在的 tooltip

    // 销毁更多图标的 tippy 实例
    if (moreIconTippy) {
      moreIconTippy.destroy();
      moreIconTippy = null;
    }

    if (compressionRef.value) {
      createTooltip(compressionRef.value, compressionTooltip.value, {
        appendTo: document.querySelector('.ai-blueking-container-wrapper') as HTMLElement,
      });
    }
    if (closeRef.value) {
      createTooltip(closeRef.value, t('关闭'), {
        appendTo: document.querySelector('.ai-blueking-container-wrapper') as HTMLElement,
      });
    }

    // 初始化更多图标的下拉菜单
    if (moreIconRef.value) {
      moreIconTippy = createTooltip(moreIconRef.value, dropdownMenuContent.value, {
        theme: 'ai-blueking-light more-menu-light light',
        placement: 'bottom-start',
        trigger: 'manual',
        interactive: true,
        allowHTML: true,
        arrow: false,
        offset: [0, 4],
        appendTo:
          (document.querySelector('.ai-blueking-container-wrapper') as HTMLElement) ||
          document.body,
        onShow: () => {
          // 添加菜单项点击事件监听
          setTimeout(() => {
            const menuItems = document.querySelectorAll('.tippy-menu-item');
            menuItems.forEach(item => {
              const element = item as HTMLElement & { _tippy?: any };
              // 初始化tippy tooltip
              if (element._tippy) {
                element._tippy.destroy();
              }
              // 为禁用的自动生成命名项添加tooltip
              if (element.classList.contains('disabled') && element.dataset.action === 'auto-generate') {
                createTooltip(element, t('请先发起会话'), {
                  arrow: true,
                  offset: [0, 8],
                  appendTo: document.querySelector('.ai-blueking-container-wrapper') as HTMLElement,
                });
              }
              element.addEventListener('click', handleMenuItemClick);
            });
          }, 0);
        },
        onHide: () => {
          // 移除菜单项点击事件监听
          const menuItems = document.querySelectorAll('.tippy-menu-item');
          menuItems.forEach(item => {
            const element = item as HTMLElement & { _tippy?: any };
            element.removeEventListener('click', handleMenuItemClick);
            // 销毁tippy实例
            if (element._tippy) {
              element._tippy.destroy();
            }
          });
        },
      });
    }
  };

  // 监听压缩状态变化，更新 tooltip
  watch(
    () => props.isCompressionHeight,
    () => {
      initTooltips();
    }
  );

  // 监听会话内容变化，更新 tooltip
  watch(
    () => props.hasSessionContents,
    () => {
      initTooltips();
    }
  );

  onMounted(() => {
    initTooltips();

    // 添加点击外部关闭重命名 tooltip 的事件监听
    document.addEventListener('click', handleClickOutside);
  });

  onBeforeUnmount(() => {
    destroyAll();
    // 清理更多图标的 tippy 实例
    if (moreIconTippy) {
      moreIconTippy.destroy();
      moreIconTippy = null;
    }

    // 移除点击外部关闭重命名 tooltip 的事件监听
    document.removeEventListener('click', handleClickOutside);
  });

  // 处理新增聊天按钮点击
  const handleNewChat = async () => {
    try {
      // 通知父组件
      emit('new-chat');
      // 创建新会话（保持初始化逻辑， 如果已有空回话，不再新建）
      await sessionStore.initSession(false);
    } catch (error) {
      console.error('Failed to create new chat:', error);
    }
  };

  // 处理更多图标点击
  const handleMoreIconClick = (event: Event) => {
    event.stopPropagation();
    if (moreIconTippy) {
      if (moreIconTippy.state.isVisible) {
        moreIconTippy.hide();
      } else {
        moreIconTippy.show();
      }
    }
  };

  // 处理菜单项点击
  const handleMenuItemClick = (event: Event) => {
    event.stopPropagation(); // 阻止事件冒泡
    event.preventDefault(); // 阻止默认行为

    const target = event.currentTarget as HTMLElement;
    const action = target.dataset.action;

    // 如果是禁用的菜单项，直接返回
    if (target.classList.contains('disabled')) {
      return;
    }

    // 隐藏下拉菜单
    if (moreIconTippy) {
      moreIconTippy.hide();
    }

    switch (action) {
      case 'rename':
        handleRename();
        break;
      case 'auto-generate':
        handleAutoGenerate();
        break;
      case 'share':
        handleShare();
        break;
    }
  };

  // 重命名处理函数
  const handleRename = () => {
    // 暂时移除点击外部事件监听器，防止立即触发
    document.removeEventListener('click', handleClickOutside);

    // 获取当前会话名称作为初始值
    const currentSession = sessionStore.currentSession.value;
    if (
      currentSession &&
      'sessionName' in currentSession &&
      typeof currentSession.sessionName === 'string'
    ) {
      renameInputValue.value = currentSession.sessionName as string;
    } else {
      renameInputValue.value = '';
    }

    // 显示重命名 tooltip
    showRenameTooltip.value = true;

    // 延迟重新添加点击外部事件监听器
    setTimeout(() => {
      document.addEventListener('click', handleClickOutside);
    }, 100);

    // 延迟获取焦点，确保DOM已渲染
    setTimeout(() => {
      if (renameInputRef.value) {
        try {
          // 尝试多种方式获取输入框元素
          let inputElement: HTMLInputElement | null = null;

          // 类型安全地访问 BkInput 组件的属性
          const bkInputInstance = renameInputRef.value;

          if (bkInputInstance && typeof bkInputInstance.focus === 'function') {
            bkInputInstance.focus();
          }
          // 查找真实的 input 元素来选中文本

          inputElement = (bkInputInstance.$el as HTMLElement)?.querySelector('input');

          // 选中文本
          if (inputElement && typeof inputElement.select === 'function') {
            inputElement.select();
          }
        } catch (error) {
          console.warn('Failed to focus rename input:', error);
        }
      }
    }, 100);
  };

  // 确认重命名
  const handleRenameConfirm = async () => {
    const newName = renameInputValue.value.trim();

    if (!newName) {
      // 如果输入为空，直接取消
      handleRenameCancel();
      return;
    }

    const currentSession = sessionStore.currentSession.value;
    if (!(currentSession as { sessionCode?: string })?.sessionCode) {
      console.warn('没有当前会话，无法重命名');
      handleRenameCancel();
      return;
    }

    try {
      // 调用 sessionStore 的重命名方法
      await sessionStore.updateSession((currentSession as { sessionCode: string }).sessionCode, {
        sessionName: newName,
      });
    } catch (error) {
      Message({
        theme: 'error',
        message: t('重命名失败'),
      });
    } finally {
      // 隐藏重命名 tooltip
      showRenameTooltip.value = false;
      renameInputValue.value = '';
    }
  };

  // 取消重命名
  const handleRenameCancel = () => {
    showRenameTooltip.value = false;
    renameInputValue.value = '';
  };

  // 处理重命名输入框的键盘事件
  const handleRenameKeyup = (inputValue: string, event: KeyboardEvent) => {
    // 更新输入值
    renameInputValue.value = inputValue;

    if (event.key === 'Enter') {
      handleRenameConfirm();
    } else if (event.key === 'Escape') {
      handleRenameCancel();
    }
  };

  // 处理点击外部关闭重命名 tooltip
  const handleClickOutside = (event: Event) => {
    if (!showRenameTooltip.value) return;

    const target = event.target as HTMLElement;
    const renameTooltip = document.querySelector('.rename-tooltip');

    // 如果点击的不是重命名 tooltip 内部，则关闭
    if (renameTooltip && !renameTooltip.contains(target)) {
      handleRenameCancel();
    }
  };

  // 自动生成命名处理函数
  const handleAutoGenerate = async () => {
    // 检查是否有当前会话
    const sessionCode: string = (sessionStore.currentSession.value as any)?.sessionCode || '';
    if (!sessionCode) {
      console.warn('没有当前会话，无法进行自动命名');
      return;
    }

    try {
      // 通过 emit 事件让父组件处理自动命名
      emit('auto-generate-name', sessionCode);
    } catch (error) {
      console.error('自动命名失败:', error);
    }
  };

  // 分享会话处理函数
  const handleShare = () => {
    // 触发自定义事件，让父组件处理进入分享选择模式
    const event = new CustomEvent('enter-select-mode', {
      detail: { type: 'share' as const },
    });
    window.dispatchEvent(event);
  };

  // 处理转人工按钮点击事件
  const handleHelpClick = () => {
    emit('help-click');
  };
</script>

<style lang="scss" scoped>
  .header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    height: 48px;
    padding: 14px;
    border-bottom: 1px solid #e5e5e5;

    &.draggable {
      cursor: move;
    }

    .left-section {
      display: flex;
      gap: 4px;
      align-items: center;
      flex: 1;
      min-width: 0;

      .logo {
        width: 32px;
        height: 32px;

        img {
          width: 100%;
          height: 100%;
          object-fit: cover;
        }
      }

      .title {
        position: relative; // 为重命名 tooltip 提供定位基准
        font-size: 14px;
        font-weight: 600;
        line-height: 20px;
        color: #4d4f56;
        max-width: calc(100% - 65px);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;

        &.title-with-tooltip {
          overflow: visible; // 显示 tooltip 时允许溢出
        }
      }
    }

    .right-section {
      display: flex;
      gap: 12px;
    }

    .bkai-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 20px;
      height: 20px;
      margin-right: 0;
      font-size: 14px;
      color: #63656e;
      cursor: pointer;
      border-radius: 2px;

      &:hover {
        color: #4d4f56;
        background: #eaebf0;
      }
    }

    // 重命名 tooltip 样式
    .rename-tooltip {
      position: absolute;
      top: 100%;
      left: 0;
      z-index: 9999;
      margin-top: 8px;
      min-width: 300px; // 设置最小宽度确保有足够空间

      .rename-content {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 8px 12px;
        background: #fff;
        border: 1px solid #dcdee5;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);

        .rename-input {
          flex: 1;
          min-width: 0;
        }

        .rename-buttons {
          display: flex;
          gap: 4px;
          flex-shrink: 0;

          .rename-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: #ffffff;
            border: 1px solid #c4c6cc;
            width: 32px;
            height: 32px;
            font-size: 20px;
            cursor: pointer;
            border-radius: 2px;
            transition: all 0.2s ease;

            &:hover {
              border: 1px solid #979ba5;
            }

            &.confirm-btn {
              color: #2caf5e;
            }

            &.cancel-btn {
              color: #979ba5;
            }
          }
        }
      }
    }
  }
</style>

<style lang="scss">
  // 历史面板 tippy 样式
  .tippy-box[data-theme~='history-panel'] {
    background-color: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    padding: 0;

    .tippy-content {
      padding: 0px;
    }
  }

  // 更多图标下拉菜单样式
  .tippy-box[data-theme~='more-menu-light'] {
    background-color: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
    padding: 0;

    .tippy-content {
      padding: 0;
    }

    .tippy-dropdown-menu {
      display: flex;
      flex-direction: column;
      gap: 2px;
      background-color: #fff;
      border-radius: 4px;
      min-width: 140px;
      padding: 4px 0;

      .tippy-menu-item {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        height: 32px;
        margin: 0;
        padding: 6px 12px;
        font-size: 12px;
        color: #4d4f56;
        cursor: pointer;
        border-radius: 0;
        white-space: nowrap;

        i {
          font-size: 14px;
          color: #979ba5;
        }

        &:hover {
          background: #f5f7fa;
          color: #3a84ff;

          i {
            color: #3a84ff;
          }
        }

        &.disabled {
          color: #c4c6cc;
          cursor: not-allowed;

          i {
            color: #c4c6cc;
          }

          &:hover {
            background: transparent;
            color: #c4c6cc;

            i {
              color: #c4c6cc;
            }
          }
        }
      }
    }
  }
</style>
