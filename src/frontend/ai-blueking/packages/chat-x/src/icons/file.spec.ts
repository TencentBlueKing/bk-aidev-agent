import { describe, expect, it } from 'vitest';
import type { VNode } from 'vue';

import { ArtifactTabIcon } from './file';

/** 设计稿节点 947-13413 导出的文档图标 path */
const FIGMA_ARTIFACT_TAB_PATH =
  'M3.5 14C3.22386 14 3 13.8082 3 13.5715L3 5.04938L6.71864 2L12.5 2C12.7761 2 13 2.192 13 2.42854L13 13.5715C13 13.8082 12.7761 14 12.5 14L3.5 14ZM3.90909 13.0769L12.0909 13.0769L12.0909 2.92308L7.77273 2.92308L7.77273 5.03069C7.77273 5.52292 7.32409 5.92308 6.77273 5.92308L3.90909 5.92308L3.90909 13.0769ZM4.50727 5L6.77273 5C6.81523 5 6.84568 4.98985 6.86364 4.98085L6.86363 3.06777L4.50727 5ZM5 8.5L5 7.5L11 7.5L11 8.5L5 8.5ZM7 10L7 9L11 9L11 10L7 10ZM5.5 12L5.5 11L11 11L11 12L5.5 12Z';

describe('ArtifactTabIcon', () => {
  it('应使用设计稿 16×16 文档图标', () => {
    expect(ArtifactTabIcon.props?.viewBox).toBe('0 0 16 16');
    const pathNode = (ArtifactTabIcon.children as VNode[])?.[0];
    expect(pathNode?.props?.d).toBe(FIGMA_ARTIFACT_TAB_PATH);
  });
});
