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

import type { IAgentModule } from '../agent';
import type { IHttpModule } from '../http';
import type { IMessageModule } from '../message';
import type { ISessionModule } from '../session';
import type { IMediatorModule } from './type';

/**
 * 中介者模块
 * 负责协调各个模块之间的通信，避免模块之间的循环依赖
 */
export const useMediator = (): IMediatorModule => {
  return {
    agent: null,
    http: null,
    message: null,
    session: null,

    registerAgent(agent: IAgentModule) {
      this.agent = agent;
    },

    registerHttp(http: IHttpModule) {
      this.http = http;
    },

    registerMessage(message: IMessageModule) {
      this.message = message;
    },

    registerSession(session: ISessionModule) {
      this.session = session;
    },
  };
};

export type { IMediatorModule } from './type';
