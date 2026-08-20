<template>
  <div
    ref="headerRef"
    class="ai-header drag-handle"
    :class="{ draggable: props.draggable, 'is-aside-expanded': !props.asideCollapsed }"
  >
    <div class="left-section">
      <div class="logo">
        <img
          alt="logo"
          :src="logo"
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
      <!-- 更多图标下拉菜单 - 使用 vue-tippy -->
      <Tippy
        v-if="props.showMoreIcon && hasPermission"
        ref="moreMenuTippyRef"
        :append-to="tippyAppendTo"
        :arrow="false"
        interactive
        :offset="[0, 4]"
        placement="bottom-start"
        theme="ai-blueking-light more-menu-light light"
        trigger="manual"
        @hidden="moreMenuVisible = false"
        @shown="moreMenuVisible = true"
      >
        <span
          class="bkai-icon bkai-more"
          @click="handleMoreIconClick"
        ></span>

        <template #content>
          <div
            v-if="moreMenuVisible"
            class="tippy-dropdown-menu"
          >
            <div
              v-if="props.dropdownMenuConfig?.showRename"
              class="tippy-menu-item"
              @click="handleRenameAction"
            >
              <i class="bkai-icon bkai-bianji"></i>
              <span>{{ t('重命名') }}</span>
            </div>
            <div
              v-if="props.dropdownMenuConfig?.showAutoGenerate"
              v-tippy="{
                content: !props.hasSessionContents ? t('请先发起会话') : '',
                theme: 'ai-blueking-tooltip',
                arrow: true,
                delay: [300, 0],
                appendTo: tippyAppendTo,
              }"
              class="tippy-menu-item"
              :class="{
                disabled: !props.hasSessionContents || props.autoGenerateLoading,
              }"
              @click="handleAutoGenerateAction"
            >
              <Loading
                v-if="props.autoGenerateLoading"
                mode="spin"
                size="mini"
                theme="primary"
              />
              <i
                v-else
                class="bkai-icon bkai-auto-refresh-line"
              ></i>
              <span>{{ t('自动生成命名') }}</span>
            </div>
            <div
              v-if="props.dropdownMenuConfig?.showShare && props.renderMode !== RenderMode.Test"
              v-tippy="{
                content: !props.hasSessionContents ? t('请先发起会话') : '',
                theme: 'ai-blueking-tooltip',
                arrow: true,
                delay: [300, 0],
                appendTo: tippyAppendTo,
              }"
              class="tippy-menu-item"
              :class="{ disabled: !props.hasSessionContents }"
              @click="handleShareAction"
            >
              <i class="bkai-icon bkai-fenxiang"></i>
              <span>{{ t('分享会话') }}</span>
            </div>
          </div>
        </template>
      </Tippy>
    </div>
    <slot name="headerLeft" />
    <div class="right-section">
      <!-- 新增会话按钮 -->
      <i
        v-if="props.showNewChatIcon && enableChatSession !== false"
        v-bk-tooltips="{
          content: isCreatingChat
            ? t('正在创建会话...')
            : !hasSessionContents
              ? t('当前已是新会话')
              : getPermissionTooltip(t('新增会话')),
          boundary: 'parent',
        }"
        :class="[
          'bkai-icon',
          'bkai-xinzengliaotian',
          { disabled: !hasPermission || isCreatingChat || !hasSessionContents },
        ]"
        :style="getPermissionStyle()"
        @click="hasPermission && !isCreatingChat && hasSessionContents ? handleNewChat() : undefined"
      >
      </i>
      <!-- 历史会话按钮 -->
      <i
        v-if="props.showHistoryIcon && enableChatSession !== false"
        ref="historyIconRef"
        v-bk-tooltips="{
          content: getPermissionTooltip(t('历史会话')),
          boundary: 'parent',
        }"
        :class="['bkai-icon', 'bkai-history', { disabled: !hasPermission }]"
        :style="getPermissionStyle()"
        @click="hasPermission ? handleHistoryClick($event) : undefined"
      ></i>
      <i
        v-if="chatGroup?.enabled"
        v-bk-tooltips="{ content: t('转人工'), boundary: 'parent' }"
        class="bkai-icon bkai-zhushou"
        @click="handleHelpClick"
      ></i>
      <i
        v-if="props.showCompressionIcon"
        v-bk-tooltips="{ content: compressionTooltip, boundary: 'parent' }"
        class="bkai-icon"
        :class="compressionIcon"
        @click="emit('toggle-compression')"
      ></i>
      <i
        v-bk-tooltips="{ content: t('关闭'), boundary: 'parent' }"
        class="bkai-icon bkai-close-line-2"
        @click="emit('close')"
      ></i>
      <!-- 设计稿：关闭与侧栏展开之间有竖线分隔 -->
      <span
        v-if="props.showAsideToggle"
        aria-hidden="true"
        class="header-toolbar-divider"
      ></span>
      <span
        v-if="props.showAsideToggle"
        v-bk-tooltips="{
          content: props.asideCollapsed ? t('展开侧栏') : t('收起侧栏'),
          boundary: 'parent',
        }"
        class="bkai-icon aside-toggle"
        @click.stop="emit('toggle-aside')"
      >
        <AsideToggleIcon />
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { cloneVNode, computed, defineComponent, onBeforeUnmount, onMounted, ref, useTemplateRef, watch } from 'vue';

  import { CollapsedAsideIcon, RenderMode } from '@blueking/chat-x';
  import { Input as BkInput, bkTooltips, Loading, Message } from 'bkui-vue';
  import { Tippy, directive as vTippy } from 'vue-tippy';

  import logo from '../../assets/images/avatar.png';
  import { t } from '../../lang';
  import { useHistoryDropdown } from './history-dropdown/use-history-dropdown';

  import type { AIHeaderEmits, AIHeaderProps } from './types';
  import type { useTippy } from 'vue-tippy';

  const props = withDefaults(defineProps<AIHeaderProps>(), {
    title: '',
    agentName: '',
    sessionName: '',
    isCompressionHeight: false,
    draggable: true,
    showHistoryIcon: true,
    showNewChatIcon: true,
    showCompressionIcon: true,
    showMoreIcon: true,
    enableChatSession: true,
    hasPermission: true,
    chatGroup: () => ({
      enabled: false,
      staff: [],
      username: '',
    }),
    dropdownMenuConfig: () => ({
      showRename: true,
      showAutoGenerate: true,
      showShare: false,
    }),
    sessionBusinessManager: undefined,
    selectedLlmCode: undefined,
    renderMode: RenderMode.Chat,
    asideCollapsed: true,
    showAsideToggle: true,
  });

  const emit = defineEmits<AIHeaderEmits>();

  const AsideToggleIcon = defineComponent({
    name: 'AsideToggleIcon',
    setup() {
      return () => cloneVNode(CollapsedAsideIcon);
    },
  });

  defineSlots<{
    headerLeft?: () => unknown;
  }>();

  const vBkTooltips = bkTooltips;

  // Refs
  const headerRef = ref<HTMLElement | null>(null);
  const historyIconRef = ref<HTMLElement | null>(null);
  const moreMenuTippyRef = useTemplateRef<InstanceType<typeof Tippy> & ReturnType<typeof useTippy>>('moreMenuTippyRef');

  // 重命名相关的状态
  const showRenameTooltip = ref(false);
  const renameInputValue = ref('');
  const renameInputRef = ref<InstanceType<typeof BkInput> | null>(null);

  // 更多菜单可见状态
  const moreMenuVisible = ref(false);

  // tippy appendTo 目标
  const tippyAppendTo = () => (document.querySelector('.ai-blueking-panel') as HTMLElement) || document.body;

  // V2: 历史会话下拉面板（延迟初始化）
  let historyDropdownInstance: null | ReturnType<typeof useHistoryDropdown> = null;

  const initHistoryDropdown = () => {
    if (!historyIconRef.value || !props.sessionBusinessManager) return;

    historyDropdownInstance = useHistoryDropdown({
      triggerRef: historyIconRef,
      sessionBusinessManager: props.sessionBusinessManager,
      onSessionSwitch: (code: string) => emit('history-session-switch', code),
      onSessionDelete: (code: string) => emit('history-session-delete', code),
      onSessionRename: (code: string, name: string) => emit('history-session-rename', code, name),
    });
  };

  // 计算属性
  const displayTitle = computed(() => {
    if (!props.hasPermission) {
      return t('无智能体使用权限');
    }
    if (!props.enableChatSession) {
      return props.agentName;
    }
    return props.title || `${props.agentName || ''}-${props.sessionName || ''}`;
  });

  const compressionIcon = computed(() => {
    return props.isCompressionHeight ? 'bkai-morenchicun' : 'bkai-yasuo';
  });

  const compressionTooltip = computed(() => {
    return props.isCompressionHeight ? t('恢复默认尺寸') : t('缩小高度');
  });

  const hasPermission = computed(() => props.hasPermission);

  // 获取按钮的通用 tooltip 内容
  const getPermissionTooltip = (normalContent: string) => {
    return hasPermission.value ? normalContent : t('暂无使用权限');
  };

  // 获取按钮的通用样式
  const getPermissionStyle = () => {
    return { cursor: hasPermission.value ? 'pointer' : 'not-allowed' };
  };

  // 新增会话防抖状态
  const isCreatingChat = ref(false);

  // 事件处理
  const handleNewChat = async () => {
    if (isCreatingChat.value) return;
    isCreatingChat.value = true;
    try {
      // V2: 如果有 sessionBusinessManager，调用它创建新会话
      if (props.sessionBusinessManager) {
        try {
          const session = await props.sessionBusinessManager.createNewSession({
            model: props.selectedLlmCode,
          });
          if (session) {
            emit('new-chat-created', {
              sessionCode: session.sessionCode,
              sessionName: session.sessionName,
              createdAt: session.createdAt,
            });
          }
        } catch (error) {
          console.error('Failed to create new session:', error);
          Message({
            theme: 'error',
            message: t('创建会话失败'),
          });
        }
      }
      // 同时 emit 事件，保持 V1 兼容性
      emit('new-chat');
    } finally {
      isCreatingChat.value = false;
    }
  };

  const handleHistoryClick = (event: Event) => {
    event.stopPropagation();
    // V2: 使用历史下拉面板
    if (props.sessionBusinessManager) {
      // 如果还未初始化，先初始化
      if (!historyDropdownInstance) {
        initHistoryDropdown();
      }
      // 调用处理器
      if (historyDropdownInstance) {
        historyDropdownInstance.handleTriggerClick(event);
      }
    } else {
      // V1 兼容：触发旧的 history-click 事件
      emit('history-click', event);
    }
  };

  const handleHelpClick = () => {
    emit('help-click');
  };

  const handleMoreIconClick = (event: Event) => {
    event.stopPropagation();
    // 点击更多图标时，关闭历史会话面板
    if (historyDropdownInstance && historyDropdownInstance.isVisible()) {
      historyDropdownInstance.hide();
    }
    // 切换更多菜单
    if (moreMenuTippyRef.value) {
      if (moreMenuVisible.value) {
        moreMenuTippyRef.value.hide();
      } else {
        moreMenuTippyRef.value.show();
      }
    }
  };

  // 菜单项点击处理
  const handleRenameAction = () => {
    moreMenuTippyRef.value?.hide();
    handleRename();
  };

  const handleAutoGenerateAction = () => {
    if (!props.hasSessionContents || props.autoGenerateLoading) return;
    // 不关闭菜单，让 loading 状态在菜单中可见
    emit('auto-generate-name');
  };

  const handleShareAction = () => {
    if (!props.hasSessionContents) return;
    moreMenuTippyRef.value?.hide();
    emit('share');
  };

  // 重命名处理
  const handleRename = () => {
    document.removeEventListener('click', handleClickOutside);
    renameInputValue.value = props.sessionName || '';
    showRenameTooltip.value = true;

    setTimeout(() => {
      document.addEventListener('click', handleClickOutside);
    }, 100);

    setTimeout(() => {
      if (renameInputRef.value) {
        try {
          const bkInputInstance = renameInputRef.value;
          if (bkInputInstance && typeof bkInputInstance.focus === 'function') {
            bkInputInstance.focus();
          }
          const inputElement = (bkInputInstance.$el as HTMLElement)?.querySelector('input');
          if (inputElement && typeof inputElement.select === 'function') {
            inputElement.select();
          }
        } catch (error) {
          console.warn('Failed to focus rename input:', error);
        }
      }
    }, 100);
  };

  const handleRenameConfirm = () => {
    const newName = renameInputValue.value.trim();
    if (!newName) {
      handleRenameCancel();
      return;
    }

    emit('rename', newName);
    showRenameTooltip.value = false;
    renameInputValue.value = '';
  };

  const handleRenameCancel = () => {
    showRenameTooltip.value = false;
    renameInputValue.value = '';
  };

  const handleRenameKeyup = (inputValue: string, event: KeyboardEvent) => {
    renameInputValue.value = inputValue;
    if (event.key === 'Enter') {
      handleRenameConfirm();
    } else if (event.key === 'Escape') {
      handleRenameCancel();
    }
  };

  const handleClickOutside = (event: Event) => {
    if (!showRenameTooltip.value) return;

    const target = event.target as HTMLElement;
    const renameTooltip = document.querySelector('.rename-tooltip');

    if (renameTooltip && !renameTooltip.contains(target)) {
      handleRenameCancel();
    }
  };

  // 监听 autoGenerateLoading：loading 结束后自动关闭菜单
  watch(
    () => props.autoGenerateLoading,
    (isLoading, wasLoading) => {
      if (wasLoading && !isLoading && moreMenuVisible.value) {
        moreMenuTippyRef.value?.hide();
      }
    },
  );

  onMounted(() => {
    // V2: 延迟初始化历史下拉面板，确保 DOM 已挂载
    if (props.sessionBusinessManager) {
      initHistoryDropdown();
    }
    document.addEventListener('click', handleClickOutside);
  });

  onBeforeUnmount(() => {
    // V2: 清理历史下拉面板
    if (historyDropdownInstance) {
      historyDropdownInstance.destroy();
      historyDropdownInstance = null;
    }
    document.removeEventListener('click', handleClickOutside);
  });

  // 暴露方法
  defineExpose({
    headerRef,
    historyIconRef,
  });
</script>

<style lang="scss" scoped>
  .ai-header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    height: 48px;
    padding: 14px;
    border-bottom: 1px solid transparent;

    &.is-aside-expanded {
      border-bottom-color: #eaebf0;
    }

    &.draggable {
      cursor: move;
    }

    .left-section {
      display: flex;
      flex: 1;
      gap: 4px;
      align-items: center;
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
        position: relative;
        max-width: calc(100% - 65px);
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 14px;
        font-weight: 600;
        line-height: 20px;
        color: #4d4f56;
        white-space: nowrap;

        &.title-with-tooltip {
          overflow: visible;
        }
      }
    }

    .right-section {
      display: flex;
      gap: 12px;
      align-items: center;
      justify-content: flex-end;
    }

    .header-toolbar-divider {
      flex-shrink: 0;
      width: 1px;
      height: 8px;
      background: #dcdee5;
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

      &.disabled {
        color: #c4c6cc;
        cursor: not-allowed;

        &:hover {
          color: #c4c6cc;
          background: transparent;
        }
      }

      &.aside-toggle :deep(svg) {
        width: 14px;
        height: 14px;
      }
    }

    // 新增会话 loading 样式
    .new-chat-loading {
      position: absolute;
      inset: 0;
      display: flex;
      align-items: center;
      justify-content: center;
      background: inherit;
      border-radius: inherit;
    }

    // 重命名 tooltip 样式
    .rename-tooltip {
      position: absolute;
      top: 100%;
      left: 0;
      z-index: 9999;
      min-width: 300px;
      margin-top: 8px;

      .rename-content {
        display: flex;
        gap: 8px;
        align-items: center;
        padding: 8px 12px;
        background: #fff;
        border: 1px solid #dcdee5;
        border-radius: 4px;
        box-shadow: 0 2px 8px rgb(0 0 0 / 10%);

        .rename-input {
          flex: 1;
          min-width: 0;
        }

        .rename-buttons {
          display: flex;
          flex-shrink: 0;
          gap: 4px;

          .rename-btn {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            font-size: 20px;
            cursor: pointer;
            background: #fff;
            border: 1px solid #c4c6cc;
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
  // 更多图标下拉菜单样式
  .tippy-box[data-theme~='more-menu-light'] {
    padding: 0;
    background-color: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-shadow: 0 2px 8px rgb(0 0 0 / 10%);

    .tippy-content {
      padding: 0;
    }

    .tippy-dropdown-menu {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 140px;
      padding: 4px 0;
      background-color: #fff;
      border-radius: 4px;

      .tippy-menu-item {
        display: inline-flex;
        gap: 8px;
        align-items: center;
        height: 32px;
        padding: 6px 12px;
        margin: 0;
        font-size: 12px;
        color: #4d4f56;
        white-space: nowrap;
        cursor: pointer;
        border-radius: 0;

        i {
          font-size: 14px;
          color: #979ba5;
        }

        &:hover {
          color: #3a84ff;
          background: #f5f7fa;

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
            color: #c4c6cc;
            background: transparent;

            i {
              color: #c4c6cc;
            }
          }
        }
      }
    }
  }

  // 历史会话面板样式
  .tippy-box[data-theme~='history-panel'] {
    z-index: 10001; // 确保历史面板在最上层，避免与编辑状态重合
    padding: 0;
    background-color: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgb(0 0 0 / 10%);

    .tippy-content {
      padding: 0;
    }
  }
</style>
