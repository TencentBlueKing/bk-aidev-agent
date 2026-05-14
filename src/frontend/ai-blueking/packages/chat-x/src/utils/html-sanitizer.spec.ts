import { describe, expect, it } from 'vitest';

import { sanitizeHtmlFragment } from './html-sanitizer';

describe('sanitizeHtmlFragment', () => {
  it('保留安全的 HTML 标签', () => {
    expect(sanitizeHtmlFragment('<b>bold</b>')).toBe('<b>bold</b>');
    expect(sanitizeHtmlFragment('<font color="red">text</font>')).toBe('<font color="red">text</font>');
    expect(sanitizeHtmlFragment('<i>italic</i>')).toBe('<i>italic</i>');
  });

  it('不自动闭合标签（流式场景核心行为）', () => {
    expect(sanitizeHtmlFragment('<font color="red">')).toBe('<font color="red">');
    expect(sanitizeHtmlFragment('<b>')).toBe('<b>');
    expect(sanitizeHtmlFragment('</b>')).toBe('</b>');
    expect(sanitizeHtmlFragment('</font>')).toBe('</font>');
  });

  it('剥离 script 标签', () => {
    expect(sanitizeHtmlFragment('<script>alert(1)</script>')).toBe('');
    expect(sanitizeHtmlFragment('<script src="evil.js"></script>')).toBe('');
    expect(sanitizeHtmlFragment('<script type="text/javascript">alert(1)</script>')).toBe('');
  });

  it('剥离事件处理器属性', () => {
    expect(sanitizeHtmlFragment('<img src=x onerror=alert(1)>')).toBe('<img src=x >');
    expect(sanitizeHtmlFragment('<div onclick="alert(1)">text</div>')).toBe('<div >text</div>');
    expect(sanitizeHtmlFragment('<body onload = "evil()">')).toBe('<body >');
  });

  it('剥离 javascript: URI', () => {
    expect(sanitizeHtmlFragment('<a href="javascript:alert(1)">link</a>')).toBe('<a href="alert(1)">link</a>');
  });

  it('过滤 style 属性中的危险 CSS', () => {
    expect(sanitizeHtmlFragment('<div style="color: red">text</div>')).toBe('<div style="color: red">text</div>');
    expect(sanitizeHtmlFragment('<div style="background: url(evil)">text</div>')).toBe('<div>text</div>');
  });

  it('剥离 null bytes 后再匹配规则', () => {
    expect(sanitizeHtmlFragment('<scr\x00ipt>alert(1)</script>')).toBe('');
  });

  it('处理空字符串', () => {
    expect(sanitizeHtmlFragment('')).toBe('');
  });

  it('处理纯文本（无 HTML）', () => {
    expect(sanitizeHtmlFragment('hello world')).toBe('hello world');
  });

  it('处理嵌套的合法 HTML', () => {
    const input = '<font color="red"><b>【通知】</b></font>';
    expect(sanitizeHtmlFragment(input)).toBe(input);
  });
});
