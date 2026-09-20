<template>
  <!--
    data-tag-* 是编辑器 void 节点的识别依据（见 ai-slash-input/constants.ts 的 tagSchema）。
    在消息里它们不参与交互，但保留后从消息复制到输入框可以原样还原成标签。
  -->
  <span
    v-tippy="tippyOptions"
    class="ai-mention-tag"
    :class="{ 'is-interactive': !!description || isPreviewable }"
    contenteditable="false"
    :data-tag-description="description || undefined"
    :data-tag-icon="icon || undefined"
    :data-tag-label="label"
    :data-tag-type="type"
    :data-tag-value="value"
    @click="handleClick"
  >
    <ResourceIcon
      :icon="icon"
      :name="label"
      :type="type"
    />
    <span class="ai-mention-tag-name">{{ label }}</span>
  </span>
</template>
<script setup lang="ts">
  import { computed } from 'vue';

  import { directive as vTippy } from 'vue-tippy';

  import { useArtifactPreviewConsumer } from '../../composables/use-artifact-preview';
  import { getMenuTypeLabel } from '../chat-input/input-menu/constants';
  import { t } from '../../lang/lang';
  import { ResourceIcon } from '../resource-icon';
  import { createMentionTippy } from './create-mention-tippy';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<{
    /** 有描述才弹气泡；来源于标签节点自身，不依赖外部数据源 */
    description?: string;
    icon?: string;
    label: string;
    type: string;
    value: string;
  }>();

  const artifactPreview = useArtifactPreviewConsumer();
  // 会话产物标签点击后打开侧栏预览，与消息区文件卡片的点击行为一致
  const isPreviewable = computed(() => props.type === 'artifact' && !!artifactPreview);

  const handleClick = () => {
    if (!isPreviewable.value) {
      return;
    }
    // 命中只依赖 outputId，标签持有的 value 即是它
    artifactPreview?.openPreview({ file: { outputId: props.value } });
  };

  // 标题形如「工具：knowlege-base」，类型名与菜单分组标题同源
  const tippyOptions = computed(() => {
    if (!props.description) {
      return { content: '', onShow: () => false };
    }
    const typeLabel = getMenuTypeLabel(props.type);
    return createMentionTippy({
      title: typeLabel ? `${t(typeLabel)}：${props.label}` : props.label,
      description: props.description,
    });
  });
</script>
<style lang="scss">
  @use '../../styles/variables.scss' as variables;

  // 设计稿：已选资源以「图标 + 蓝色文字」内联展示，无背景块
  .ai-mention-tag {
    display: inline-flex;
    gap: 4px;
    align-items: center;
    height: 22px;
    font-size: var(--ai-font-size, 12px);
    line-height: var(--ai-line-height-compact, 20px);
    vertical-align: bottom;
    color: variables.$color-primary;
    border-radius: 2px;

    // 有描述可看或可点开预览时，才给出可交互的暗示
    &.is-interactive:hover {
      cursor: pointer;

      .ai-mention-tag-name {
        text-decoration: underline;
      }
    }
  }
</style>
