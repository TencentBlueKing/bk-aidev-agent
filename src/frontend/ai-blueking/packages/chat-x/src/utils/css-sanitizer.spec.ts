import { describe, expect, it } from 'vitest';

import { sanitizeCSS } from './css-sanitizer';

describe('sanitizeCSS', () => {
  it('保留白名单中的安全属性', () => {
    expect(sanitizeCSS('color: red')).toBe('color: red');
    expect(sanitizeCSS('font-size: 16px')).toBe('font-size: 16px');
    expect(sanitizeCSS('background-color: #fff')).toBe('background-color: #fff');
  });

  it('过滤不在白名单中的属性', () => {
    expect(sanitizeCSS('position: absolute')).toBe('');
    expect(sanitizeCSS('z-index: 999')).toBe('');
    expect(sanitizeCSS('content: "hello"')).toBe('');
  });

  it('过滤危险 CSS 模式 - url()', () => {
    expect(sanitizeCSS('background: url(http://evil.com)')).toBe('');
    expect(sanitizeCSS('background-image: url("data:image/png;base64,xxx")')).toBe('');
  });

  it('过滤危险 CSS 模式 - expression()', () => {
    expect(sanitizeCSS('width: expression(alert(1))')).toBe('');
  });

  it('过滤危险 CSS 模式 - javascript:', () => {
    expect(sanitizeCSS('background: javascript:alert(1)')).toBe('');
  });

  it('过滤危险 CSS 模式 - @import', () => {
    expect(sanitizeCSS('background: @import url("evil.css")')).toBe('');
  });

  it('处理多个属性（分号分隔）', () => {
    const input = 'color: red; font-size: 16px; position: absolute';
    expect(sanitizeCSS(input)).toBe('color: red; font-size: 16px');
  });

  it('处理空字符串', () => {
    expect(sanitizeCSS('')).toBe('');
  });

  it('处理无冒号的声明（跳过）', () => {
    expect(sanitizeCSS('invalid-declaration')).toBe('');
  });

  it('属性名大小写不敏感', () => {
    expect(sanitizeCSS('COLOR: red')).toBe('color: red');
    expect(sanitizeCSS('Font-Size: 14px')).toBe('font-size: 14px');
  });

  it('保留 style 属性的完整格式', () => {
    expect(sanitizeCSS('color: red; font-weight: bold')).toBe('color: red; font-weight: bold');
  });
});
