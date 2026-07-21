<template>
  <Tippy
    ref="tippyRef"
    v-bind="innerTippyProps"
    @hidden="handleHidden"
    @show="handleShow"
  >
    <ModelSelectorTrigger
      :disabled="disabled"
      :expanded="isExpanded"
      :model="currentModel"
      :placeholder="placeholder"
    />
    <template #content>
      <ModelSelectorPanel
        ref="panelRef"
        v-model:keyword="keyword"
        :models="filteredModels"
        :search-placeholder="searchPlaceholder"
        :selected-name="selectedModel"
        @select="handleSelect"
      />
    </template>
  </Tippy>
</template>

<script setup lang="ts">
  import { computed, shallowRef, toRef, useTemplateRef } from 'vue';

  import { type TippyOptions, Tippy } from 'vue-tippy';

  import { t } from '../../../lang/lang';
  import ModelSelectorPanel from './model-selector-panel.vue';
  import ModelSelectorTrigger from './model-selector-trigger.vue';
  import { useModelSelector } from './use-model-selector';

  import type { IModelOption } from './types';

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
  }>();
  /** 当前选中的模型（值为 llm_name，v-model） */
  const selectedModel = defineModel<string>();

  const tippyRef = useTemplateRef<InstanceType<typeof Tippy>>('tippyRef');
  const panelRef = useTemplateRef<InstanceType<typeof ModelSelectorPanel>>('panelRef');
  const isExpanded = shallowRef(false);

  const { keyword, filteredModels, currentModel, resetKeyword } = useModelSelector({
    models: toRef(props, 'models'),
    selectedModel,
  });

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
      }) as InstanceType<typeof Tippy>['$props'],
  );

  const handleShow = () => {
    if (props.disabled || !props.models.length) {
      return false;
    }
    isExpanded.value = true;
    resetKeyword();
    // 展开后自动聚焦搜索框（设计稿 annotation）
    panelRef.value?.focusSearch();
  };
  const handleHidden = () => {
    isExpanded.value = false;
  };

  const handleSelect = (model: IModelOption) => {
    selectedModel.value = model.llm_name;
    emit('change', model);
    tippyRef.value?.hide?.();
  };
</script>
