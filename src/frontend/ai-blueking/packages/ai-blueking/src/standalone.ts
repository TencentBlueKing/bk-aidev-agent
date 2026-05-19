/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * Standalone bundle：内联 Vue3 runtime，供非 Vue 宿主通过 mount helpers 或同源 h/render 挂载组件。
 * 自定义 side render / slots 请使用本入口导出的 h、render，勿混用外部 vue 包。
 */

// @ts-ignore - icon 资源文件不需要类型检查
import './assets/icon/iconcool.js';
import '../../chat-x/dist/index.css';
import './assets/icon/style.css';

export { createApp, h, render } from 'vue';

export * from './index';

export { mountAIBlueking, mountChatBot } from './standalone-mount';
export {
  mountStandaloneComponent,
  buildStandaloneListeners,
  resolveMountContainer,
  type StandaloneEventHandlers,
  type StandaloneMountHandle,
  type StandaloneMountOptions,
} from './standalone-mount-core';
