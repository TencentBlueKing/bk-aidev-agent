import { ref, computed, type Ref, watch } from 'vue';
import type { IShortcut, IShortcutComponent } from '../types';
import BkForm from 'bkui-vue/lib/form';
import { t } from '../lang';

export const useCustomForm = (shortcut: Ref<IShortcut>) => {
  const formRef = ref<InstanceType<typeof BkForm>>();

  // 表单数据
  const formData = ref<Record<string, any>[]>(
    shortcut.value.components.reduce(
      (data, item) => {
        data.push({
          [item.key]: item.selectedText || item.default || '',
          context_type: item.type,
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

  // 表单验证规则
  const formRules = computed(() => {
    return shortcut.value.components.reduce(
      (acc, item) => {
        if (item.required) {
          acc[item.key] = [
            {
              required: true,
              message: t('请输入内容'),
              trigger: item.type === 'select' ? 'change' : 'blur',
            },
          ];
        }
        return acc;
      },
      {} as Record<string, any>
    );
  });

  // 根据 component 更新 formData
  const updateFormData = (component: IShortcutComponent) => {
    const key = component.key;
    const index = formData.value.findIndex(item => item[key]);
    if (index !== -1) {
      formData.value[index][key] = component.selectedText || component.default || '';
    }
  };

  watch(
    () => shortcut.value.components,
    (val) => {
      const updatedComponent = val.find(item => item.selectedText);
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
