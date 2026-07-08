<template>
  <div
    v-if="hasArgs"
    class="ai-tool-approval-args"
  >
    <!-- 参数标题：文件图标 + 「参数：」 -->
    <div class="ai-tool-approval-args-header">
      <ToolApprovalArgsIcon class="ai-tool-approval-args-header-icon" />
      <span class="ai-tool-approval-args-header-label">{{ t('参数') }}：</span>
    </div>

    <!-- 参数内容：格式化 JSON，默认最多 3 行，超出后可展开/收起 -->
    <div class="ai-tool-approval-args-body">
      <pre
        ref="codeRef"
        class="ai-tool-approval-args-code"
        :class="{ 'is-collapsed': isCollapsed, 'is-expanded': isExpanded }"
        v-text="formattedArgs"
      />
      <div
        v-if="hasOverflow"
        class="ai-tool-approval-args-toggle"
        @click="toggle"
      >
        <span class="ai-tool-approval-args-toggle-text">{{ expanded ? t('收起') : t('展开更多') }}</span>
        <ArrowLeftIcon
          class="ai-tool-approval-args-toggle-icon"
          :class="{ 'is-expanded': expanded }"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed, onBeforeUnmount, onMounted, shallowRef, useTemplateRef, watch } from 'vue';

  import { ArrowLeftIcon, ToolApprovalArgsIcon } from '../../../icons';
  import { t } from '../../../lang/lang';

  // 折叠态最多显示 3 行，行高固定 18px，故折叠高度阈值为 3 * 18 = 54px
  const COLLAPSED_MAX_HEIGHT = 90;

  const props = defineProps<{
    // 工具参数，来源于中断 metadata.toolArgs
    toolArgs?: Record<string, unknown>;
  }>();

  const codeRef = useTemplateRef<HTMLElement>('codeRef');
  // 用户是否点击展开
  const expanded = shallowRef(false);
  // 内容是否超过 3 行（超出才需要展开/收起）
  const hasOverflow = shallowRef(false);

  const hasArgs = computed(() => !!props.toolArgs && Object.keys(props.toolArgs).length > 0);
  // 参数以两空格缩进的 JSON 美化展示，异常兜底为空串
  const formattedArgs = computed(() => {
    if (!hasArgs.value) return '';
    try {
      return JSON.stringify(props.toolArgs, null, 2);
    } catch {
      return '';
    }
  });

  const isCollapsed = computed(() => hasOverflow.value && !expanded.value);
  const isExpanded = computed(() => hasOverflow.value && expanded.value);

  // 以内容完整高度（scrollHeight）与阈值比较判断是否溢出；折叠态下 scrollHeight 仍为完整内容高度
  const measureOverflow = () => {
    const el = codeRef.value;
    if (!el) return;
    hasOverflow.value = el.scrollHeight > COLLAPSED_MAX_HEIGHT;
  };

  const toggle = () => {
    expanded.value = !expanded.value;
  };

  // 卡片可能位于可拖拽面板中，宽度变化会影响换行进而改变行数，用 ResizeObserver 精准重算，避免深监听/轮询
  let resizeObserver: ResizeObserver | undefined;

  onMounted(() => {
    measureOverflow();
    if (typeof ResizeObserver !== 'undefined' && codeRef.value) {
      resizeObserver = new ResizeObserver(() => measureOverflow());
      resizeObserver.observe(codeRef.value);
    }
  });

  onBeforeUnmount(() => resizeObserver?.disconnect());

  // 参数内容变化时重置展开态并重新测量
  watch(formattedArgs, () => {
    expanded.value = false;
    measureOverflow();
  });
</script>

<style lang="scss">
  .ai-tool-approval-args {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;
    padding: 12px;
    background: #fff;
    border: 1px solid #f0f1f5;
    border-radius: 4px;

    &-header {
      display: flex;
      gap: 4px;
      align-items: center;
    }

    &-header-icon {
      flex: 0 0 16px;
      width: 16px;
      height: 16px;
    }

    &-header-label {
      font-size: var(--ai-font-size, 12px);
      line-height: 18px;
      color: #666;
    }

    &-body {
      display: flex;
      flex-direction: column;
      gap: 4px;
      width: 100%;
      padding: 12px 0 12px 8px;
      background: #f5f7fa;
    }

    &-code {
      width: 100%;
      margin: 0;
      overflow: hidden;
      font-family: ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace;
      font-size: var(--ai-font-size, 12px);
      line-height: 18px;
      color: #666;
      overflow-wrap: break-word;
      white-space: pre-wrap;

      // 折叠态：最多 3 行（54px），超出裁剪
      &.is-collapsed {
        max-height: 54px;
      }

      // 展开态：限制最大高度并滚动，避免超长参数把卡片撑爆
      &.is-expanded {
        max-height: 300px;
        overflow-y: auto;
      }
    }

    // 文字与箭头统一继承 toggle 的 color，hover 时整体变色，避免选择器特异性顺序问题
    &-toggle {
      display: flex;
      gap: 4px;
      align-items: center;
      justify-content: center;
      width: 100%;
      color: #3a84ff;
      cursor: pointer;
      user-select: none;

      &:hover {
        color: #1768ef;
      }
    }

    &-toggle-text {
      font-size: var(--ai-font-size, 12px);
      line-height: 18px;
    }

    &-toggle-icon {
      width: 12px;
      height: 12px;
      transform: rotate(-90deg);
      transition: transform 0.2s ease;

      path {
        stroke-width: 120;
      }

      // 展开态箭头向上
      &.is-expanded {
        transform: rotate(90deg);
      }
    }
  }
</style>
