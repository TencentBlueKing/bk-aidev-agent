<template>
  <Tippy
    ref="tippyRef"
    v-bind="innerTippyProps"
    @show="handleTippyShow"
  >
    <ToolBtn v-bind="toolBtnProps" />
    <template #content>
      <div class="ai-delete-confirm">
        <div class="ai-delete-confirm__title">{{ t('确认删除该回答？') }}</div>
        <div class="ai-delete-confirm__desc">{{ t('删除操作无法撤回，请谨慎操作！') }}</div>
        <div class="ai-delete-confirm__actions">
          <Button
            size="small"
            theme="danger"
            @click="handleConfirm"
          >
            {{ t('删除') }}
          </Button>
          <Button
            size="small"
            @click="handleCancel"
          >
            {{ t('取消') }}
          </Button>
        </div>
      </div>
    </template>
  </Tippy>
</template>

<script setup lang="ts">
  import { computed, onUnmounted, useTemplateRef } from 'vue';

  import { Button } from 'bkui-vue';
  import { type TippyOptions, Tippy, useTippy } from 'vue-tippy';

  import { t } from '../../../lang/lang';
  import ToolBtn from '../../ai-buttons/tool-btn/tool-btn.vue';

  import type { IToolBtn } from '../../../types';

  export type DeleteToolProps = IToolBtn & {
    disabled?: boolean;
    tippyOptions?: Partial<Omit<TippyOptions, 'getReferenceClientRect' | 'triggerTarget'>>;
  };

  const props = defineProps<
    IToolBtn & {
      disabled?: boolean;
      tippyOptions?: Partial<Omit<TippyOptions, 'getReferenceClientRect' | 'triggerTarget'>>;
    }
  >();
  const emit = defineEmits<{
    (e: 'confirm'): void;
    (e: 'cancel'): void;
  }>();

  const tippyRef = useTemplateRef<InstanceType<typeof Tippy> & ReturnType<typeof useTippy>>('tippyRef');

  const toolBtnProps = computed(() => ({
    id: props.id,
    name: props.name,
    description: props.description,
    disabled: props.disabled,
    tippyOptions: props.tippyOptions,
  }));

  const innerTippyProps = computed(
    () =>
      ({
        arrow: false,
        interactive: true,
        offset: [0, 6],
        theme: 'ai-chat-box-light light',
        trigger: 'click',
        appendTo: () => document.body,
        ...(props.tippyOptions || {}),
      }) as InstanceType<typeof Tippy>['$props'],
  );

  const handleTippyShow = () => {
    if (props.disabled) return false;
  };

  const hide = () => {
    tippyRef.value?.hide?.();
  };

  const handleConfirm = () => {
    hide();
    emit('confirm');
  };

  const handleCancel = () => {
    hide();
    emit('cancel');
  };

  onUnmounted(() => {
    hide();
  });
</script>

<style lang="scss">
  .ai-delete-confirm {
    width: 280px;
    padding: 16px;
    font-size: var(--ai-font-size, 12px);
    color: #4d4f56;
    background: #fff;
    border: 1px solid #dcdee5;
    box-shadow: 0 2px 6px 0 #0000001a;

    &__title {
      margin-bottom: 6px;
      font-size: 16px;
      font-weight: 600;
      line-height: 22px;
      color: #313238;
    }

    &__desc {
      margin-bottom: 16px;
      line-height: 20px;
    }

    &__actions {
      display: flex;
      gap: 8px;
      justify-content: flex-end;
    }
  }
</style>
