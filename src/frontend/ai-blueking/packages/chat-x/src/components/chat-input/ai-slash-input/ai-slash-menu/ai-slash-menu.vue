<template>
  <div
    v-if="resourceList?.length"
    ref="menuRef"
    class="ai-slash-menu"
  >
    <template v-for="(groupItems, index) in menuList">
      <div
        v-if="groupItems.items.length > 0"
        :key="index"
        class="ai-slash-group"
      >
        <div class="ai-slash-item ai-slash-group-title">
          <svg
            class="title-icon"
            :style="{
              transform: expandList.includes(groupItems.type) ? 'rotate(90deg)' : 'rotate(0deg)',
            }"
            viewBox="0 0 1024 1024"
            @click="toggleCollapse(groupItems)"
          >
            <path d="M800 512L288 928V96z"></path>
          </svg>
          {{ groupItems.name }}
          ({{ groupItems.items.length }})
        </div>
        <template v-if="expandList.includes(groupItems.type)">
          <div
            v-for="item in groupItems.items"
            :key="item.id"
            class="ai-slash-item ai-slash-group-item"
            :class="{ 'is-active': sortedResourceList?.[activeIndex]?.id === item.id }"
            @click="onSelect(item)"
          >
            <img
              v-if="item.icon && !failedIcons.has(String(item.id))"
              :src="item.icon"
              alt=""
              class="ai-slash-group-item-icon"
              @error="failedIcons.add(String(item.id))"
            />
            <div
              v-else
              class="ai-slash-group-item-icon ai-slash-group-item-icon--fallback"
            >
              {{ item.name?.[0]?.toUpperCase() }}
            </div>
            <span
              v-overflow-tips="{
                text: item.name,
                zIndex: 9999999,
                placement: 'right-start',
                theme: 'ai-slash-editor-overflow-tips-theme',
              }"
              class="ellipsis-text"
              :title="item.name"
            >
              {{ item.name }}
            </span>
          </div>
        </template>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { reactive, ref as deepRef, shallowRef, useTemplateRef, watchEffect } from 'vue';

  import { useMenuKeydown } from '../../../../composables/use-menu-keydown';
  import { OverflowTips as vOverflowTips } from '../../../../directives';
  import { type IAiSlashGroupItem, type IAiSlashMenuItem, type ResourceType, resourceTypeMap } from '../../../../types';
  const props = defineProps<{
    onSelect: (item: IAiSlashMenuItem) => void;
    resourceList?: IAiSlashMenuItem[];
  }>();

  const menuRef = useTemplateRef<HTMLElement>('menuRef');
  const failedIcons = reactive(new Set<string>());

  const expandList = deepRef<ResourceType[]>(['tool', 'shortcut', 'doc', 'knowledgebase', 'mcp'] as ResourceType[]);
  const sortedResourceList = shallowRef<IAiSlashMenuItem[]>([]);

  const menuList = shallowRef<IAiSlashGroupItem[]>([]);

  const { activeIndex } = useMenuKeydown<IAiSlashMenuItem>({
    items: sortedResourceList,
    onSelect: props.onSelect,
    menuRef: menuRef,
  });

  watchEffect(() => {
    const list: IAiSlashGroupItem[] = [];
    const sortedList: IAiSlashMenuItem[] = [];
    for (const [key, name] of Object.entries(resourceTypeMap)) {
      const items = props.resourceList?.filter(item => item.type === key) ?? [];
      if (items.length > 0) {
        list.push({
          type: key as ResourceType,
          name: name,
          isExpand: false,
          items: items || [],
        });
        sortedList.push(...items);
      }
    }
    activeIndex.value = 0;
    sortedResourceList.value = sortedList;
    menuList.value = list;
  });

  const toggleCollapse = (groupItems: IAiSlashGroupItem) => {
    const index = expandList.value.findIndex(type => type === groupItems.type);
    if (index !== -1) {
      expandList.value.splice(index, 1);
    } else {
      expandList.value.push(groupItems.type);
    }
  };
</script>
<style lang="scss">
  .ai-slash-menu {
    box-sizing: border-box;
    width: 100%;
    // 最多展示 10 个选项（每项 32px），超出再滚动
    max-height: 320px;
    overflow: hidden auto;
    font-size: var(--ai-font-size, 12px);
    background: #fff;
    border: 0;
    border-radius: 8px; // 与聊天输入框一致
    outline: none;
    box-shadow: none; // 外阴影由 tippy-box 承担，避免被裁切
    scrollbar-color: #dcdee5 transparent;
    scrollbar-width: thin;

    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-track {
      background: transparent;
    }

    &::-webkit-scrollbar-thumb {
      background: #dcdee5;
      border-radius: 2px;

      &:hover {
        background: #c4c6cc;
      }
    }

    .ai-slash-item {
      display: flex;
      flex: 0 0 32px;
      flex-wrap: nowrap;
      align-items: center;
      width: 100%;
      height: 32px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;

      .ellipsis-text {
        flex: 1;
        width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }

    .ai-slash-group {
      display: flex;
      flex-direction: column;
      color: #979ba5;

      .ai-slash-group-title {
        .title-icon {
          display: flex;
          flex: 0 0 12px;
          align-items: center;
          justify-content: center;
          width: 12px;
          height: 12px;
          margin-right: 4px;
          margin-left: 8px;
          fill: #979ba5;
          transform: rotate(0deg);
          transition: transform 0.2s ease-in-out;

          &:hover {
            cursor: pointer;
            fill: #3a84ff;
          }

          &.is-expand {
            transform: rotate(90deg);
          }
        }
      }

      .ai-slash-group-item {
        width: 100%;
        padding: 0 16px 0 24px;
        color: #4d4f56;
        cursor: pointer;

        &.is-active,
        &:hover {
          background-color: #f5f7fa;
        }

        &-icon {
          flex-shrink: 0;
          width: 20px;
          height: 20px;
          margin-right: 8px;
          object-fit: contain;
          border-radius: 2px;

          &--fallback {
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: var(--ai-font-size, 12px);
            font-weight: 700;
            line-height: var(--ai-line-height-compact, 20px);
            color: #fff;
            background: #3a84ff;
            border-radius: 2px;
          }
        }
      }
    }
  }

  .tippy-box[data-theme~='ai-slash-editor-overflow-tips-theme'] {
    .tippy-content {
      font-size: 12px;
    }
  }
</style>
