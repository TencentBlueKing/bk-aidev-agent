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
        <div class="ai-file-artifact-panel-preview-body">
          <!-- 异步取链 / HTML 拉取中：统一 MessageLoading -->
          <div
            v-if="previewStatus === 'loading'"
            class="ai-file-artifact-panel-preview-loading"
          >
            <MessageLoading />
          </div>
          <div
            v-else-if="previewStatus === 'error'"
            class="ai-file-artifact-panel-preview-error"
          >
            <span>{{ t('预览加载失败') }}</span>
            <Button
              size="small"
              text
              theme="primary"
              @click="loadPreview"
            >
              {{ t('重试') }}
            </Button>
          </div>
          <div
            v-else-if="previewStatus === 'empty'"
            class="ai-file-artifact-panel-preview-empty"
          >
            {{ t('暂无可预览的文件') }}
          </div>
          <!-- HTML：用 download_url 拉取 html 后 iframe srcdoc -->
          <iframe
            v-else-if="isHtml"
            class="ai-file-artifact-panel-preview-iframe"
            :srcdoc="htmlContent"
          />
          <!-- 其余类型：preview_url 为后台转换好的 pdf -->
          <iframe
            v-else
            class="ai-file-artifact-panel-preview-iframe"
            :src="previewUrl"
          />
        </div>
      </template>
      <div
        v-else
        class="ai-file-artifact-panel-preview-empty"
      >
        {{ t('暂无可预览的文件') }}
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { cloneVNode, computed, onBeforeUnmount, shallowRef, watch } from 'vue';

  import { Button, Input, Loading } from 'bkui-vue';

  import { AIFileType } from '../../../../ag-ui/types/file';
  import { triggerArtifactDownload, useArtifactPreviewConsumer } from '../../../../composables/use-artifact-preview';
  import { OverflowTips as vOverflowTips } from '../../../../directives/overflow-tips';
  import { DownloadFileIcon } from '../../../../icons/file';
  import { t } from '../../../../lang/lang';
  import MessageLoading from '../../../message-loading/message-loading.vue';
  import ArtifactFileCard from './artifact-file-card.vue';
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
  const previewStatus = shallowRef<'empty' | 'error' | 'idle' | 'loading' | 'ready'>('idle');
  const previewUrl = shallowRef('');
  const htmlContent = shallowRef('');
  // 记录当前进行中的请求，切换文件时中断旧请求，避免竞态覆盖
  let htmlAbortController: AbortController | undefined;
  // 用于丢弃过期的 URL 解析结果
  let loadSeq = 0;

  const filteredArtifacts = computed(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) {
      return props.artifacts;
    }
    return props.artifacts.filter(item => item.name.toLowerCase().includes(kw));
  });

  const activeArtifact = computed(() => props.artifacts.find(item => item.artifactId === props.activeId));

  const isHtml = computed(() => activeArtifact.value?.type === AIFileType.Html);

  const loadPreview = async () => {
    const file = activeArtifact.value;
    if (!file) {
      previewStatus.value = 'empty';
      return;
    }

    // 未传 onArtifactClick：预览区展示无数据
    if (!artifactPreview?.canResolveArtifactUrl.value) {
      previewStatus.value = 'empty';
      previewUrl.value = '';
      htmlContent.value = '';
      return;
    }

    const seq = ++loadSeq;
    htmlAbortController?.abort();
    previewStatus.value = 'loading';
    previewUrl.value = '';
    htmlContent.value = '';

    try {
      const urls = await artifactPreview.resolveArtifactUrls(file);
      if (seq !== loadSeq) {
        return;
      }

      if (file.type === AIFileType.Html) {
        const downloadUrl = urls.download_url;
        if (!downloadUrl) {
          previewStatus.value = 'empty';
          return;
        }
        const controller = new AbortController();
        htmlAbortController = controller;
        const res = await fetch(downloadUrl, { signal: controller.signal });
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const text = await res.text();
        if (controller.signal.aborted || seq !== loadSeq) {
          return;
        }
        htmlContent.value = text;
        previewStatus.value = 'ready';
        return;
      }

      if (!urls.preview_url) {
        previewStatus.value = 'empty';
        return;
      }
      previewUrl.value = urls.preview_url;
      previewStatus.value = 'ready';
    } catch {
      if (seq !== loadSeq) {
        return;
      }
      // abort 不算失败
      if (htmlAbortController?.signal.aborted) {
        return;
      }
      previewStatus.value = 'error';
    }
  };

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

  // 命中文件变化时重新异步取链并加载预览
  watch(
    () => activeArtifact.value?.artifactId,
    () => {
      downloadLoading.value = false;
      loadPreview();
    },
    { immediate: true },
  );

  onBeforeUnmount(() => {
    loadSeq += 1;
    htmlAbortController?.abort();
  });
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

      &-iframe {
        width: 100%;
        height: 100%;
        border: none;
      }

      &-loading {
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
      }

      &-error {
        display: flex;
        gap: 8px;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: variables.$color-text-secondary;
      }

      &-empty {
        display: flex;
        flex: 1;
        align-items: center;
        justify-content: center;
        height: 100%;
        color: variables.$color-text-secondary;
      }
    }
  }
</style>
