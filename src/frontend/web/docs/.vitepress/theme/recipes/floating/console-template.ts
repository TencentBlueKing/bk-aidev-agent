import type { FloatingConfig } from '../../demo-kit/types';

export interface FloatingConsoleConfig {
  draggable: boolean;
  showNimbus: boolean;
  nimbusSize: 'small' | 'normal' | 'large';
  defaultWidth: number;
  enablePopup: boolean;
  frontendShortcuts: boolean;
}

export const DEFAULT_CONSOLE_CONFIG: Readonly<FloatingConsoleConfig> = {
  draggable: true,
  showNimbus: true,
  nimbusSize: 'normal',
  defaultWidth: 400,
  enablePopup: false,
  frontendShortcuts: false,
};

/** 配置台演示用的前端快捷指令（与智能体后台配置的指令合并展示） */
export const DEMO_SHORTCUTS = [
  { id: 'translate', name: '翻译', icon: 'translate', prompt: '请把以下内容翻译成英文：' },
  { id: 'summarize', name: '总结', icon: 'summarize', prompt: '请用三句话总结以下内容：' },
  { id: 'explain-error', name: '解释报错', icon: 'explain', prompt: '请解释以下报错的原因并给出处理建议：' },
];

const SHORTCUTS_SNIPPET = [
  '',
  '// 前端自定义快捷指令（与智能体后台配置的指令合并展示）',
  'const shortcuts = [',
  ...DEMO_SHORTCUTS.map(s => `  { id: '${s.id}', name: '${s.name}', icon: '${s.icon}', prompt: '${s.prompt}' },`),
  '];',
];

const isDefault = (config: FloatingConsoleConfig): boolean =>
  (Object.keys(DEFAULT_CONSOLE_CONFIG) as (keyof FloatingConsoleConfig)[]).every(
    key => config[key] === DEFAULT_CONSOLE_CONFIG[key],
  );

/** 生成与当前配置等价的 <AIBlueking> 模板：只输出与默认值不同的属性 */
export function buildFloatingTemplate(config: FloatingConsoleConfig): string {
  const d = DEFAULT_CONSOLE_CONFIG;
  const lines = ['<AIBlueking', '  ref="aiBluekingRef"', '  :url="apiUrl"'];
  if (config.draggable !== d.draggable) lines.push(`  :draggable="${config.draggable}"`);
  if (config.showNimbus !== d.showNimbus) lines.push('  hide-nimbus');
  if (config.nimbusSize !== d.nimbusSize) lines.push(`  nimbus-size="${config.nimbusSize}"`);
  if (config.defaultWidth !== d.defaultWidth) lines.push(`  :default-width="${config.defaultWidth}"`);
  if (config.enablePopup !== d.enablePopup) lines.push(`  :enable-popup="${config.enablePopup}"`);
  if (config.frontendShortcuts) lines.push('  :shortcuts="shortcuts"');
  lines.push('/>');
  if (config.frontendShortcuts) lines.push(...SHORTCUTS_SNIPPET);
  return lines.join('\n');
}

/** 转为宿主可直接 v-bind 的浮窗配置；与默认值相同时复用默认实例 */
export function toFloatingConfig(config: FloatingConsoleConfig): FloatingConfig {
  if (isDefault(config)) return { props: {}, key: 'default' };
  return {
    key: `console:${JSON.stringify(config)}`,
    props: {
      draggable: config.draggable,
      hideNimbus: !config.showNimbus,
      nimbusSize: config.nimbusSize,
      defaultWidth: config.defaultWidth,
      enablePopup: config.enablePopup,
      ...(config.frontendShortcuts ? { shortcuts: DEMO_SHORTCUTS } : {}),
    },
  };
}

export { diffLines } from '../../demo-kit/code-steps';
