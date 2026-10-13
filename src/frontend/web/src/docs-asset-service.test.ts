import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { after, before, describe, it } from 'node:test';

import { DocsAssetService, type DocsAssetResult } from './docs-asset-service';

const PAGES: Record<string, string> = {
  'index.html': '<html><head></head><body>home</body></html>',
  'guide/introductions.html': '<html><head></head><body>introductions</body></html>',
  'demos/index.html': '<html><head></head><body>demos overview</body></html>',
};

let staticDir = '';
let service: DocsAssetService;

function bodyOf(result: DocsAssetResult): string {
  assert.equal(result.kind, 'text');
  return result.kind === 'text' ? result.body : '';
}

describe('DocsAssetService 无后缀地址', () => {
  before(() => {
    staticDir = fs.mkdtempSync(path.join(os.tmpdir(), 'docs-asset-'));
    for (const [rel, html] of Object.entries(PAGES)) {
      fs.mkdirSync(path.dirname(path.join(staticDir, rel)), { recursive: true });
      fs.writeFileSync(path.join(staticDir, rel), html);
    }
    service = new DocsAssetService({ staticDir, basePath: '/docs' });
  });

  after(() => fs.rmSync(staticDir, { recursive: true, force: true }));

  it('映射到同名 .html 页面', () => {
    assert.match(bodyOf(service.handleGet('/guide/introductions')), /introductions/);
  });

  it('目录地址映射到目录下的 index.html', () => {
    assert.match(bodyOf(service.handleGet('/demos/')), /demos overview/);
    assert.match(bodyOf(service.handleGet('/demos')), /demos overview/);
  });

  it('找不到对应页面时回退到首页', () => {
    assert.match(bodyOf(service.handleGet('/guide/missing')), /home/);
    assert.match(bodyOf(service.handleGet('/')), /home/);
  });

  it('不会解析到静态目录之外', () => {
    const outside = path.join(path.dirname(staticDir), 'docs-asset-outside.html');
    fs.writeFileSync(outside, 'outside');
    try {
      assert.match(bodyOf(service.handleGet('/../docs-asset-outside')), /home/);
    } finally {
      fs.rmSync(outside, { force: true });
    }
  });
});
