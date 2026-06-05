<template>
  <div
    ref="skillListRef"
    class="ai-skill-list"
  >
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
        <div
          v-if="skill.description"
          class="ai-skill-list-item-desc"
        >
          {{ skill.description }}
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
    width: 330px;
    max-height: 258px;
    padding: 8px;
    overflow-y: auto;
    font-size: 12px;
    color: #4d4f56;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    box-shadow: 0 2px 6px 0 #0000001a;

    .ai-skill-list-item {
      display: flex;
      align-items: flex-start;
      width: 100%;
      padding: 8px 10px;
      margin-bottom: 4px;
      cursor: pointer;
      background-color: #f5f7fa;
      border-radius: 2px;

      &:last-child {
        margin-bottom: 0;
      }

      &:hover {
        background-color: #eaebf0;
      }

      &.is-active {
        background-color: #eaebf0;
      }

      &-icon {
        flex-shrink: 0;
        width: 20px;
        height: 20px;
        margin-top: 1px;
        margin-right: 8px;
        object-fit: contain;
        border-radius: 2px;

        &--fallback {
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 12px;
          font-weight: 700;
          line-height: 20px;
          color: #fff;
          background: #3a84ff;
          border-radius: 2px;
        }
      }

      &-info {
        display: flex;
        flex: 1;
        flex-direction: column;
        min-width: 0;
      }

      &-name {
        line-height: 20px;
        color: #313238;
      }

      &-desc {
        display: -webkit-box;
        overflow: hidden;
        line-height: 18px;
        color: #979ba5;
        text-overflow: ellipsis;
        -webkit-box-orient: vertical;
        -webkit-line-clamp: 2;
      }
    }
  }
</style>
