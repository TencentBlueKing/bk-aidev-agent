/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { useAgent } from './agent';
import { useHttp } from './http';
import { useMediator } from './mediator';
import { useMessage } from './message';
import { useSession } from './session';

import type { IUseChatHelperOptions } from './type';

export * from './agent';
export * from './event';
export * from './http';
export * from './mediator';
export * from './message';
export * from './session';
export * from './type';

/**
 * Chat Helper 主入口
 * 使用中介者模式协调各个模块之间的通信
 */
export const useChatHelper = (options: IUseChatHelperOptions) => {
  // 创建中介者
  const mediator = useMediator();

  // 创建各个模块
  const http = useHttp(options);
  const agent = useAgent(mediator, options.protocol);
  const message = useMessage(mediator);
  const session = useSession(mediator);

  // 注册所有模块
  mediator.registerHttp(http);
  mediator.registerMessage(message);
  mediator.registerAgent(agent);
  mediator.registerSession(session);

  // 重置所有模块
  const reset = (options: IUseChatHelperOptions) => {
    http.reset(options);
    agent.reset(options.protocol);
    message.reset();
    session.reset();
  };

  return {
    agent,
    session,
    message,
    http,
    reset,
  };
};
