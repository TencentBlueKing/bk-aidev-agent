/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { getCookieByName } from '../utils';

export const lang = getCookieByName('blueking_language') || 'zh-cn';

export const langData = {
  小鲸: 'BK GPT',
  关闭: 'close',
  发送: 'Send',
  请输入: 'Please input',
  昨天: 'yesterday',
  '3天前': '3 days ago',
  '5天前': '5 days ago',
  '1周前': '1 week ago',
  更早: 'Older',
  删除: 'Delete',
  恢复默认大小: 'Restore default size',
  'AI 小鲸': 'AI BK GPT',
  新增会话: 'New chat',
  历史会话: 'History session',
  停止生成: 'Stop generating',
  复制: 'Copy',
  编辑: 'Edit',
  今天: 'Today',
  搜索会话名称: 'Search session name',
  重命名: 'Rename',
  自动生成命名: 'Auto generate name',
  分享会话: 'Share session',
  无智能体使用权限: 'No permission to use this agent',
  暂无使用权限: 'No permission',
  请输入新的会话名称: 'Please enter new session name',
  '确认删除会话 ?': 'Confirm delete session?',
  搜索为空: 'No search results',
  暂无对话: 'No conversations',
  转人工: 'Transfer to human',
  缩小高度: 'Shrink height',
  全选: 'Select all',
  取消: 'Cancel',
  确定: 'Confirm',
  分享链接已复制到剪贴板: 'Share link copied to clipboard',
  请求失败: 'Request failed',
} as const;

export const zhLangData = {
  重命名: '重命名',
  自动生成命名: '自动生成命名',
  分享会话: '分享会话',
  全选: '全选',
  取消: '取消',
  确定: '确定',
  分享链接已复制到剪贴板: '分享链接已复制到剪贴板',
  请求失败: '请求失败',
};

export const t = (key: string) => {
  if (lang !== 'en') return zhLangData[key as keyof typeof zhLangData] || key;

  return langData[key as keyof typeof langData] || key;
};
