/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { describe, expect, it } from 'vitest';

import { transferAgentInfoApi2AgentInfo } from './agent';

describe('transferAgentInfoApi2AgentInfo', () => {
  it('maps agent_type to agentType', () => {
    const result = transferAgentInfoApi2AgentInfo({
      agent_name: '验证devops-skill',
      agent_type: 'claw',
    });
    expect(result.agentType).toBe('claw');
  });

  it('leaves agentType undefined when agent_type is absent', () => {
    const result = transferAgentInfoApi2AgentInfo({
      agent_name: '验证devops-skill',
    });
    expect(result.agentType).toBeUndefined();
  });

  it('maps agent_type single without special handling', () => {
    const result = transferAgentInfoApi2AgentInfo({
      agent_name: '验证devops-skill',
      agent_type: 'single',
    });
    expect(result.agentType).toBe('single');
  });
});
