/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/**
 * 消息基础接口，用于泛型约束
 */
interface IMessageLike {
  id?: number | string;
  role: string;
}

/**
 * 在消息列表中查找目标消息之前最近的用户消息
 *
 * @description 遍历消息列表，找到目标消息之前最后一条 role 为 'user' 且有 id 的消息。
 * 常用于：
 * - 提交反馈时找到对应的用户消息 ID
 * - 删除 AI 消息组时找到关联的用户消息
 * - 重新生成时找到原始的用户消息
 *
 * @param messages - 完整的消息列表
 * @param targetMessage - 目标消息（通常是 AI 消息组的第一条）
 * @returns 用户消息，如果未找到则返回 null
 */
export function findLastUserMessageBefore<T extends IMessageLike>(messages: T[], targetMessage: T): null | T {
  let lastUserMessage: null | T = null;

  for (const m of messages) {
    if (m.role === 'user' && m.id !== undefined) {
      lastUserMessage = m;
    }
    if (m === targetMessage) {
      break;
    }
  }

  return lastUserMessage;
}

/**
 * 获取用户消息的数字 ID
 *
 * @description 便捷函数，组合 findLastUserMessageBefore 和 ID 提取
 *
 * @param messages - 完整的消息列表
 * @param targetMessage - 目标消息（通常是 AI 消息组的第一条）
 * @returns 用户消息的数字 ID，如果未找到则返回 undefined
 */
export function findLastUserMessageIdBefore<T extends IMessageLike>(
  messages: T[],
  targetMessage: T,
): number | undefined {
  const userMessage = findLastUserMessageBefore(messages, targetMessage);
  if (userMessage?.id !== undefined) {
    return typeof userMessage.id === 'number' ? userMessage.id : Number(userMessage.id);
  }
  return undefined;
}
