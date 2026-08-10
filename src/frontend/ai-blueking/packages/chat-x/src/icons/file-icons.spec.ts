import { describe, expect, it } from 'vitest';

import { UNKNOWN_FILE_ICON_SVG, getFileIconSvg } from './file-icons';

describe('getFileIconSvg', () => {
  it('应返回可直接内联的 svg 源码', () => {
    expect(getFileIconSvg('pdf')).toMatch(/^<svg[\s>]/);
  });

  it('同一图标覆盖的扩展名应返回同一份 svg', () => {
    expect(getFileIconSvg('xlsx')).toBe(getFileIconSvg('csv'));
    expect(getFileIconSvg('tsx')).toBe(getFileIconSvg('jsx'));
    expect(getFileIconSvg('sh')).toBe(getFileIconSvg('zsh'));
  });

  it('不同类型应返回不同图标', () => {
    expect(getFileIconSvg('pdf')).not.toBe(getFileIconSvg('docx'));
    expect(getFileIconSvg('py')).not.toBe(getFileIconSvg('go'));
  });

  it('大小写与无扩展名文件应正确命中', () => {
    expect(getFileIconSvg('PDF')).toBe(getFileIconSvg('pdf'));
    expect(getFileIconSvg('Dockerfile')).toBe(getFileIconSvg('dockerignore'));
  });

  it('type 缺省时回退文件名，未登记类型返回兜底图标', () => {
    expect(getFileIconSvg(undefined, 'main.py')).toBe(getFileIconSvg('py'));
    expect(getFileIconSvg('unknown-ext')).toBe(UNKNOWN_FILE_ICON_SVG);
    expect(getFileIconSvg()).toBe(UNKNOWN_FILE_ICON_SVG);
  });
});
