<template>
  <div :class="rootElementClass">
    <div class="header">
      <component
        :is="props.shortcut.iconRender ? props.shortcut.iconRender(h) : null"
        v-if="props.shortcut.iconRender"
      />
      <i
        v-else-if="props.shortcut.icon"
        class="bkai-icon"
        :class="props.shortcut.icon"
      />
      <span>{{ props.shortcut.alias || props.shortcut.name }}</span>
    </div>
    <bk-form
      ref="formRef"
      class="form-container"
      form-type="vertical"
      :model="modelFormData"
      :rules="formRules"
    >
      <template
        v-for="(componentItem, index) in visibleComponents"
        :key="componentItem.key"
      >
        <bk-form-item
          error-display-type="tooltips"
          error-tip-append-to-parent
          :label="componentItem.name"
          :property="componentItem.key"
          :required="componentItem.required"
          :class="{
            'full-width':
              componentItem.type === 'textarea' || isLastInOddGroup(visibleComponents, index),
            'with-send-button': componentItem.showSendButton,
          }"
        >
          <component
            :is="getComponent(componentItem.type)"
            :id="componentItem.key"
            v-model="formData[getOriginalIndex(componentItem)][componentItem.key]"
            v-bind="componentItem"
            :popover-options="{
              boundary: props.rootNode || 'parent',
            }"
            @enter="() => handleComponentSend(componentItem)"
          />
          <!-- @since v1.2.9 -->
          <template v-if="componentItem.showSendButton">
            <span
              :class="[
                'send-button',
                { disabled: !formData[getOriginalIndex(componentItem)][componentItem.key] },
              ]"
              @click="() => handleComponentSend(componentItem)"
            >
              <i class="bkai-icon bkai-fasong"></i>
            </span>
          </template>
        </bk-form-item>
      </template>
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
  import { toRef, onMounted, computed, h } from 'vue';

  import { useCustomForm } from '../../composables/use-custom-form';
  import { t } from '../../lang';
  import type { IShortcut, IShortcutComponent } from '../../types';

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

  const getComponent = (type: string) => {
    if (!type) return FormInput; // 默认返回 FormInput
    return componentMap[type as keyof typeof componentMap] || FormInput;
  };

  const shortCutRef = toRef(props, 'shortcut');

  const { formRef, formData, modelFormData, formRules } = useCustomForm(shortCutRef);

  /**
   * 计算根元素的 class
   * @since v1.2.9
   */
  const rootElementClass = computed(() => {
    return [
      'custom-input-wrapper',
      shortCutRef.value.mode ?? 'advanced',
      shortCutRef.value.hideFooter ? 'no-footer' : '',
    ];
  });

  // 计算可见组件（过滤掉隐藏的组件）
  const visibleComponents = computed(() => {
    return (props.shortcut.components || [])
      .map((component, originalIndex) => ({
        ...component,
        // 保存原始索引，用于 formData 映射
        __originalIndex: originalIndex,
        // 确保 placeholder 和 options 有默认值
        placeholder: component.placeholder === null ? undefined : component.placeholder,
        options: component.options || [],
      }))
      .filter(component => {
        // 使用类型断言确保 component 有 hide 属性
        const item = component as IShortcutComponent;
        return !item.hide;
      });
  });

  // 获取原始索引（用于 formData 的正确映射）
  const getOriginalIndex = (component: any) => {
    // 现在从组件对象中直接获取保存的原始索引
    return component.__originalIndex ?? 0;
  };

  // Layout 辅助函数：判断是否为奇数组的最后一个
  const isLastInOddGroup = (components: IAgentCommandComponent[], currentIndex: number) => {
    // 处理空数组或无效索引的情况
    if (!components || currentIndex < 0 || currentIndex >= components.length) return false;

    // 确保当前元素存在
    if (!components[currentIndex]) return false;

    // 跳过 textarea 类型
    if (components[currentIndex].type === 'textarea') return false;

    // 向前查找连续的非 textarea 数量
    let count = 0;
    for (let i = currentIndex; i >= 0; i--) {
      // 确保元素存在
      if (!components[i] || components[i].type === 'textarea') break;
      count++;
    }

    // 如果是连续非 textarea 的奇数位置且是最后一个
    return (
      count % 2 === 1 &&
      (currentIndex === components.length - 1 ||
        (components[currentIndex + 1] && components[currentIndex + 1].type === 'textarea'))
    );
  };

  // 提交表单
  const handleSubmit = () => {
    formRef.value?.validate().then(() => {
      // 处理表单数据的辅助函数
      const processFormData = (data: Record<string, any>[]) => {
        return data.map(item => ({
          ...item,
          __value: item && item.__key ? item[item.__key] : undefined,
        }));
      };

      // 过滤掉隐藏字段的辅助函数
      const filterVisibleFormData = (data: Record<string, any>[]) => {
        return data.filter(item => {
          const key = Object.keys(item).find(k => !k.startsWith('__'));
          if (!key) return false;
          const component = props.shortcut.components?.find(
            c => c.key === key
          ) as IShortcutComponent;
          return component && !component.hide;
        });
      };

      // 过滤掉隐藏字段
      const visibleFormData = filterVisibleFormData(formData.value);

      emit('submit', {
        shortcut: props.shortcut,
        // 传递完整的 formData 给后端
        formData: processFormData(formData.value),
        // 仅用于 cite 显示的过滤数据
        citeFormData: processFormData(visibleFormData),
      });
    });
  };

  /**
   * 单个指令提交
   * @since v1.2.9
   * @param componentItem
   */
  const handleComponentSend = (componentItem: IAgentCommandComponent) => {
    const componentValue = formData.value[getOriginalIndex(componentItem)]?.[componentItem.key];
    if (!componentItem.showSendButton || !componentValue) {
      return;
    }

    handleSubmit();
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

    /**
     * 带发送按钮的输入模块样式
     * @since v1.2.9
     */
    :deep(.with-send-button .bk-form-content),
    :deep(.with-send-button .ai-blueking-form-content) {
      position: relative;

      .bk-ai-custom-input {
        padding-right: 24px;
      }

      .send-button {
        position: absolute;
        right: 4px;
        bottom: 4px;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;

        /* width: 24px; */
        padding: 0 4px;
        height: 24px;
        border-radius: 4px;

        display: flex;
        align-items: center;
        justify-content: center;

        color: #fff;
        background: #3a84ff;

        &.disabled {
          cursor: not-allowed;
          background: #f0f1f5;

          .bkai-icon {
            color: #c4c6cc;
          }
        }

        .bkai-icon {
          font-size: 14px;
          margin-right: 0;
          color: #fff;
        }
      }
    }

    /**
     * 隐藏底部按钮区域
     * @since v1.2.9
     */
    &.no-footer {
      .footer {
        display: none;
      }

      :deep(.bk-form-item:last-child),
      :deep(.ai-blueking-form-item:last-child) {
        margin-bottom: 0;
      }
    }

    /**
     * simple 模式样式
     * @since v1.2.9
     */
    &.simple {
      background: none;
      border-radius: 0;
      border: none;

      .header {
        display: none;
      }

      :deep(.bk-form.form-container),
      :deep(.ai-blueking-form.form-container) {
        padding: 0;
      }

      :deep(.bk-form-item .bk-form-label),
      :deep(.ai-blueking-form-item .ai-blueking-form-label) {
        display: none;
      }
    }
  }
</style>
