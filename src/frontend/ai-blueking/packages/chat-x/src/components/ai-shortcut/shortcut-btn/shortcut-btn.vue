<template>
  <button
    ref="el"
    class="ai-shortcut-btn"
    :class="{ 'is-menu-mode': mode === 'menu' }"
    @click="handleSelectShortcut(shortcut)"
  >
    <slot name="default">
      <template v-if="shortcut?.icon">
        <template v-if="typeof shortcut.icon === 'string'">
          <template v-if="shortcut.icon.startsWith('http')">
            <img
              v-if="!imgError"
              class="ai-common-icon ai-shortcut-btn-icon"
              :src="shortcut.icon"
              @error="imgError = true"
            />
            <AgentIcon
              v-else
              class="ai-shortcut-btn-icon"
            />
          </template>
          <span
            v-else
            :class="shortcut.icon"
          />
        </template>
        <component
          :is="typeof shortcut?.icon === 'function' ? shortcut.icon?.(h) : shortcut.icon"
          v-else
          class="ai-shortcut-btn-icon"
        />
      </template>
      <template v-else-if="shortcut && !shortcut.components?.length">
        <AgentIcon class="ai-shortcut-btn-icon" />
      </template>
      {{ shortcut?.alias || shortcut?.name }}
    </slot>
    <slot name="append" />
  </button>
</template>

<script setup lang="ts">
  import { h, shallowRef, useTemplateRef, watch } from 'vue';

  import { AgentIcon } from '../../../icons';

  import type { Shortcut } from '../../../types';

  const props = defineProps<{
    mode?: 'btn' | 'menu';
    shortcut?: Shortcut;
  }>();

  const imgError = shallowRef(false);

  const emits = defineEmits<{
    (e: 'click', shortcut?: Shortcut): void;
  }>();
  watch(
    () => props.shortcut?.icon,
    () => {
      imgError.value = false;
    },
    { immediate: true },
  );
  const handleSelectShortcut = (shortcut?: Shortcut) => {
    emits('click', shortcut);
  };
  const el = useTemplateRef<HTMLElement>('el');
  defineExpose({
    get $el() {
      return el.value;
    },
  });
</script>
<style lang="scss">
  .ai-shortcut-btn {
    display: flex;
    gap: 4px;
    align-items: center;
    justify-content: center;
    height: 28px;
    padding: 0 4px;
    font-size: 12px;
    color: #313238;
    white-space: nowrap;
    background: transparent;
    border: none;
    border-radius: 4px;
    transition: background-color 0.2s;

    &.is-menu-mode {
      display: flex;
      flex: 0 0 32px;
      align-items: center;
      justify-content: flex-start;
      width: 100%;
      height: 32px;
      padding: 0 12px;
      border-radius: 0;

      &:hover {
        cursor: pointer;
        background-color: #f5f7fa;
      }

      .shortcut-btn-icon {
        display: flex;
        flex: 0 0 14px;
        align-items: center;

        // margin-right: 6px;
        font-size: 14px;
        color: #4d4f56;
      }
    }

    &-icon {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      font-size: 16px;
      color: #979ba5;
    }

    &:hover {
      cursor: pointer;
      cursor: default;
      background: #f0f1f5;

      .shortcut-btn-icon {
        color: #4d4f56;
      }

      .ai-close-icon {
        cursor: pointer;
      }
    }
  }
</style>
