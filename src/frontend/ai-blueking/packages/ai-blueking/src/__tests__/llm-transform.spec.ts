import { describe, expect, it } from 'vitest';

import { transferLlmApi2LlmItem, transferLlmListApi2LlmItems } from '@blueking/chat-helper';

describe('transferLlmApi2LlmItem', () => {
  it('should normalize missing fields with safe defaults', () => {
    const result = transferLlmApi2LlmItem({
      llm_code: 'hy3-preview',
      llm_name: '混元3',
      property: null,
    });

    expect(result).toEqual({
      id: 0,
      llm_code: 'hy3-preview',
      llm_name: '混元3',
      llm_type: 'chat.completion',
      icon: '',
      description: '',
      base_model: undefined,
      max_token_size: 0,
      property: {},
      space_auth_mode: '',
      user_auth_mode: '',
      tag_names: undefined,
    });
  });

  it('should keep provided fields', () => {
    const result = transferLlmApi2LlmItem({
      id: 9,
      llm_code: 'deepseek',
      llm_name: 'DeepSeek',
      llm_type: 'chat.completion',
      icon: 'https://example.com/icon.png',
      description: 'desc',
      base_model: 'deepseek',
      max_token_size: 64000,
      property: { support_thinking: true, default: true },
      space_auth_mode: 'APPLY',
      user_auth_mode: 'PUBLIC',
      tag_names: ['new'],
    });

    expect(result.id).toBe(9);
    expect(result.icon).toBe('https://example.com/icon.png');
    expect(result.property.support_thinking).toBe(true);
    expect(result.space_auth_mode).toBe('APPLY');
  });
});

describe('transferLlmListApi2LlmItems', () => {
  it('should return empty array for non-array input', () => {
    expect(transferLlmListApi2LlmItems(null)).toEqual([]);
    expect(transferLlmListApi2LlmItems(undefined)).toEqual([]);
  });

  it('should map list items', () => {
    const list = transferLlmListApi2LlmItems([
      { llm_code: 'a', llm_name: 'A' },
      { llm_code: 'b', llm_name: 'B', id: 2 },
    ]);
    expect(list).toHaveLength(2);
    expect(list[0].llm_code).toBe('a');
    expect(list[1].id).toBe(2);
  });
});
