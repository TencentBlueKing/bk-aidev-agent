<template>
  <div class="ai-flow-agent-node-detail">
    <h3 class="detail-title">
      <template v-if="loading">
        <span>{{ t('节点') }}：</span>
        <span class="skeleton-title ai-skeleton-element" />
      </template>
      <div
        v-else
        class="detail-title-content"
      >
        {{ t('节点') }}：{{ basicInfo?.node_name }}
      </div>
      <slot name="locateButton" />
    </h3>
    <div class="detail-tab-bar">
      <div
        v-for="tab in TABS"
        :key="tab.key"
        class="detail-tab"
        :class="{ 'is-active': activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <component
          :is="tab.key === DetailTab.Config ? NodeTabIcon : NodeOutputIcon"
          class="detail-tab-icon"
        />
        {{ tab.label }}
      </div>
    </div>

    <div class="detail-body">
      <template v-if="activeTab === DetailTab.Config">
        <template v-if="loading">
          <div class="skeleton-section">
            <div class="skeleton-heading ai-skeleton-element" />
            <div
              v-for="i in 6"
              :key="i"
              class="skeleton-row ai-skeleton-element"
            />
          </div>
          <div class="skeleton-section">
            <div class="skeleton-heading ai-skeleton-element" />
            <div
              v-for="i in 4"
              :key="i"
              class="skeleton-row ai-skeleton-element"
            />
          </div>
        </template>
        <template v-else>
          <DetailSection :title="t('基础信息')">
            <div class="info-form">
              <div
                v-for="row in basicInfoRows"
                :key="row.label"
                class="info-row"
              >
                <div class="info-label">{{ row.label }}</div>
                <div class="info-value">{{ row.value }}</div>
              </div>
              <div class="info-row">
                <div class="info-label">{{ t('失败处理') }}</div>
                <div class="info-value">
                  <template v-if="hasFailureHandling">
                    <span
                      v-if="basicInfo?.skippable"
                      class="failure-item"
                    >
                      <span class="tag-badge">MS</span>
                      {{ t('手动跳过') }}{{ basicInfo?.auto_retry?.enable ? '；' : '' }}
                    </span>
                    <span
                      v-if="basicInfo?.auto_retry?.enable"
                      class="failure-item"
                    >
                      <span class="tag-badge">AR</span>
                      {{ autoRetryText }}
                    </span>
                  </template>
                  <template v-else>--</template>
                </div>
              </div>
              <div class="info-row">
                <div class="info-label">{{ t('超时控制') }}</div>
                <div class="info-value">{{ timeoutText }}</div>
              </div>
            </div>
          </DetailSection>
          <DetailSection :title="t('输入参数')">
            <SimpleTable
              :columns="INPUT_COLUMNS"
              :data="inputTableData"
            />
          </DetailSection>
          <DetailSection :title="t('输出参数')">
            <SimpleTable
              :columns="PLUGIN_OUTPUT_COLUMNS"
              :data="pluginOutputTableData"
            />
          </DetailSection>
        </template>
      </template>
      <template v-else>
        <template v-if="loading">
          <div class="skeleton-section">
            <div class="skeleton-heading ai-skeleton-element" />
            <div
              v-for="i in 5"
              :key="i"
              class="skeleton-row ai-skeleton-element"
            />
          </div>
        </template>
        <template v-else>
          <DetailSection :title="t('结构化输出')">
            <SimpleTable
              :columns="OUTPUT_COLUMNS"
              :data="outputTableData"
            />
          </DetailSection>
        </template>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { type VNode, computed, shallowRef } from 'vue';

  import { isEn } from '../../../common/lang';
  import { NodeOutputIcon, NodeTabIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import DetailSection from './detail-section.vue';
  import SimpleTable from './simple-table.vue';

  import type { CustomBkFlowTabData, NodeDetailData } from '../../../types';
  import type { SimpleTableColumn } from './simple-table.vue';
  defineSlots<{
    locateButton: () => VNode;
  }>();
  enum DetailTab {
    Config = 'config',
    Output = 'output',
  }
  const TABS = [
    { key: DetailTab.Config, label: t('节点配置') },
    { key: DetailTab.Output, label: t('节点输出') },
  ];

  const INPUT_COLUMNS: SimpleTableColumn[] = [
    { key: 'key', label: t('参数名') },
    { breakAll: true, key: 'value', label: t('参数值') },
  ];

  const PLUGIN_OUTPUT_COLUMNS: SimpleTableColumn[] = [
    { key: 'name', label: t('名称') },
    { key: 'description', label: t('变量说明') },
    { key: 'key', label: 'KEY' },
  ];

  const OUTPUT_COLUMNS: SimpleTableColumn[] = [
    { key: 'key', label: t('参数名') },
    { breakAll: true, key: 'value', label: t('参数值') },
  ];

  const TIMEOUT_ACTION_MAP: Record<string, string> = {
    forced_fail: isEn ? 'Force Fail' : '强制失败',
  };

  const props = defineProps<CustomBkFlowTabData['props'] & { data: Partial<NodeDetailData> }>();

  const activeTab = shallowRef(DetailTab.Config);

  const basicInfo = computed(() => props.data?.basic_info);

  const basicInfoRows = computed(() => {
    const info = basicInfo.value;
    if (!info) return [];
    return [
      { label: t('流程模板'), value: info.template_name || '--' },
      { label: t('节点名称'), value: info.node_name || '--' },
      { label: t('步骤名称'), value: info.stage_name || '--' },
      { label: t('是否可选'), value: info.optional ? t('是') : t('否') },
    ];
  });

  const hasFailureHandling = computed(() => {
    const info = basicInfo.value;
    return info?.skippable || info?.auto_retry?.enable;
  });

  const autoRetryText = computed(() => {
    const retry = basicInfo.value?.auto_retry;
    if (!retry?.enable) return '';
    return isEn
      ? `In ${retry.interval} seconds, auto retry ${retry.times} times`
      : `在 ${retry.interval} 秒后，自动重试 ${retry.times} 次`;
  });

  const timeoutText = computed(() => {
    const config = basicInfo.value?.timeout_config;
    if (!config?.enable) return '--';
    const action = TIMEOUT_ACTION_MAP[config.action] ?? config.action;
    return isEn ? `Timeout ${config.seconds} seconds later, ${action}` : `超时 ${config.seconds} 秒后则${action}`;
  });

  const inputTableData = computed(() =>
    Object.entries(props.data?.inputs ?? {}).map(([key, value]) => ({
      key,
      value: formatValue(value),
    })),
  );

  const pluginOutputTableData = computed(() =>
    (props.data?.plugin_output ?? []).map(item => ({
      description: item.schema?.description || '--',
      name: item.name,
      key: item.key,
    })),
  );

  const outputTableData = computed(() =>
    (props.data?.outputs ?? []).map(item => ({
      key: item.key,
      value: formatValue(item.value),
    })),
  );

  const formatValue = (value: unknown): string => {
    if (value === null || value === undefined) return '--';
    if (typeof value === 'object') return JSON.stringify(value);
    return String(value);
  };
</script>

<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-flow-agent-node-detail {
    display: flex;
    flex-direction: column;
    height: 100%;
    padding: 16px 24px;
    font-size: var(--ai-font-size, 12px);

    .detail-title {
      display: flex;
      align-items: center;
      margin: 0 0 16px;
      line-height: 24px;
      color: variables.$color-title;

      &-content {
        flex: 1;
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 16px;
        font-weight: bold;
        white-space: nowrap;
      }
    }

    .detail-tab-bar {
      display: flex;
      align-items: center;
      height: 32px;
      padding: 4px;
      background: variables.$color-bg-tab;
      border-radius: 2px;
    }

    .detail-tab {
      display: inline-flex;
      flex: 1;
      gap: 4px;
      align-items: center;
      justify-content: center;
      height: 24px;
      padding: 5px 12px;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: variables.$color-text;
      cursor: pointer;
      border-radius: 2px;

      &.is-active {
        color: variables.$color-primary;
        background: white;
        box-shadow: 1px 1px 4px 0 rgb(0 0 0 / 10%);
      }
    }

    .detail-body {
      flex: 1;
      min-height: 0;
      padding: 16px 24px;
      margin: -16px -24px;
      margin-top: 16px;
      overflow: auto;
    }

    .skeleton-title {
      display: inline-block;
      width: 120px;
      height: 20px;
      vertical-align: middle;
      border-radius: 2px;
    }

    .skeleton-section {
      margin-bottom: 16px;
    }

    .skeleton-heading {
      width: 80px;
      height: 22px;
      margin-bottom: 8px;
      border-radius: 2px;
    }

    .skeleton-row {
      height: 20px;
      margin-bottom: 12px;
      border-radius: 2px;
    }

    .info-form {
      overflow: hidden;
      border: 1px solid variables.$color-border;
      border-radius: 2px;
    }

    .info-row {
      display: flex;

      &:not(:last-child) {
        border-bottom: 1px solid variables.$color-border;
      }
    }

    .info-label {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      width: 140px;
      min-height: 42px;
      padding: 11px 16px;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: variables.$color-text;
      background: variables.$color-bg-light;
      border-right: 1px solid variables.$color-border;
    }

    .info-value {
      display: flex;
      flex: 1;
      flex-wrap: wrap;
      align-items: center;
      min-height: 42px;
      padding: 11px 16px;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: variables.$color-text;
      word-break: break-all;
    }

    .failure-item {
      display: inline-flex;
      gap: 4px;
      align-items: center;
    }

    .tag-badge {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 18px;
      height: 14px;
      padding: 0 2px;
      font-size: var(--ai-font-size, 12px);
      line-height: 1;
      color: white;
      background: variables.$color-text-secondary;
      border-radius: 1px;
      transform: scale(0.8);
    }
  }
</style>
