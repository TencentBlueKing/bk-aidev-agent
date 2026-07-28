<template>
  <div class="ai-file-artifact-panel">
    <!-- 左侧：文件列表 + 搜索 -->
    <div class="ai-file-artifact-panel-list">
      <p class="ai-file-artifact-panel-list-title">{{ t('文件列表') }}（{{ artifacts.length }}）</p>
      <Input
        v-model="keyword"
        class="ai-file-artifact-panel-list-search"
        clearable
        :placeholder="t('搜索文件关键字')"
      />
      <div class="ai-file-artifact-panel-list-scroll">
        <template v-if="filteredArtifacts.length">
          <ArtifactFileCard
            v-for="item in filteredArtifacts"
            :key="item.artifactId"
            :active="item.artifactId === activeId"
            :file="item"
            :on-preview="() => handleSelect(item)"
            variant="list"
          />
        </template>
        <div
          v-else
          class="ai-file-artifact-panel-list-empty"
        >
          {{ t('搜索结果为空') }}
        </div>
      </div>
    </div>

    <!-- 右侧：预览区 -->
    <div class="ai-file-artifact-panel-preview">
      <template v-if="activeArtifact">
        <div class="ai-file-artifact-panel-preview-header">
          <div class="ai-file-artifact-panel-preview-header-info">
            <span class="ai-file-artifact-panel-preview-header-icon">
              <component :is="getFileIcon(activeArtifact.type)" />
            </span>
            <span
              v-overflow-tips="{ text: activeArtifact.name, placement: 'top' as const }"
              class="ai-file-artifact-panel-preview-header-name"
            >
              {{ activeArtifact.name }}
            </span>
          </div>
          <span
            v-if="canResolveArtifactUrl"
            class="ai-file-artifact-panel-preview-header-download"
            :class="{ 'is-loading': downloadLoading }"
            @click="handleDownload(activeArtifact)"
          >
            <Loading
              v-if="downloadLoading"
              mode="spin"
              size="mini"
              theme="primary"
            />
            <component
              :is="getDownloadIcon()"
              v-else
            />
          </span>
        </div>
      </template>
      <div class="ai-file-artifact-panel-preview-body">
        <ArtifactPreviewHost :file="activeArtifact" />
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { cloneVNode, computed, shallowRef, watch } from 'vue';

  import { Input, Loading } from 'bkui-vue';

  import { triggerArtifactDownload, useArtifactPreviewConsumer } from '../../../../composables/use-artifact-preview';
  import { OverflowTips as vOverflowTips } from '../../../../directives/overflow-tips';
  import { DownloadFileIcon } from '../../../../icons/file';
  import { t } from '../../../../lang/lang';
  import ArtifactFileCard from './artifact-file-card.vue';
  import ArtifactPreviewHost from './artifact-preview/artifact-preview-host.vue';
  import { getFileIcon } from './file-icon';

  import type { SessionArtifact } from '../../../../composables/use-artifact-preview';

  const props = defineProps<{
    // 命中的文件 id（messageUid#index#outputId）
    activeId: string;
    // 当前会话全部文件产物
    artifacts: SessionArtifact[];
  }>();

  const emits = defineEmits<{
    (e: 'select', id: string): void;
  }>();

  const artifactPreview = useArtifactPreviewConsumer();
  const canResolveArtifactUrl = computed(() => !!artifactPreview?.canResolveArtifactUrl.value);

  // 下载图标为共享 VNode，每处渲染克隆一份，避免多处复用同一实例
  const getDownloadIcon = () => cloneVNode(DownloadFileIcon);

  const keyword = shallowRef('');
  const downloadLoading = shallowRef(false);

  const filteredArtifacts = computed(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) {
      return props.artifacts;
    }
    return props.artifacts.filter(item => item.name.toLowerCase().includes(kw));
  });

  const activeArtifact = computed(() => props.artifacts.find(item => item.artifactId === props.activeId));

  const handleSelect = (item: SessionArtifact) => {
    if (item.artifactId === props.activeId) {
      return;
    }
    emits('select', item.artifactId);
  };

  const handleDownload = async (file: SessionArtifact) => {
    if (downloadLoading.value || !artifactPreview?.canResolveArtifactUrl.value) {
      return;
    }
    downloadLoading.value = true;
    try {
      const { download_url: downloadUrl } = await artifactPreview.resolveArtifactUrls(file);
      if (downloadUrl) {
        triggerArtifactDownload(downloadUrl, file.name);
      }
    } finally {
      downloadLoading.value = false;
    }
  };

  watch(
    () => activeArtifact.value?.artifactId,
    () => {
      downloadLoading.value = false;
    },
  );
</script>
<style lang="scss">
  @use '../../../../styles/variables.scss' as variables;

  .ai-file-artifact-panel {
    display: flex;
    width: 100%;
    height: 100%;
    overflow: hidden;
    font-size: var(--ai-font-size, 12px);

    &-list {
      display: flex;
      flex-shrink: 0;
      flex-direction: column;
      gap: 10px;
      width: 221px;
      height: 100%;
      padding: 16px 8px 8px 16px;
      border-right: 1px solid variables.$color-border-light;

      &-title {
        margin: 0;
        line-height: var(--ai-line-height, 20px);
        color: variables.$color-title;
      }

      &-scroll {
        display: flex;
        flex: 1;
        flex-direction: column;
        min-height: 0;
        overflow-y: auto;
        scrollbar-color: variables.$color-border transparent;
        scrollbar-width: thin;
      }

      &-empty {
        padding: 24px 0;
        color: variables.$color-text-secondary;
        text-align: center;
      }
    }

    &-preview {
      display: flex;
      flex: 1;
      flex-direction: column;
      min-width: 0;
      padding: 10px 16px;

      &-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 4px 0 12px;
        border-bottom: 1px solid variables.$color-border-light;

        &-info {
          display: flex;
          gap: 8px;
          align-items: center;
          min-width: 0;
        }

        &-icon {
          display: inline-flex;
          flex-shrink: 0;
          font-size: 20px;
        }

        &-name {
          overflow: hidden;
          text-overflow: ellipsis;
          font-size: 16px;
          font-weight: bold;
          line-height: 24px;
          color: variables.$color-title;
          white-space: nowrap;
        }

        &-download {
          display: inline-flex;
          flex-shrink: 0;
          align-items: center;
          justify-content: center;
          width: 24px;
          height: 24px;
          padding: 4px;
          font-size: 16px;
          color: #969799;
          border-radius: 4px;

          &:hover {
            color: variables.$color-primary;
            cursor: pointer;
            background-color: #f5f7fa;
          }

          &.is-loading {
            pointer-events: none;
            cursor: default;
          }
        }
      }

      &-body {
        flex: 1;
        min-height: 0;
        margin-top: 10px;
      }
    }
  }
</style>
