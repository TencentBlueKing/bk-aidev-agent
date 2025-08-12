<template>
  <div class="custom-input-wrapper">
    <div class="header">
      <i
        class="bkai-icon"
        :class="props.shortcut.icon"
      />
      <span>{{ props.shortcut.name }}</span>
    </div>
    <bk-form
      ref="formRef"
      class="form-container"
      form-type="vertical"
      :model="modelFormData"
      :rules="formRules"
    >
      <bk-form-item
        v-for="(item, index) in props.shortcut.components || []"
        :key="item.key"
        error-display-type="tooltips"
        :label="item.name"
        :property="item.key"
        :required="item.required"
        error-tip-append-to-parent
        :class="{
          'full-width':
            item.type === 'textarea' || isLastInOddGroup(props.shortcut.components || [], index),
        }"
      >
        <component
          :is="getComponent(item.type)"
          :id="item.key"
          v-model="formData[index][item.key]"
          v-bind="{
            ...item,
            placeholder: item.placeholder === null ? undefined : item.placeholder,
            options: item.options || [],
          }"
          :popover-options="{
            boundary: props.rootNode || 'parent',
          }"
        />
      </bk-form-item>
    </bk-form>
    <div class="footer">
      <bk-button
        theme="primary"
        @click="handleSubmit"
      >
        {{ t('提交') }}
      </bk-button>
      <bk-button @click="handleCancel">{{ t('取消') }}</bk-button>
    </div>
  </div>
</template>

<script setup lang="ts">
  import type { IAgentCommandComponent } from '@blueking/ai-ui-sdk/types';
  import { Button as BkButton } from 'bkui-vue';
  import BkForm from 'bkui-vue/lib/form';
  import { BkFormItem } from 'bkui-vue/lib/form';
  import { toRef, onMounted } from 'vue';

  import { useCustomForm } from '../../composables/use-custom-form';
  import { t } from '../../lang';
  import type { IShortcut } from '../../types';

  import FormInput from './form-input.vue';
  import FormSelect from './form-select.vue';

  const props = defineProps<{
    shortcut: IShortcut;
    rootNode: HTMLElement | undefined;
  }>();

  const emit = defineEmits(['submit', 'cancel']);

  // 动态组件映射
  const componentMap = {
    text: FormInput,
    number: FormInput,
    textarea: FormInput,
    select: FormSelect,
  };

  const getComponent = (type: string) => componentMap[type as keyof typeof componentMap];

  const shortCutRef = toRef(props, 'shortcut');

  const { formRef, formData, modelFormData, formRules } = useCustomForm(shortCutRef);

  // Layout 辅助函数：判断是否为奇数组的最后一个
  const isLastInOddGroup = (components: IAgentCommandComponent[], currentIndex: number) => {
    // 处理空数组或无效索引的情况
    if (!components || currentIndex < 0 || currentIndex >= components.length) return false;

    // 跳过 textarea 类型
    if (components[currentIndex].type === 'textarea') return false;

    // 向前查找连续的非 textarea 数量
    let count = 0;
    for (let i = currentIndex; i >= 0; i--) {
      if (components[i].type === 'textarea') break;
      count++;
    }

    // 如果是连续非 textarea 的奇数位置且是最后一个
    return (
      count % 2 === 1 &&
      (currentIndex === components.length - 1 || components[currentIndex + 1].type === 'textarea')
    );
  };

  // 提交表单
  const handleSubmit = () => {
    formRef.value?.validate().then(() => {
      emit('submit', {
        shortcut: props.shortcut,
        formData: formData.value.map(item => ({
          ...item,
          __value: item[item.__key],
        })),
      });
    });
  };

  // 取消表单
  const handleCancel = () => {
    emit('cancel');
  };

  onMounted(() => {
    // 只有来自 popup 的快捷方式才能自动提交
    const actualShortcut = props.shortcut;
    if ((actualShortcut as any).autoSubmit) {
      handleSubmit();
    }
    // 注意：来自 main 的快捷方式（chat-input-box）永远不允许自动提交
    // 即使表单只有一项且有默认值，也禁止自动提交
  });
</script>

<style scoped>
  .custom-input-wrapper {
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background:
      linear-gradient(#fff, #fff) padding-box,
      linear-gradient(180deg, #6cbaff, #3a84ff) border-box;
    border: 1px solid transparent;
    border-radius: 8px;
    .header {
      height: 32px;
      background: #f5f7fa;
      border-radius: 8px 8px 0 0;
      display: flex;
      align-items: center;
      gap: 6px;
      padding: 0 8px;
      color: #313238;
      font-size: 12px;
      .bkai-icon {
        font-size: 12px;
        margin-right: 0;
      }
    }
    .form-container {
      max-height: 424px;
      overflow-y: auto;
      padding: 12px;
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;

      :deep(.ai-blueking-form-label, .bk-form-label) {
        font-size: 12px;
      }
    }
    .footer {
      display: flex;
      justify-content: flex-end;
      gap: 12px;
      padding: 0 12px 12px 12px;
    }

    :deep(.ai-blueking-form-item, .bk-form-item) {
      margin-bottom: 0;
    }

    :deep(.full-width) {
      grid-column: 1 / -1;
    }
  }
</style>
