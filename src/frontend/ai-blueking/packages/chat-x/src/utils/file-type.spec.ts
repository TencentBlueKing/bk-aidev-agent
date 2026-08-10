import { describe, expect, it } from 'vitest';

import { normalizeFileExtension, resolveFileKind } from './file-type';

describe('normalizeFileExtension', () => {
  it('应取最后一段扩展名并转小写', () => {
    expect(normalizeFileExtension('PDF')).toBe('pdf');
    expect(normalizeFileExtension(undefined, '季度报告.final.XLSX')).toBe('xlsx');
  });

  it('无扩展名文件应返回文件名本身', () => {
    expect(normalizeFileExtension('Dockerfile')).toBe('dockerfile');
    expect(normalizeFileExtension(undefined, 'Makefile')).toBe('makefile');
  });

  it('点号开头的隐藏文件应取点号后的部分', () => {
    expect(normalizeFileExtension(undefined, '.gitignore')).toBe('gitignore');
    expect(normalizeFileExtension('.editorconfig')).toBe('editorconfig');
  });

  it('type 缺省时回退文件名，两者都为空时返回空串', () => {
    expect(normalizeFileExtension('', 'main.py')).toBe('py');
    expect(normalizeFileExtension()).toBe('');
  });
});

describe('resolveFileKind', () => {
  it('源码与配置类扩展名归为 code', () => {
    for (const type of ['py', 'ts', 'vue', 'json', 'yml', 'toml', 'sh', 'dockerfile', 'makefile']) {
      expect(resolveFileKind(type)).toBe('code');
    }
  });

  it('md / html / 图片 / 纯文本各自独立分类', () => {
    expect(resolveFileKind('md')).toBe('markdown');
    expect(resolveFileKind('markdown')).toBe('markdown');
    expect(resolveFileKind('htm')).toBe('html');
    expect(resolveFileKind('png')).toBe('image');
    expect(resolveFileKind('svg')).toBe('image');
    expect(resolveFileKind('rst')).toBe('text');
  });

  it('Office 文档与未登记扩展名兜底为 binary', () => {
    for (const type of ['pdf', 'docx', 'xlsx', 'pptx', 'csv', 'zip', '']) {
      expect(resolveFileKind(type)).toBe('binary');
    }
  });
});
