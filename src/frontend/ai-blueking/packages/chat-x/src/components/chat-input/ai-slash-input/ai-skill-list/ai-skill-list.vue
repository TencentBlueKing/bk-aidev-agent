<template>
  <div
    ref="skillListRef"
    class="ai-skill-list"
  >
    <div class="ai-skill-list-title">Skill（{{ skills.length }}）</div>
    <div
      v-for="(skill, index) in skills"
      :key="skill.skill_code"
      class="ai-skill-list-item"
      :class="{ 'is-active': activeIndex === index }"
      @click="onSelect(skill)"
    >
      <img
        v-if="skill.icon && !failedIcons.has(skill.skill_code)"
        :src="skill.icon"
        alt=""
        class="ai-skill-list-item-icon"
        @error="failedIcons.add(skill.skill_code)"
      />
      <div
        v-else
        class="ai-skill-list-item-icon ai-skill-list-item-icon--fallback"
      >
        {{ skill.skill_name?.[0]?.toUpperCase() }}
      </div>
      <div class="ai-skill-list-item-info">
        <div class="ai-skill-list-item-name">
          {{ skill.skill_name }}
        </div>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, reactive, useTemplateRef, watchEffect } from 'vue';

  import { useMenuKeydown } from '../../../../composables/use-menu-keydown';

  import type { ISkillListItem } from '../../../../types/editor';

  const props = defineProps<{
    onSelect: (skill: ISkillListItem) => void;
    skills: ISkillListItem[];
  }>();

  const failedIcons = reactive(new Set<string>());

  const skillListRef = useTemplateRef<HTMLElement>('skillListRef');
  const { activeIndex } = useMenuKeydown<ISkillListItem>({
    items: computed(() => props.skills),
    onSelect: props.onSelect,
    menuRef: skillListRef,
  });

  watchEffect(() => {
    props.skills;
    activeIndex.value = 0;
  });
</script>
<style lang="scss">
  .ai-skill-list {
    display: flex;
    flex-direction: column;
    box-sizing: border-box;
    width: 100%;
    max-height: 320px; // 与 @ 菜单一致：10 * 32px
    padding: 4px 0;
    overflow: hidden auto;
    font-size: var(--ai-font-size, 12px);
    color: #4d4f56;
    background: #fff;
    border: 0;
    border-radius: 8px;
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

    .ai-skill-list-title {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      height: 32px;
      padding: 0 10px;
      color: #979ba5; // 与 @ 菜单分组标题一致
      white-space: nowrap;
    }

    .ai-skill-list-item {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      box-sizing: border-box;
      width: 100%;
      height: 32px;
      padding: 0 10px;
      cursor: pointer;
      background-color: transparent;
      border-radius: 2px;

      &:hover {
        background-color: #e1ecff;
      }

      &.is-active {
        background-color: #f5f7fa;
      }

      &-icon {
        flex-shrink: 0;
        width: 20px;
        height: 20px;
        margin-right: 8px;
        object-fit: contain;
        border-radius: 2px; // 与 @ 菜单 / MCP 等资源图标一致，用方形

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

      &-info {
        display: flex;
        flex: 1;
        align-items: flex-start;
        min-width: 0;
      }

      &-name {
        overflow: hidden;
        line-height: 20px;
        color: #313238;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
    }
  }
</style>
