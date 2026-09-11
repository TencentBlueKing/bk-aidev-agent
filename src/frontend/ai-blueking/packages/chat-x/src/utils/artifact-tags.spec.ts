import { describe, expect, it } from 'vitest';

import { appendArtifactTags, omitArtifactTags, toArtifactTagNode } from './artifact-tags';

import type { AIFileInfo } from '../ag-ui/types/file';
import type { TagSchema } from '../types/input';

const createFile = (overrides: Partial<AIFileInfo> = {}): AIFileInfo => ({
  name: 'bk_apigw_resources_bp-aidev-develop (7).yaml',
  outputId: 'files/bk_apigw_resources_bp-aidev-develop_7.yaml',
  size: 1909,
  type: 'yaml',
  ...overrides,
});

const artifactTag = {
  type: 'tag',
  data: {
    type: 'artifact',
    label: 'bk_apigw_resources_bp-aidev-develop (7).yaml',
    value: 'files/bk_apigw_resources_bp-aidev-develop_7.yaml',
    icon: '',
    description: '',
  },
};

const kbTag = {
  type: 'tag',
  data: { type: 'knowledgebase', label: '运维知识库', value: '58', icon: '', description: '' },
};

const textLine = [{ type: 'text', text: '分析这个文件' }] as unknown as TagSchema[number];

describe('toArtifactTagNode', () => {
  it('maps name to label and outputId to value', () => {
    expect(toArtifactTagNode(createFile())).toEqual(artifactTag);
  });
});

describe('appendArtifactTags', () => {
  it('appends attachments as one trailing artifact tag line', () => {
    const doc = [textLine] as TagSchema;

    expect(appendArtifactTags(doc, [createFile()])).toEqual([textLine, [artifactTag]]);
  });

  it('keeps tags already inserted via the @ menu and appends the attachment after them', () => {
    const doc = [[kbTag]] as unknown as TagSchema;

    expect(appendArtifactTags(doc, [createFile()])).toEqual([[kbTag], [artifactTag]]);
  });

  it('does not append again when the same file is already tagged (edit refill)', () => {
    const doc = [textLine, [artifactTag]] as unknown as TagSchema;

    expect(appendArtifactTags(doc, [createFile()])).toEqual(doc);
  });

  it('skips files without outputId and returns the document untouched', () => {
    const doc = [textLine] as TagSchema;

    expect(appendArtifactTags(doc, [createFile({ outputId: '' })])).toBe(doc);
    expect(appendArtifactTags(doc, [])).toBe(doc);
  });
});

describe('omitArtifactTags', () => {
  it('strips artifact tags whose value matches an attachment outputId', () => {
    const doc = [textLine, [artifactTag]] as unknown as TagSchema;

    expect(omitArtifactTags(doc, [{ outputId: 'files/bk_apigw_resources_bp-aidev-develop_7.yaml' }])).toEqual([
      textLine,
    ]);
  });

  it('matches history attachments that only carry id', () => {
    const doc = [textLine, [artifactTag]] as unknown as TagSchema;

    expect(omitArtifactTags(doc, [{ id: 'files/bk_apigw_resources_bp-aidev-develop_7.yaml' }])).toEqual([textLine]);
  });

  it('keeps non-artifact tags and artifact tags not backed by an attachment', () => {
    const artifactFromMenu = {
      type: 'tag',
      data: { type: 'artifact', label: '操作文档.docx', value: 'files/doc.docx', icon: '', description: '' },
    };
    const doc = [[kbTag, artifactFromMenu], [artifactTag]] as unknown as TagSchema;

    expect(omitArtifactTags(doc, [{ outputId: 'files/bk_apigw_resources_bp-aidev-develop_7.yaml' }])).toEqual([
      [kbTag, artifactFromMenu],
    ]);
  });

  it('preserves blank lines the user typed', () => {
    const doc = [textLine, [], [artifactTag]] as unknown as TagSchema;

    expect(omitArtifactTags(doc, [{ outputId: 'files/bk_apigw_resources_bp-aidev-develop_7.yaml' }])).toEqual([
      textLine,
      [],
    ]);
  });

  it('returns the document untouched when there is no attachment', () => {
    const doc = [textLine, [artifactTag]] as unknown as TagSchema;

    expect(omitArtifactTags(doc, [])).toBe(doc);
  });
});
