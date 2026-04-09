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
          <span :class="`mark-${groupItems.type}`"></span>
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
  import { ref as deepRef, shallowRef, useTemplateRef, watchEffect } from 'vue';

  import { useMenuKeydown } from '../../../../composables/use-menu-keydown';
  import { OverflowTips as vOverflowTips } from '../../../../directives';
  import { type IAiSlashGroupItem, type IAiSlashMenuItem, type ResourceType, resourceTypeMap } from '../../../../types';
  const props = defineProps<{
    onSelect: (item: IAiSlashMenuItem) => void;
    resourceList?: IAiSlashMenuItem[];
  }>();

  const menuRef = useTemplateRef<HTMLElement>('menuRef');

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
  @use 'sass:list';
  @use '../../../../styles/variables.scss' as variables;

  .ai-slash-menu {
    width: 260px;
    max-height: 200px;
    overflow-y: auto;
    font-size: 12px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
    box-shadow: 0 2px 6px 0 #0000001a;

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

      @each $type, $color in variables.$resourceTypeMap {
        .mark-#{$type} {
          display: flex;
          flex: 0 0 10px;
          width: 10px;
          height: 10px;
          margin-right: 6px;
          background-color: list.nth($color, 3);
          border-radius: 2px;
        }
      }

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
        padding: 0 16px 0 32px;
        color: #4d4f56;
        cursor: pointer;

        &.is-active,
        &:hover {
          background-color: #f5f7fa;
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
