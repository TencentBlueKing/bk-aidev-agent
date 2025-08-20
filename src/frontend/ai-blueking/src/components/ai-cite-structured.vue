<template>
  <section
    v-if="citeData"
    class="ai-cite-structured"
  >
    <div class="cite-container">
      <div
        class="cite-content"
        ref="contentRef"
        :class="{ expanded: expanded }"
      >
        <span class="title">{{ citeData.title }}</span>
        <div class="data-items">
          <div
            v-for="(item, index) in citeData.data"
            :key="index"
            class="data-item"
          >
            <span class="data-key">{{ item.key }}:</span>
            <span
              class="data-value"
              :class="{ truncated: !expanded && isOverflow }"
            >
              {{ item.value }}
            </span>
          </div>
        </div>
      </div>
      <div
        v-if="isOverflow"
        class="cite-footer"
        @click="toggleExpand"
      >
        <i
          class="bkai-icon bkai-angle-down"
          :class="{ 'bkai-angle-up': expanded }"
        />
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
  import { nextTick, onMounted, ref, watch } from 'vue';

  interface CitedData {
    key: string;
    value: string;
  }

  interface StructuredCite {
    type: 'structured';
    title: string;
    data: CitedData[];
  }

  const props = defineProps<{
    citeData: StructuredCite;
    showCloseIcon?: boolean;
  }>();

  defineEmits<{
    close: [];
  }>();

  const contentRef = ref<HTMLElement | null>(null);
  const isOverflow = ref(false);
  const expanded = ref(false);

  const checkOverflow = () => {
    if (contentRef.value) {
      isOverflow.value = contentRef.value.scrollHeight > 400;
    }
  };

  const toggleExpand = () => {
    expanded.value = !expanded.value;
  };

  onMounted(() => {
    nextTick(() => {
      checkOverflow();
    });
  });

  watch(
    () => props.citeData,
    () => {
      nextTick(() => {
        checkOverflow();
      });
    },
    { deep: true }
  );
</script>

<style lang="scss" scoped>
  .ai-cite-structured {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
    justify-content: center;
    user-select: none;
    margin-bottom: 8px;

    .cite-container {
      position: relative;
      max-width: 100%;
      background-color: #e1ecff;
      border-radius: 4px;
      overflow: hidden;
    }

    .cite-content {
      max-height: 400px;
      padding: 10px;
      overflow: hidden;
      transition: all 0.3s ease;

      &.expanded {
        max-height: none;
        overflow: visible;
      }

      .title {
        color: #3a84ff;
        line-height: 12px;
        font-weight: 700;
        font-size: 12px;
        margin-bottom: 8px;
        display: inline-block;
      }

      .data-item {
        display: flex;
        font-size: 12px;
        line-height: 20px;

        &:last-child {
          margin-bottom: 0;
        }

        .data-key {
          flex-shrink: 0;
          margin-right: 8px;
          font-weight: 700;
          color: #313238;
          min-width: fit-content;
        }

        .data-value {
          flex: 1;
          color: #313238;
          word-break: break-word;
          white-space: pre-wrap;

          &.truncated {
            display: -webkit-box;
            -webkit-line-clamp: 3;
            line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
            text-overflow: ellipsis;
          }
        }
      }
    }
  }

  // 滚动条样式
  .cite-content:not(.expanded) {
    &::-webkit-scrollbar {
      width: 4px;
    }

    &::-webkit-scrollbar-track {
      background: #f5f7fa;
      border-radius: 2px;
    }

    &::-webkit-scrollbar-thumb {
      background: #dcdee5;
      border-radius: 2px;

      &:hover {
        background: #c4c6cc;
      }
    }
  }

  .cite-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 24px;
    background-image: linear-gradient(180deg, #ffffff00 0%, #31323833 99%);
    border-radius: 0 0 6px 6px;
    cursor: pointer;
    transition: background-image 0.3s ease;

    &:hover {
      height: 24px;
      background-image: linear-gradient(180deg, #ffffff1a 0%, #3132384d 99%);
      border-radius: 0 0 6px 6px;
    }

    .bkai-icon {
      color: #979ba5;
      font-size: 14px;

      &.bkai-angle-up {
        transform: rotate(180deg);
      }
    }
  }
</style>
