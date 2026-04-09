/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

export { default as HistoryGroup } from './ai-header/history-dropdown/history-group.vue';
export { default as HistoryItem } from './ai-header/history-dropdown/history-item.vue';
export { default as HistorySearch } from './ai-header/history-dropdown/history-search.vue';
// 历史下拉组件（原子组件）
export { default as HistoryDropdown } from './ai-header/history-dropdown/index.vue';
export type * from './ai-header/history-dropdown/types';

export { useHistoryDropdown } from './ai-header/history-dropdown/use-history-dropdown';
export { default as AIHeader } from './ai-header/index.vue';
export type * from './ai-header/types';
export { default as ChatBot } from './chat-bot.vue';
// 选择模式底部操作栏组件
// export { default as SelectionFooter } from './selection-footer/selection-footer.vue';

export type * from './types';
