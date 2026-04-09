/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { AGUIProtocol } from '@blueking/chat-helper';

import type { IEventEmitter } from '../manager/business/types';

/**
 * Protocol 配置选项
 */
export interface ProtocolOptions {
  /** 事件发射器 */
  eventEmitter?: IEventEmitter | null;
  /** 流式响应完成回调 */
  onDone?: () => void;
  /** 发生错误回调 */
  onError?: (error: unknown) => void;
  /** 每次接收到事件回调 */
  onMessage?: (event: any) => void;
  /** 流式响应开始回调 */
  onStart?: () => void;
  /** 文本块回调 */
  onTextChunk?: (event: any) => void;
}

/**
 * 扩展 AGUIProtocol 的自定义类
 *
 * 可以重写特定事件处理方法
 */
export class BluekingProtocol extends AGUIProtocol {
  private eventEmitter?: IEventEmitter | null;

  constructor(options: ProtocolOptions = {}) {
    super({
      onStart: options.onStart,
      onMessage: options.onMessage,
      onDone: options.onDone,
      onError: options.onError,
    });

    this.eventEmitter = options.eventEmitter;
  }

  /**
   * 重写运行错误事件处理
   */
  handleRunErrorEvent(event: any) {
    super.handleRunErrorEvent(event);

    // 显示自定义错误消息
    this.eventEmitter?.emit('run-error', { event });
  }

  /**
   * 重写文本消息块事件处理
   */
  handleTextMessageChunkEvent(event: any) {
    // 调用父类方法
    super.handleTextMessageChunkEvent(event);

    // 触发自定义事件
    this.eventEmitter?.emit('text-chunk', { event });
  }

  /**
   * 重写思考结束事件处理
   */
  handleThinkingEndEvent(event: any) {
    super.handleThinkingEndEvent(event);

    this.eventEmitter?.emit('thinking-end', { event });
  }

  /**
   * 重写思考开始事件处理
   */
  handleThinkingStartEvent(event: any) {
    super.handleThinkingStartEvent(event);

    this.eventEmitter?.emit('thinking-start', { event });
  }

  /**
   * 重写工具调用结束事件处理
   */
  handleToolCallEndEvent(event: any) {
    super.handleToolCallEndEvent(event);

    this.eventEmitter?.emit('tool-call-end', { event });
  }

  /**
   * 重写工具调用开始事件处理
   */
  handleToolCallStartEvent(event: any) {
    super.handleToolCallStartEvent(event);

    this.eventEmitter?.emit('tool-call-start', { event });
  }
}

/**
 * 创建小鲸自定义 Protocol
 *
 * 集成小鲸的事件处理逻辑
 *
 * @param options Protocol 配置选项
 * @returns AGUIProtocol 实例
 */
export function createBluekingProtocol(options: ProtocolOptions = {}): AGUIProtocol {
  const { eventEmitter, onStart, onMessage, onDone, onError, onTextChunk } = options;

  return new AGUIProtocol({
    // 流式响应开始
    onStart: () => {
      // 触发事件
      eventEmitter?.emit('receive-start', {});

      // 执行自定义回调
      onStart?.();
    },

    // 每次接收到事件
    onMessage: (event: any) => {
      // 触发事件
      eventEmitter?.emit('receive-message', { event });

      // 处理特定事件类型
      if (event.type === 'TextMessageChunk' && onTextChunk) {
        onTextChunk(event);
      }

      // 执行自定义回调
      onMessage?.(event);
    },

    // 流式响应完成
    onDone: () => {
      // 触发事件
      eventEmitter?.emit('receive-end', {});

      // 执行自定义回调
      onDone?.();
    },

    // 发生错误
    onError: (error: unknown) => {
      // 触发事件
      eventEmitter?.emit('receive-error', { error });

      // 执行自定义回调
      onError?.(error);
    },
  });
}
