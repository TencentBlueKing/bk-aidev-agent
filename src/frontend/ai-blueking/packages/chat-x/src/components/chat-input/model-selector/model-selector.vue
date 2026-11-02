<template>
  <Tippy
    ref="tippyRef"
    v-bind="innerTippyProps"
    @hidden="handleHidden"
    @show="handleShow"
  >
    <ModelSelectorTrigger
      :disabled="disabled"
      :effort-label="effortLabel"
      :expanded="isExpanded"
      :model="currentModel"
      :placeholder="placeholder"
    />
    <template #content>
      <ModelSelectorPanel
        ref="panelRef"
        v-model:keyword="keyword"
        :models="filteredModels"
        :reasoning-effort="reasoningEffort"
        :search-placeholder="searchPlaceholder"
        :selected-name="selectedModel"
        :tippy-options="tippyOptions"
        @reasoning-effort-change="handleReasoningEffortChange"
        @select="handleSelect"
      />
    </template>
  </Tippy>
</template>

<script setup lang="ts">
  import { computed, shallowRef, toRef, useTemplateRef } from 'vue';

  import { type TippyOptions, Tippy, useTippy } from 'vue-tippy';

  import { t } from '../../../lang/lang';
  import ModelSelectorPanel from './model-selector-panel.vue';
  import ModelSelectorTrigger from './model-selector-trigger.vue';
  import { resolveReasoningSuffix } from './reasoning-effort';
  import { useModelSelector } from './use-model-selector';

  import type { IModelOption, ReasoningEffort } from './types';
  import type { Instance } from 'tippy.js';

  import 'tippy.js/dist/tippy.css';

  const props = withDefaults(
    defineProps<{
      /** 是否禁用整个选择器 */
      disabled?: boolean;
      /** 模型列表 */
      models?: IModelOption[];
      /** trigger 无选中时的占位文案 */
      placeholder?: string;
      /** 搜索框占位文案 */
      searchPlaceholder?: string;
      /** 透传给 tippy 的额外配置 */
      tippyOptions?: Partial<Omit<TippyOptions, 'getReferenceClientRect' | 'triggerTarget'>>;
    }>(),
    {
      models: () => [],
      placeholder: () => t('选择模型'),
      searchPlaceholder: () => t('搜索模型关键字'),
      tippyOptions: undefined,
    },
  );
  const emit = defineEmits<{
    (e: 'change', model: IModelOption): void;
    (e: 'reasoningEffortChange', model: IModelOption, effort: ReasoningEffort): void;
    (e: 'show'): void;
  }>();
  /** 当前选中的模型（值为 llm_name，v-model） */
  const selectedModel = defineModel<string>();
  /** 当前模型生效的思考深度档位（v-model:reasoningEffort），为空时按模型 default_effort 展示 */
  const reasoningEffort = defineModel<null | ReasoningEffort>('reasoningEffort');

  const tippyRef = useTemplateRef<InstanceType<typeof Tippy> & ReturnType<typeof useTippy>>('tippyRef');
  const panelRef = useTemplateRef<InstanceType<typeof ModelSelectorPanel>>('panelRef');
  const isExpanded = shallowRef(false);
  /** 本次「点击外部」落在描述卡片内，下拉不应收起 */
  let keepOpenOnHide = false;

  const { keyword, filteredModels, currentModel, resetKeyword } = useModelSelector({
    models: toRef(props, 'models'),
    selectedModel,
  });

  const effortLabel = computed(() => resolveReasoningSuffix(currentModel.value, reasoningEffort.value));

  const innerTippyProps = computed(
    () =>
      ({
        arrow: false,
        interactive: true,
        offset: [0, 6],
        placement: 'top-end',
        theme: 'ai-model-selector',
        trigger: 'click',
        appendTo: () => document.body,
        ...(props.tippyOptions || {}),
        // 描述卡片挂在下拉浮层之外，点击 / 拖动卡片内的滑块会被当作「点击外部」，需在收起前拦截
        onClickOutside: (instance: Instance, event: Event) => {
          keepOpenOnHide = Boolean(panelRef.value?.isTipTarget(event.target));
          props.tippyOptions?.onClickOutside?.(instance, event);
        },
        onHide: (instance: Instance) => {
          if (keepOpenOnHide) {
            keepOpenOnHide = false;
            return false;
          }
          return props.tippyOptions?.onHide?.(instance);
        },
      }) as InstanceType<typeof Tippy>['$props'],
  );

  const handleShow = () => {
    if (props.disabled || !props.models.length) {
      return false;
    }
    isExpanded.value = true;
    resetKeyword();
    emit('show');
    // 展开后自动聚焦搜索框（设计稿 annotation）
    panelRef.value?.focusSearch();
  };
  const handleHidden = () => {
    isExpanded.value = false;
    // 下拉内容保持挂载，收起时不会走面板卸载，需主动关掉描述 tip
    panelRef.value?.hideDescriptionTip();
  };

  /** 切换模型；换了模型时清空档位，与后端「换模型即清空会话档位」一致，展示回落新模型的默认档 */
  const selectModel = (model: IModelOption) => {
    if (selectedModel.value !== model.llm_name) {
      reasoningEffort.value = undefined;
    }
    selectedModel.value = model.llm_name;
    emit('change', model);
  };

  const handleSelect = (model: IModelOption) => {
    selectModel(model);
    tippyRef.value?.hide?.();
  };

  /**
   * 卡片内调档：非当前模型先选中该模型（先抛 change，再抛 reasoningEffortChange，
   * 便于接入方按「切模型、切档位分开调」的顺序更新会话），下拉保持展开。
   */
  const handleReasoningEffortChange = (model: IModelOption, effort: ReasoningEffort) => {
    if (selectedModel.value !== model.llm_name) {
      selectModel(model);
    }
    reasoningEffort.value = effort;
    emit('reasoningEffortChange', model, effort);
  };
</script>
