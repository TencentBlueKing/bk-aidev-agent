import { ref, computed } from 'vue';
import type { IShortcut } from '../types';
import BkForm from 'bkui-vue/lib/form';
import { t } from '../lang';

export const useCustomForm = (shortcut: IShortcut) => {
  const formRef = ref<InstanceType<typeof BkForm>>();

  // 表单数据
  const formData = ref<Record<string, any>[]>(
    shortcut.components.reduce(
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
    return shortcut.components.reduce(
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

  return {
    formRef,
    formData,
    modelFormData,
    formRules,
  };
};
