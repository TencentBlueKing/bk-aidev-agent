import { describe, expect, it } from 'vitest';

import { buildMenuSources } from '../build-menu-sources';
import type { IHostResourceItem, IHostSkillItem } from '../../types';

describe('buildMenuSources', () => {
  it('maps skill id to skill_code and name to skill_name', () => {
    const skills: IHostSkillItem[] = [
      {
        skill_code: 'code_review',
        skill_name: '代码审查',
        description: '审查代码',
        icon: 'icon-skill',
      },
    ];

    expect(buildMenuSources({ skills })).toEqual([
      {
        type: 'skill',
        id: 'code_review',
        name: '代码审查',
        description: '审查代码',
        icon: 'icon-skill',
      },
    ]);
  });

  it('maps tool and mcp id to code', () => {
    const resources: IHostResourceItem[] = [
      { type: 'tool', name: '搜索工具', code: 'search_tool', id: 1, icon: 'icon-tool' },
      { type: 'mcp', name: '监控 MCP', code: 'monitor_mcp', id: 2, icon: 'icon-mcp' },
    ];

    expect(buildMenuSources({ resources })).toEqual([
      { type: 'tool', id: 'search_tool', name: '搜索工具', icon: 'icon-tool' },
      { type: 'mcp', id: 'monitor_mcp', name: '监控 MCP', icon: 'icon-mcp' },
    ]);
  });

  it('maps knowledgebase id to stringified numeric id', () => {
    const resources: IHostResourceItem[] = [
      { type: 'knowledgebase', name: '运维知识库', code: 'ops_kb', id: 58, icon: 'icon-kb' },
    ];

    expect(buildMenuSources({ resources })).toEqual([
      { type: 'knowledgebase', id: '58', name: '运维知识库', icon: 'icon-kb' },
    ]);
  });

  it('falls back to code when knowledgebase id is null', () => {
    const resources: IHostResourceItem[] = [
      { type: 'knowledgebase', name: '运维知识库', code: 'ops_kb', id: null, icon: null },
    ];

    expect(buildMenuSources({ resources })).toEqual([
      { type: 'knowledgebase', id: 'ops_kb', name: '运维知识库', icon: null },
    ]);
  });

  it('keeps original type for both doc and knowledgebase', () => {
    const resources: IHostResourceItem[] = [
      { type: 'doc', name: '旧知识库', code: 'legacy_doc', id: 9, icon: '' },
      { type: 'knowledgebase', name: '新知识库', code: 'new_kb', id: 10, icon: '' },
    ];

    const result = buildMenuSources({ resources });
    expect(result.map(item => item.type)).toEqual(['doc', 'knowledgebase']);
    expect(result.map(item => item.id)).toEqual(['9', '10']);
  });

  it('falls back to code when doc id is null', () => {
    const resources: IHostResourceItem[] = [{ type: 'doc', name: '旧知识库', code: 'legacy_doc', id: null, icon: '' }];

    expect(buildMenuSources({ resources })[0].id).toBe('legacy_doc');
  });

  it('discards shortcut, file, artifact, unknown type, and empty id', () => {
    const resources: IHostResourceItem[] = [
      { type: 'shortcut', name: '总结', code: 'summary', id: 1, icon: '' },
      { type: 'file', name: '上传文件', code: 'file', id: 'f1', icon: '' },
      { type: 'artifact', name: '产物', code: 'art', id: 'a1', icon: '' },
      { type: 'unknown', name: '未知', code: 'unk', id: 3, icon: '' },
      { type: 'tool', name: '空标识', icon: '' },
      { type: 'tool', name: '有效工具', code: 'valid_tool', id: 4, icon: '' },
    ];

    expect(buildMenuSources({ resources })).toEqual([
      { type: 'tool', id: 'valid_tool', name: '有效工具', icon: '' },
    ]);
  });

  it('uses full prompt text for both name and content without truncation', () => {
    const prompts = ['这是一段很长的提示词，用于验证菜单搜索按全文匹配且不会被截断'];

    expect(buildMenuSources({ prompts })).toEqual([
      {
        type: 'prompt',
        id: 'prompt-0',
        name: prompts[0],
        content: prompts[0],
      },
    ]);
  });

  it('merges skills, resources, and prompts in that order', () => {
    const result = buildMenuSources({
      skills: [{ skill_code: 's1', skill_name: 'Skill 1' }],
      resources: [{ type: 'tool', name: 'Tool 1', code: 't1', id: 1, icon: '' }],
      prompts: ['p1', 'p2'],
    });

    expect(result.map(item => `${item.type}:${item.id}`)).toEqual([
      'skill:s1',
      'tool:t1',
      'prompt:prompt-0',
      'prompt:prompt-1',
    ]);
  });

  it('falls back to stringified id when tool/mcp code is missing', () => {
    const resources: IHostResourceItem[] = [{ type: 'tool', name: '无 code 工具', id: 99, icon: '' }];

    expect(buildMenuSources({ resources })[0].id).toBe('99');
  });
});
