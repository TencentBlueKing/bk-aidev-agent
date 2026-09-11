import { describe, expect, it } from 'vitest';

import type { TagSchema } from '@blueking/chat-x';

import { buildDocSchemaPayload } from '../build-doc-schema-payload';

const kbDoc: TagSchema = [
  [
    { type: 'text', text: '分析 ' },
    {
      type: 'tag',
      data: {
        type: 'knowledgebase',
        label: '运维知识库',
        value: '58',
        icon: '',
        description: '',
      },
    },
  ],
];

describe('buildDocSchemaPayload', () => {
  it('passes editor document through unchanged including text nodes and 2d structure', () => {
    expect(buildDocSchemaPayload(kbDoc)).toEqual(kbDoc);
  });

  it('passes artifact tags injected by chat-x through as is, without re-deriving them', () => {
    const docWithArtifact: TagSchema = [
      ...kbDoc,
      [
        {
          type: 'tag',
          data: {
            type: 'artifact',
            label: 'bk_apigw_resources_bp-aidev-develop (7).yaml',
            value: 'files/bk_apigw_resources_bp-aidev-develop_7.yaml',
            icon: '',
            description: '',
          },
        },
      ],
    ];

    expect(buildDocSchemaPayload(docWithArtifact)).toEqual(docWithArtifact);
  });

  it('drops empty lines', () => {
    expect(buildDocSchemaPayload([[], ...kbDoc, []])).toEqual(kbDoc);
  });

  it('returns undefined when there is no tag at all', () => {
    expect(buildDocSchemaPayload([[{ type: 'text', text: '普通文本' }]])).toBeUndefined();
    expect(buildDocSchemaPayload([[]])).toBeUndefined();
    expect(buildDocSchemaPayload(undefined)).toBeUndefined();
  });
});
