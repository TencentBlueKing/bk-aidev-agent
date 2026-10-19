<template>
  <div
    ref="panelRef"
    class="ai-model-selector-panel"
    @scroll.passive="hideDescriptionTip"
  >
    <div class="ai-model-selector-panel-search">
      <BkInput
        ref="searchInputRef"
        v-model="keyword"
        :behavior="'simplicity'"
        class="ai-model-selector-panel-search-input"
        clearable
        :placeholder="searchPlaceholder"
        type="text"
      >
        <template #prefix>
          <SearchIcon class="ai-model-selector-panel-search-icon" />
        </template>
      </BkInput>
    </div>
    <div
      class="ai-model-selector-panel-list"
      @scroll.passive="hideDescriptionTip"
    >
      <div
        v-for="(model, index) in models"
        :key="model.id"
        class="ai-model-selector-panel-option"
        :class="{
          'is-selected': model.llm_name === selectedName,
          'is-active': index === activeIndex,
          'is-disabled': model.disabled,
        }"
        @click="handleSelect(model)"
        @mouseenter="handleOptionEnter($event, model)"
        @mouseleave="handleOptionLeave"
      >
        <ResourceIcon
          v-if="model.icon"
          class="ai-model-selector-panel-option-icon"
          :icon="model.icon"
          :name="model.llm_name"
          type="model"
        />
        <span
          class="ai-model-selector-panel-option-name"
          :title="optionNameTitle(model)"
        >
          {{ model.llm_name }}
        </span>
        <span
          v-if="capabilityMap.get(model.llm_name)?.length"
          class="ai-model-selector-panel-option-tags"
        >
          <span
            v-for="(capability, capabilityIndex) in capabilityMap.get(model.llm_name)"
            :key="capabilityIndex"
            class="ai-model-capability-tag"
            :class="`is-${capability.theme || 'default'}`"
          >
            {{ capability.text }}
          </span>
        </span>
      </div>
      <div
        v-if="!models.length"
        class="ai-model-selector-panel-empty"
      >
        <Exception
          scene="part"
          :type="'empty'"
        >
          {{ t('搜索结果为空') }}
        </Exception>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, nextTick, onBeforeUnmount, shallowRef, useTemplateRef, watch } from 'vue';

  import { Input as BkInput, Exception } from 'bkui-vue';
  import tippy from 'tippy.js';

  import { useMenuKeydown } from '../../../composables/use-menu-keydown';
  import { SearchIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import { ResourceIcon } from '../../resource-icon';
  import { resolveModelCapabilities } from './capabilities';
  import { createModelDescriptionTippy, MODEL_DESCRIPTION_TIP_DELAY_MS } from './create-model-description-tippy';

  import type { AITippyProps } from '../../../types';
  import type { IModelCapability, IModelOption } from './types';
  import type { Instance } from 'tippy.js';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<{
    /** 待展示的模型列表（已按关键字过滤） */
    models: IModelOption[];
    /** 搜索框占位文案 */
    searchPlaceholder?: string;
    /** 当前选中模型的 llm_name */
    selectedName?: string;
    /** 外层 common tippy 配置，描述气泡复用其中的 appendTo / placement / zIndex */
    tippyOptions?: AITippyProps;
  }>();

  /** 预计算每个模型的能力标签，避免模板内重复派生（键为 llm_name） */
  const capabilityMap = computed(() => {
    const map = new Map<string, IModelCapability[]>();
    props.models.forEach(model => map.set(model.llm_name, resolveModelCapabilities(model)));
    return map;
  });
  const emit = defineEmits<{
    (e: 'select', model: IModelOption): void;
  }>();
  /** 搜索关键字（受控，回传给容器交由 composable 过滤） */
  const keyword = defineModel<string>('keyword', { default: '' });

  const panelRef = useTemplateRef<HTMLElement>('panelRef');
  const searchInputRef = useTemplateRef<HTMLInputElement>('searchInputRef');

  // 整表共用一个 tip：移入后延迟创建，离开 / 滚动 / 列表替换 / 卸载时销毁
  let descriptionTip: Instance | undefined;
  let tipAnchor: HTMLElement | undefined;
  let showTimer: ReturnType<typeof setTimeout> | undefined;
  let showToken = 0;

  const readDescription = (model: IModelOption) => model.description?.trim() || undefined;

  /** 有描述时不再挂名称 title，避免和描述 tip 叠成两个气泡 */
  const optionNameTitle = (model: IModelOption) => (readDescription(model) ? undefined : model.llm_name);

  const getReferenceClientRect = Object.assign(
    () => (tipAnchor?.isConnected ? tipAnchor.getBoundingClientRect() : new DOMRect()),
    { contextElement: document.body },
  );

  /** 描述气泡和 common tippy 挂到同一层，裁切边界才跟得上全屏容器 */
  const resolveTipContextElement = (appendTo: AITippyProps['appendTo']) => {
    if (appendTo instanceof HTMLElement) {
      return appendTo;
    }
    if (typeof appendTo === 'function') {
      const target = appendTo(document.body);
      if (target instanceof HTMLElement) {
        return target;
      }
    }
    return document.body;
  };

  const clearShowTimer = () => {
    if (showTimer === undefined) {
      return;
    }
    clearTimeout(showTimer);
    showTimer = undefined;
  };

  const hideDescriptionTip = () => {
    showToken += 1;
    clearShowTimer();
    tipAnchor = undefined;
    const instance = descriptionTip;
    descriptionTip = undefined;
    instance?.destroy();
  };

  const handleOptionEnter = (event: MouseEvent, model: IModelOption) => {
    const description = readDescription(model);
    if (!description) {
      hideDescriptionTip();
      return;
    }
    const anchor = event.currentTarget;
    if (!(anchor instanceof HTMLElement)) {
      return;
    }
    clearShowTimer();
    tipAnchor = anchor;
    const token = showToken;
    showTimer = setTimeout(() => {
      showTimer = undefined;
      if (token !== showToken || tipAnchor !== anchor || !anchor.isConnected) {
        return;
      }
      if (!descriptionTip) {
        getReferenceClientRect.contextElement = resolveTipContextElement(props.tippyOptions?.appendTo);
        descriptionTip = tippy(document.createElement('div'), {
          ...createModelDescriptionTippy(getReferenceClientRect, props.tippyOptions),
          // tippy 的 onShow 只认 false（取消展示）或 void；锚点已卸载时取消
          onShow: () => {
            if (!tipAnchor?.isConnected) {
              return false;
            }
          },
        });
      }
      descriptionTip.setContent(description);
      descriptionTip.show();
    }, MODEL_DESCRIPTION_TIP_DELAY_MS);
  };

  const handleOptionLeave = () => {
    hideDescriptionTip();
  };

  onBeforeUnmount(hideDescriptionTip);

  // 键盘导航复用通用 composable，items 需为 shallowRef，故本地同步一份并在列表变化时重置高亮
  const navItems = shallowRef<IModelOption[]>(props.models);
  const { activeIndex } = useMenuKeydown<IModelOption>({
    items: navItems,
    menuRef: panelRef,
    onSelect: model => handleSelect(model),
  });

  watch(
    () => props.models,
    models => {
      navItems.value = models;
      activeIndex.value = 0;
      hideDescriptionTip();
    },
  );

  const handleSelect = (model: IModelOption) => {
    if (model.disabled) {
      return;
    }
    emit('select', model);
  };

  /** 聚焦搜索框（容器在下拉展开时调用） */
  const focusSearch = () => {
    nextTick(() => {
      searchInputRef.value?.focus();
    });
  };

  defineExpose({
    focusSearch,
    hideDescriptionTip,
  });
</script>

<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-model-selector-panel {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 360px;
    max-height: 360px;
    padding-top: 4px;
    overflow-y: auto;
    background: #fff;
    border: 1px solid variables.$color-border;
    border-radius: 4px;

    // 阴影来源 Figma Shadow/Card - Normal
    box-shadow: 0 2px 4px 0 rgb(25 25 41 / 5%);

    &-search {
      display: flex;
      gap: 8px;
      align-items: center;
      margin: 0 8px;

      &-icon {
        flex: 0 0 16px;
        width: 16px;
        height: 16px;
        margin: auto;
        font-size: 16px;
        color: variables.$color-text-secondary;
      }

      input {
        flex: 1;
        min-width: 0;
        padding: 0;
        margin-left: 8px;
        font-size: var(--ai-font-size, 12px);
        line-height: var(--ai-line-height, 20px);
        color: variables.$color-text;
        outline: none;
        background: transparent !important;
        border: none;

        &::placeholder {
          color: #c4c6cc;
        }
      }
    }

    &-list {
      display: flex;
      flex-direction: column;
      max-height: 300px;
      overflow-y: auto;
    }

    &-option {
      display: flex;
      gap: 8px;
      align-items: center;
      padding: 6px 12px;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height, 20px);
      color: variables.$color-text;
      cursor: pointer;

      &.is-active,
      &:hover {
        background: #f5f7fa;
      }

      // 选中态优先级高于 hover/active
      &.is-selected {
        color: variables.$color-primary;
        background: #e1ecff;
      }

      &.is-disabled {
        color: #c4c6cc;
        cursor: not-allowed;
        background: transparent;
      }

      // 尺寸与圆角由 ResourceIcon 自带，此处只做定位约束
      &-icon {
        flex: 0 0 16px;
      }

      &-name {
        flex: 1;
        min-width: 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      &-tags {
        display: flex;
        flex: 0 0 auto;
        gap: 4px;
        align-items: center;
      }
    }

    &-empty {
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 12px;
      padding-top: 0;
      font-size: var(--ai-font-size, 12px);
      color: variables.$color-text-secondary;
      text-align: center;

      img {
        margin-top: -10px;
      }
    }
  }

  // 模型选择下拉的 tippy 容器：去除默认内边距与背景，交由面板自身按设计稿渲染边框/圆角/阴影
  .tippy-box[data-theme~='ai-model-selector'] .tippy-content {
    padding: 0;
    background: transparent;
  }

  // 能力标签：语义色直接取自设计稿（warn/brand/success 背景与深色文字），源码无对应变量故直用 hex
  .ai-model-capability-tag {
    display: flex;
    flex: 0 0 auto;
    align-items: center;
    height: 16px;
    padding: 0 6px;
    font-size: 10px;
    line-height: 16px;
    white-space: nowrap;
    border-radius: 2px;

    &.is-warning {
      color: #e38b02;
      background: #fdeed8;
    }

    &.is-primary {
      color: #1768ef;
      background: #e1ecff;
    }

    &.is-success {
      color: #299e56;
      background: #daf6e5;
    }

    &.is-default {
      color: variables.$color-text;
      background: variables.$color-bg-tab;
    }
  }
</style>
