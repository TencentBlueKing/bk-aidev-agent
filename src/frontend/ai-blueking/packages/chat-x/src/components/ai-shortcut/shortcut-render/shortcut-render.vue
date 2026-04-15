<template>
  <div class="shortcut-render">
    <div class="shortcut-render-header">
      <ThinkingIcon class="header-icon" />
      <span class="header-name">{{ alias || name }}</span>
      <CloseIcon
        class="header-close"
        @click="handleClose"
      />
    </div>
    <div class="shortcut-render-content">
      <Form
        ref="formRef"
        class="shortcut-render-form"
        form-type="vertical"
        :model="localFormModel"
        :rules="rules"
      >
        <template
          v-for="(component, index) in components"
          :key="component.id"
        >
          <Form.FormItem
            v-bind="getFormItemProps(component)"
            class="shortcut-render-form-item"
            :style="{ gridColumn: getGridColumn(component, index) }"
          >
            <component :is="getComponent(component)" />
          </Form.FormItem>
        </template>
        <Form.FormItem class="shortcut-footer-item">
          <div class="shortcut-footer">
            <Button
              theme="primary"
              @click="handleSubmit"
            >
              {{ t('提交') }}
            </Button>
            <Button @click="handleCancel">
              {{ t('取消') }}
            </Button>
          </div>
        </Form.FormItem>
      </Form>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { h, reactive, shallowRef, useTemplateRef, watchEffect } from 'vue';

  import { Button, Checkbox, Form, Input, Radio, Select, Switcher } from 'bkui-vue';

  import { CloseIcon, ThinkingIcon } from '../../../icons';
  import { t } from '../../../lang/lang';

  import type { Shortcut, ShortcutComponent } from '../../../types';
  const props = defineProps<Partial<Shortcut>>();
  export type ShortcutRenderEmits = {
    (e: 'close'): void;
    (e: 'submit', formModel: Record<string, unknown>): void;
  };
  const emits = defineEmits<ShortcutRenderEmits>();
  const formRef = useTemplateRef<InstanceType<typeof Form>>('formRef');
  const localFormModel = reactive<Record<string, unknown>>({});
  const rules = shallowRef<Record<string, Record<string, unknown>>>({});
  watchEffect(() => {
    if (props.formModel) {
      for (const key in props.formModel) {
        localFormModel[key] = props.formModel[key];
      }
    }
    for (const component of props?.components ?? []) {
      if (component.key) {
        localFormModel[component.key] = component.default ?? component.props?.default ?? component.props?.modelValue;
      }
    }
  });

  const getGridColumn = (component: ShortcutComponent, index: number) => {
    if (component.type === 'textarea') return 'span 2';

    // 计算当前 item 之前所有 item 占用的总列数
    let usedColumns = 0;
    for (let i = 0; i < index; i++) {
      usedColumns += props.components?.[i]?.type === 'textarea' ? 2 : 1;
    }

    // 如果是最后一个 item 且它在新行开始（没有配对的 item），则独占一行
    const isLast = index === (props.components?.length ?? 0) - 1;
    if (isLast && usedColumns % 2 === 0) {
      return 'span 2';
    }

    return 'auto';
  };

  const getFormItemProps = (component: ShortcutComponent) => {
    return {
      ...component.formItemProps,
      property: component.key,
      label: component.name ?? component.formItemProps?.label,
      required: component.fillBack ?? component.formItemProps?.required,
    };
  };
  const getComponent = (component: ShortcutComponent) => {
    const { options: componentOptions, ...otherProps } = component?.props ?? {};
    const { options: oldOptions, ...oldProps } = component ?? {};
    const options = (componentOptions ?? oldOptions) as { label: string; value: string }[];
    const componentProps = {
      ...oldProps,
      ...otherProps,
      modelValue: localFormModel[component.key],
      onChange: (value: unknown) => {
        localFormModel[component.key] = value;
      },
      'onUpdate:modelValue': (value: unknown) => {
        localFormModel[component.key] = value;
      },
    } as Record<string, unknown>;
    switch (component.type) {
      case 'text':
      case 'input':
        return h(Input, componentProps);
      case 'textarea':
        return h(Input, {
          ...componentProps,
          type: 'textarea',
        });
      case 'number':
        return h(Input, {
          ...componentProps,
          type: 'number',
        });
      case 'select': {
        return h(
          Select,
          componentProps,
          options?.map(option =>
            h(Select.Option, {
              ...option,
            }),
          ),
        );
      }
      case 'checkboxGroup': {
        return h(
          Checkbox.Group,
          componentProps,
          options?.map(option =>
            h(Checkbox, {
              ...option,
            }),
          ),
        );
      }
      case 'radioGroup': {
        return h(
          Radio.Group,
          componentProps,
          options?.map(option =>
            h(Radio, {
              ...option,
            }),
          ),
        );
      }
      case 'switcher':
        return h(Switcher, componentProps);
      default:
        return null;
    }
  };
  const handleSubmit = async () => {
    if (!(await formRef.value?.validate?.().catch(() => false))) {
      return;
    }
    emits('submit', {
      ...localFormModel,
    });
  };
  const handleCancel = () => {
    emits('close');
  };
  const handleClose = () => {
    emits('close');
  };
</script>
<style lang="scss">
  @use '../../../styles/border.scss' as border;

  .shortcut-render {
    position: relative;
    display: flex;
    flex-direction: column;
    width: 100%;
    overflow: hidden;
    font-size: 12px;
    background: #fff;
    border-radius: 8px;

    &::before {
      @include border.linear-gradient-border(180deg, #6cbaff, #3a84ff);
    }

    &-header {
      display: flex;
      flex: 0 0 32px;
      align-items: center;
      height: 32px;
      padding: 0 12px;
      color: #313238;
      background: #f5f7fa;
      border-radius: 8px 8px 0 0;

      .header-icon {
        width: 16px;
        height: 16px;
        margin-right: 6px;
        font-size: 16px;
      }

      .header-close {
        width: 16px;
        height: 16px;
        margin-left: auto;
        font-size: 16px;
        color: #979ba5;

        &:hover {
          color: #3a84ff;
          cursor: pointer;
        }
      }

      .header-name {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    &-content {
      flex: 1;
      width: 100%;
      max-height: 424px;
      overflow-y: auto;
      border-radius: 0 0 8px 8px;

      .shortcut-render-form {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        column-gap: 12px;
        margin: 12px;
        margin-bottom: 0;

        .shortcut-footer-item {
          position: sticky;
          bottom: 1px;
          z-index: 0;
          grid-column: span 2;
          padding: 12px 11px;
          margin: 0 -11px;
          background: white;
          border-bottom-right-radius: 8px;
          border-bottom-left-radius: 8px;

          // box-shadow: 0 -2px 4px 0 rgb(0 0 0 / 5.9%);

          .shortcut-footer {
            display: flex;
            gap: 8px;
            justify-content: flex-end;
          }
        }

        .bk-form-label {
          font-size: 12px;
          color: #4d4f56;
        }

        .bk-form-item {
          margin-bottom: 16px;

          .bk-radio-label,
          .bk-checkbox-label {
            font-size: 12px;
          }

          &:last-child {
            margin-bottom: 0;
          }
        }
      }
    }
  }
</style>
