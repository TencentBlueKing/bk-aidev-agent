import type { IAgentCommandComponent } from '@blueking/ai-ui-sdk/types';
import BkForm from 'bkui-vue/lib/form';
import { ref, computed, type Ref, watch } from 'vue';

import { t } from '../lang';
import type { IShortcut, IShortcutComponent, FormRule, ValidationStrategy } from '../types';

export const useCustomForm = (shortcut: Ref<IShortcut>) => {
  const formRef = ref<InstanceType<typeof BkForm>>();

  // 表单数据
  const formData = ref<Record<string, any>[]>(
    (shortcut.value.components || []).reduce(
      (data, item) => {
        // 为 IAgentCommandComponent 添加 selectedText 属性的兼容处理
        const selectedItem = item as IAgentCommandComponent & { selectedText?: string };
        data.push({
          [item.key]: selectedItem.selectedText || item.default || '',
          context_type: item.type,
          __label: item.name,
          __key: item.key,
        });
        return data;
      },
      [] as Record<string, any>[]
    )
  );

  // 用于绑定 model 的表单数据
  const modelFormData = computed(() => {
    return formData.value.reduce(
      (acc, item) => {
        Object.entries(item).forEach(([key, value]) => {
          acc[key] = value;
        });
        return acc;
      },
      {} as Record<string, any>
    );
  });

  // 必填验证策略
  const requiredValidation: ValidationStrategy = component => {
    if (component.required) {
      return {
        required: true,
        message: t('请输入内容'),
        trigger: component.type === 'select' ? 'change' : 'blur',
      };
    }
    return null;
  };

  // 数字类型验证策略
  const numberTypeValidation: ValidationStrategy = component => {
    if (component.type === 'number') {
      return {
        message: t('请输入数字'),
        trigger: 'blur',
      };
    }
    return null;
  };

  // 最小值验证策略
  const minValidation: ValidationStrategy = component => {
    if (component.type === 'number' && typeof component.min === 'number') {
      // 使用类型断言确保 TypeScript 知道 component.min 是一个数字
      const min = component.min as number;
      return {
        validator: (value: number) => value >= min,
        message: `${t('数值不能小于')} ${min}`,
        trigger: 'blur',
      };
    }
    return null;
  };

  // 最大值验证策略
  const maxValidation: ValidationStrategy = component => {
    if (component.type === 'number' && typeof component.max === 'number') {
      // 使用类型断言确保 TypeScript 知道 component.max 是一个数字
      const max = component.max as number;
      return {
        validator: (value: number) => value <= max,
        message: `${t('数值不能大于')} ${max}`,
        trigger: 'blur',
      };
    }
    return null;
  };

  // 验证策略注册表
  const validationStrategies: ValidationStrategy[] = [
    requiredValidation,
    numberTypeValidation,
    minValidation,
    maxValidation,
  ];

  // 表单验证规则
  const formRules = computed(() => {
    return (shortcut.value.components || []).reduce(
      (acc, item) => {
        const rules: FormRule[] = [];

        // 应用所有验证策略
        validationStrategies.forEach(strategy => {
          const result = strategy(item as IShortcutComponent);
          if (result) {
            if (Array.isArray(result)) {
              rules.push(...result);
            } else {
              rules.push(result);
            }
          }
        });

        if (rules.length > 0) {
          acc[item.key] = rules;
        }

        return acc;
      },
      {} as Record<string, FormRule[]>
    );
  });

  // 根据 component 更新 formData
  const updateFormData = (component: IAgentCommandComponent) => {
    const key = component.key;
    const index = formData.value.findIndex(item => item[key]);
    if (index !== -1) {
      // 为 IAgentCommandComponent 添加 selectedText 属性的兼容处理
      const selectedItem = component as IAgentCommandComponent & { selectedText?: string };
      formData.value[index][key] = selectedItem.selectedText || component.default || '';
    }
  };

  watch(
    () => shortcut.value.components,
    val => {
      // 为 IAgentCommandComponent 添加 selectedText 属性的兼容处理
      const updatedComponent = (val || []).find(item => {
        const selectedItem = item as IAgentCommandComponent & { selectedText?: string };
        return selectedItem.selectedText;
      });
      if (updatedComponent) {
        updateFormData(updatedComponent);
      }
    },
    { deep: true, immediate: true }
  );

  return {
    formRef,
    formData,
    modelFormData,
    formRules,
    updateFormData,
  };
};
