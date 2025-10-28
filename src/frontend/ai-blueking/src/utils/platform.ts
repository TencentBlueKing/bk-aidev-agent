/**
 * 检测当前操作系统平台
 */
export function getPlatform() {
  const userAgent = window.navigator.userAgent.toLowerCase();
  const platform = window.navigator.platform.toLowerCase();

  if (platform.includes('mac') || userAgent.includes('mac')) {
    return 'mac';
  }
  if (platform.includes('win') || userAgent.includes('win')) {
    return 'windows';
  }
  if (platform.includes('linux') || userAgent.includes('linux')) {
    return 'linux';
  }
  return 'unknown';
}

/**
 * 判断是否为 Mac 系统
 */
export function isMac() {
  return getPlatform() === 'mac';
}

/**
 * 获取打开面板的快捷键文本
 */
export function getTogglePanelShortcut() {
  return isMac() ? 'Cmd + I' : 'Ctrl + I';
}

/**
 * 检查键盘事件是否触发了打开面板的快捷键
 * @param event 键盘事件
 * @returns 是否触发快捷键
 */
export function isTogglePanelShortcut(event: KeyboardEvent): boolean {
  const isMacPlatform = isMac();
  const isModifierPressed = isMacPlatform ? event.metaKey : event.ctrlKey;
  const isIKey = event.key.toLowerCase() === 'i';

  return isModifierPressed && isIKey && !event.shiftKey && !event.altKey;
}
