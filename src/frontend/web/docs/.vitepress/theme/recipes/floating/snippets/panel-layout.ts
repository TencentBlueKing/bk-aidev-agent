/** AIBlueking 的初始位置与尺寸：default-* 只在挂载时生效 */
export interface PanelBox {
  defaultLeft: number;
  defaultTop: number;
  defaultWidth: number;
  defaultHeight: number;
}

/** 导航栏下方 */
const TOP = 76;
const GAP = 12;

const box = (left: number, width: number): PanelBox => ({
  defaultLeft: left,
  defaultTop: TOP,
  defaultWidth: width,
  defaultHeight: window.innerHeight - TOP - GAP,
});

// ① 贴在右侧（与默认行为一致）
export function dockRight(width = 400): PanelBox {
  return box(window.innerWidth - width - GAP, width);
}

// ② 贴在左侧导航之后，避开页面右侧的操作区
export function dockLeft(sidebarRight: number, width = 400): PanelBox {
  return box(sidebarRight + GAP, width);
}

// ③ 宽面板，适合阅读长回复
export function widePanel(): PanelBox {
  return dockRight(640);
}

// 用法：<AIBlueking v-bind="dockLeft(sidebarRight)" :url="apiUrl" />
