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
            v-if="activeArtifact.url"
            class="ai-file-artifact-panel-preview-header-download"
            @click="handleDownload(activeArtifact)"
          >
            <component :is="getDownloadIcon()" />
          </span>
        </div>
        <div class="ai-file-artifact-panel-preview-body">
          <!-- HTML：拉取 file.url 的 html 字符串后用 iframe srcdoc 渲染 -->
          <template v-if="isHtml">
            <div
              v-if="htmlStatus === 'loading'"
              class="ai-file-artifact-panel-preview-skeleton ai-skeleton-element"
            />
            <div
              v-else-if="htmlStatus === 'error'"
              class="ai-file-artifact-panel-preview-error"
            >
              <span>{{ t('预览加载失败') }}</span>
              <Button
                size="small"
                text
                theme="primary"
                @click="loadHtml"
              >
                {{ t('重试') }}
              </Button>
            </div>
            <iframe
              v-else
              class="ai-file-artifact-panel-preview-iframe"
              :srcdoc="htmlContent"
            />
          </template>
          <!-- 其余类型：previewUrl 为后台转换好的 pdf，直接 iframe 展示 -->
          <iframe
            v-else
            class="ai-file-artifact-panel-preview-iframe"
            :src="activeArtifact.previewUrl"
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

  import { Button, Input } from 'bkui-vue';

  import { AIFileType } from '../../../../ag-ui/types/file';
  import { OverflowTips as vOverflowTips } from '../../../../directives/overflow-tips';
  import { DownloadIcon } from '../../../../icons/file';
  import { t } from '../../../../lang/lang';
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

  // 下载图标为共享 VNode，每处渲染克隆一份，避免多处复用同一实例
  const getDownloadIcon = () => cloneVNode(DownloadIcon);

  const keyword = shallowRef('');

  const filteredArtifacts = computed(() => {
    const kw = keyword.value.trim().toLowerCase();
    if (!kw) {
      return props.artifacts;
    }
    return props.artifacts.filter(item => item.name.toLowerCase().includes(kw));
  });

  const activeArtifact = computed(() => props.artifacts.find(item => item.artifactId === props.activeId));

  const isHtml = computed(() => activeArtifact.value?.type === AIFileType.Html);

  const htmlStatus = shallowRef<'error' | 'idle' | 'loading' | 'ready'>('idle');
  const htmlContent = shallowRef('');
  // 记录当前进行中的请求，切换文件时中断旧请求，避免竞态覆盖
  let htmlAbortController: AbortController | undefined;

  const loadHtml = async () => {
    const file = activeArtifact.value;
    if (!file) {
      return;
    }
    htmlAbortController?.abort();
    const controller = new AbortController();
    htmlAbortController = controller;
    htmlStatus.value = 'loading';
    htmlContent.value = '';
    try {
      const res = await fetch(file.url, { signal: controller.signal });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const text = await res.text();
      // 请求返回时若已切换到其它文件则丢弃结果
      if (controller.signal.aborted) {
        return;
      }
      htmlContent.value = text;
      htmlStatus.value = 'ready';
    } catch {
      if (controller.signal.aborted) {
        return;
      }
      htmlStatus.value = 'error';
    }
  };

  const handleSelect = (item: SessionArtifact) => {
    if (item.artifactId === props.activeId) {
      return;
    }
    emits('select', item.artifactId);
  };

  const handleDownload = (file: SessionArtifact) => {
    const link = document.createElement('a');
    link.href = file.url;
    link.download = file.name;
    link.target = '_blank';
    link.rel = 'noopener';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // 命中文件变化时：html 触发拉取，其余类型清空 html 缓存交给 iframe.src 直接渲染
  watch(
    () => activeArtifact.value?.artifactId,
    () => {
      if (isHtml.value) {
        loadHtml();
      } else {
        htmlAbortController?.abort();
        htmlStatus.value = 'idle';
        htmlContent.value = '';
      }
    },
    { immediate: true },
  );

  onBeforeUnmount(() => {
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
          padding: 4px;
          font-size: 16px;
          color: #969799;
          border-radius: 4px;

          &:hover {
            color: variables.$color-primary;
            cursor: pointer;
            background-color: #f5f7fa;
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

      &-skeleton {
        width: 100%;
        height: 100%;
        border-radius: 4px;
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
        color: variables.$color-text-secondary;
      }
    }
  }
</style>
