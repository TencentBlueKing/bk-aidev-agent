export type HeaderLeftTag = '' | '测试环境' | 'Pro';

export interface HeaderSlotConfig {
  leftTag: HeaderLeftTag;
  customAction: boolean;
  showHistoryIcon: boolean;
}

export const DEFAULT_HEADER_CONFIG: Readonly<HeaderSlotConfig> = {
  leftTag: '测试环境',
  customAction: true,
  showHistoryIcon: true,
};

export type DemoRenderMode = 'chat' | 'test' | 'share';

/** 生成与 Header 插槽配置等价的模板 */
export function buildHeaderTemplate(config: HeaderSlotConfig): string {
  const open = ['<AIBlueking', '  ref="aiBluekingRef"', '  :url="apiUrl"'];
  if (!config.showHistoryIcon) open.push('  :show-history-icon="false"');
  const body: string[] = [];
  if (config.leftTag) {
    body.push('  <!-- 标题区与工具栏之间：适合标签、状态，不要放工具按钮 -->', '  <template #headerLeft>', `    <span class="env-tag">${config.leftTag}</span>`, '  </template>');
  }
  if (config.customAction) {
    body.push(
      '  <!-- 右侧工具栏：会话操作之后、窗口控制之前；带 bkai-icon 与内置图标对齐 -->',
      '  <template #headerActions>',
      '    <i class="bkai-icon" title="导出对话" @click="exportChat"><DownloadIcon /></i>',
      '  </template>',
    );
  }
  if (!body.length) return [...open, '/>'].join('\n');
  return [...open, '>', ...body, '</AIBlueking>'].join('\n');
}

/** 生成 renderMode 示例模板（dropdownMenuConfig 打开全部菜单项，便于对比） */
export function buildRenderModeTemplate(mode: DemoRenderMode): string {
  return [
    '<AIBlueking',
    '  ref="aiBluekingRef"',
    '  :url="apiUrl"',
    ...(mode === 'chat' ? [] : [`  render-mode="${mode}"`]),
    '  :dropdown-menu-config="{ showRename: true, showAutoGenerate: true, showShare: true }"',
    '/>',
  ].join('\n');
}
