/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import type { IMessage, IMessageProperty } from '@blueking/chat-helper';

/**
 * 消息基础接口，用于泛型约束
 */
interface IMessageLike {
  id?: number | string;
  role: string;
}

/**
 * 判断消息列表中是否存在「真实会话内容」。
 *
 * pause 预设消息（property.extra.pause）仅用于初始化展示，不算用户发起的真实对话；
 * 其余消息均视为真实内容。
 *
 * 这是「当前会话是否为空」的统一判断口径：sessionContentCount 是后端快照，聊天过程中
 * 不会更新，因此发消息后必须以实时消息列表为准。UI（hasSessionContents）与业务管理器
 * （createNewSession）都应使用此函数，避免两处判断不一致。
 *
 * @param messages 消息列表
 * @returns 是否存在真实会话内容
 */
export function hasRealMessageContent(messages: readonly IMessage[]): boolean {
  return messages.some(msg => {
    if (!('property' in msg)) return true;
    const { property } = msg as { property?: IMessageProperty };
    return !property?.extra?.pause;
  });
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

/**
 * 从用户消息起收集一整轮：含该用户消息，到下一条用户消息之前为止。
 *
 * @description 按对象引用定位，不检查 id。分组后不在消息组里的消息（如挂到 toolCall 上的 tool）
 * 只要落在这一轮的位置区间内也会被收进来。
 *
 * @param messages - 完整的消息列表
 * @param userMessage - 这一轮的用户消息
 * @returns 这一轮的消息；用户消息不在列表中时返回 null
 */
export function collectTurnMessages<T extends IMessageLike>(messages: T[], userMessage: T): null | T[] {
  const startIndex = messages.indexOf(userMessage);
  if (startIndex === -1) {
    return null;
  }

  const turnMessages: T[] = [userMessage];
  for (let index = startIndex + 1; index < messages.length; index++) {
    if (messages[index].role === 'user') {
      break;
    }
    turnMessages.push(messages[index]);
  }
  return turnMessages;
}

/**
 * 由这一轮里的任意一条 AI 消息取出整轮消息（含对应的用户消息）。
 *
 * @description findLastUserMessageBefore 在锚点不在列表中时会返回整个列表最后一条用户消息，
 * 并会跳过没有 id 的用户消息命中更早一轮。删除接口按用户消息 id 删整轮，
 * 所以这两种情况都返回 null，交由调用方放弃操作，避免删错轮次。
 *
 * @param messages - 完整的消息列表
 * @param anchor - 这一轮中的一条 AI 消息（通常是消息组的第一条）
 * @returns 这一轮的消息；无法唯一对应这一轮时返回 null
 */
export function collectTurnMessagesByAnchor<T extends IMessageLike>(messages: T[], anchor: T | undefined): null | T[] {
  const anchorIndex = anchor ? messages.indexOf(anchor) : -1;
  if (anchorIndex === -1) {
    return null;
  }

  const userMessage = findLastUserMessageBefore(messages, anchor as T);
  const userIndex = userMessage ? messages.indexOf(userMessage) : -1;
  if (userIndex === -1 || userIndex > anchorIndex) {
    return null;
  }
  for (let index = userIndex + 1; index < anchorIndex; index++) {
    if (messages[index].role === 'user') {
      return null;
    }
  }

  return collectTurnMessages(messages, messages[userIndex]);
}
