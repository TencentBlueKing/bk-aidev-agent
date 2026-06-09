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
import { transferMessageApi2Message } from '../http/transform';
import {
  type IKnowledgeRag,
  type IMessageModule,
  type IReferenceDocument,
  ActivityType,
  MessageRole,
  MessageStatus,
  MessageType,
} from '../message';
import {
  type IActivityDeltaEvent,
  type IActivitySnapshotEvent,
  type ICustomEvent,
  type IEvent,
  type IFlowAgentEndCustomValue,
  type IFlowAgentResultCustomValue,
  type IFlowAgentStartCustomValue,
  type IKnowledgeRagResultCustomValue,
  type IKnowledgeRagTextContentCustomValue,
  type IMessagesSnapshotEvent,
  type IRawEvent,
  type IRunErrorEvent,
  type IRunFinishedEvent,
  type IRunStartedEvent,
  type IStateDeltaEvent,
  type IStateSnapshotEvent,
  type IStepFinishedEvent,
  type IStepStartedEvent,
  type ITempMessageCustomValue,
  type ITextMessageChunkEvent,
  type ITextMessageContentEvent,
  type ITextMessageEndEvent,
  type ITextMessageStartEvent,
  type IThinkingEndEvent,
  type IThinkingStartEvent,
  type IThinkingTextMessageContentEvent,
  type IThinkingTextMessageEndEvent,
  type IThinkingTextMessageStartEvent,
  type IToolCallArgsEvent,
  type IToolCallChunkEvent,
  type IToolCallEndEvent,
  type IToolCallResultEvent,
  type IToolCallStartEvent,
  CustomEventName,
  EventType,
  FlowTaskState,
  IApprovalResultCustomValue,
  RunFinishedOutcomeType,
} from './type';

import type { ISSEProtocol } from '../http/fetch';

/**
 * AGUI 协议
 * @param message - 消息模块
 */
export class AGUIProtocol implements ISSEProtocol {
  public messageModule: IMessageModule;
  private onDoneCallback?: () => void;
  private onErrorCallback?: (error: unknown) => void;
  private onMessageCallback?: (message: IEvent) => void;
  private onStartCallback?: () => void;

  constructor(params?: {
    onDone?: () => void;
    onError?: (error: unknown) => void;
    onMessage?: (message: IEvent) => void;
    onStart?: () => void;
  }) {
    this.onDoneCallback = params?.onDone;
    this.onErrorCallback = params?.onError;
    this.onMessageCallback = params?.onMessage;
    this.onStartCallback = params?.onStart;
  }

  /**
   * 处理活动增量更新事件
   * 使用 JSON Patch 格式增量更新活动数据
   */
  handleActivityDeltaEvent(_event: IActivityDeltaEvent) {}

  /**
   * 处理活动快照事件
   * 记录活动的完整状态
   */
  handleActivitySnapshotEvent(_event: IActivitySnapshotEvent) {}

  /**
   * 处理自定义事件
   */
  handleCustomEvent(event: ICustomEvent) {
    switch (event.name) {
      case CustomEventName.FlowAgentStart:
        this.handleFlowAgentStartCustomEvent(event);
        break;
      case CustomEventName.FlowAgentResult:
        this.handleFlowAgentResultCustomEvent(event);
        break;
      case CustomEventName.FlowAgentEnd:
        this.handleFlowAgentEndCustomEvent(event);
        break;
      case CustomEventName.ReferenceDocument:
        this.handleReferenceDocumentCustomEvent(event);
        break;
      case CustomEventName.KnowledgeRagStart:
        this.handleKnowledgeRagStartCustomEvent(event);
        break;
      case CustomEventName.KnowledgeRagTextContent:
        this.handleKnowledgeRagTextContentCustomEvent(event);
        break;
      case CustomEventName.KnowledgeRagResult:
        this.handleKnowledgeRagResultCustomEvent(event);
        break;
      case CustomEventName.KnowledgeRagEnd:
        this.handleKnowledgeRagEndCustomEvent(event);
        break;
      case CustomEventName.TempMessage:
        this.handleTempMessageCustomEvent(event);
        break;
      case CustomEventName.ApprovalResult:
        this.handleApprovalResultCustomEvent(event);
        break;
      case CustomEventName.FlowAgentUpdate:
        this.handleFlowAgentUpdateCustomEvent(event);
        break;
      default:
        break;
    }
  }

  /**
   * 自定义事件 处理流程编排任务结束
   */
  handleFlowAgentEndCustomEvent(event: ICustomEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message && message.role === MessageRole.Activity && message.activityType === ActivityType.FlowAgent) {
      // 先把最后一个loading消息标记为complete
      message.status = MessageStatus.Complete;
      // 然后创建一个结束消息
      const value = event.value as IFlowAgentEndCustomValue;
      this.messageModule.plusMessage({
        role: MessageRole.Assistant,
        content: value.map(item => item.task_outputs.join('\n')).join('\n'),
        status: MessageStatus.Complete,
      });
    }
  }

  /**
   * 自定义事件 处理流程编排任务结果（增量更新节点状态）
   */
  handleFlowAgentResultCustomEvent(event: ICustomEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message && message.role === MessageRole.Activity && message.activityType === ActivityType.FlowAgent) {
      message.content = event.value as IFlowAgentResultCustomValue;
    }
  }

  /**
   * 自定义事件 处理流程编排任务开始
   */
  handleFlowAgentStartCustomEvent(event: ICustomEvent) {
    const value = event.value as IFlowAgentStartCustomValue;
    this.messageModule.plusMessage({
      role: MessageRole.Activity,
      activityType: ActivityType.FlowAgent,
      content: value.map(item => ({
        nodes: {},
        task_id: Number(item.task_id),
        task_name: '',
        task_outputs: [] as string[],
        task_state: FlowTaskState.Created,
      })),
      status: MessageStatus.Streaming,
    });
  }

  /**
   * 自定义事件 处理流程编排任务更新
   */
  handleFlowAgentUpdateCustomEvent(event: ICustomEvent) {
    const value = event.value as IFlowAgentResultCustomValue;
    this.messageModule.list.value.forEach(item => {
      if (item.role === MessageRole.Activity && item.activityType === ActivityType.FlowAgent) {
        const isSameTask = (item.content as IFlowAgentResultCustomValue)[0].task_id === value[0].task_id;
        // 通过第一个 task_id 判断是否是同一个任务，是的话直接更新消息内容
        if (isSameTask) {
          item.content = value;
        }
      }
    });
  }

  /**
   * 自定义事件 处理意图识别结束
   */
  handleKnowledgeRagEndCustomEvent(_event: ICustomEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message && message.role === MessageRole.Activity && message.activityType === ActivityType.KnowledgeRag) {
      message.status = MessageStatus.Complete;
    }
  }

  /**
   * 自定义事件 处理意图识别结果
   */
  handleKnowledgeRagResultCustomEvent(event: ICustomEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message && message.role === MessageRole.Activity && message.activityType === ActivityType.KnowledgeRag) {
      (message.content as IKnowledgeRag).referenceDocument = event.value as IKnowledgeRagResultCustomValue;
    }
  }

  /**
   * 自定义事件 处理意图识别开始
   */
  handleKnowledgeRagStartCustomEvent(_event: ICustomEvent) {
    this.messageModule.plusMessage({
      role: MessageRole.Activity,
      activityType: ActivityType.KnowledgeRag,
      content: {
        content: '',
        referenceDocument: [],
      },
      status: MessageStatus.Streaming,
    });
  }

  /**
   *  自定义事件 处理意图识别文本
   */
  handleKnowledgeRagTextContentCustomEvent(event: ICustomEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message && message.role === MessageRole.Activity && message.activityType === ActivityType.KnowledgeRag) {
      const value = event.value as IKnowledgeRagTextContentCustomValue;
      (message.content as IKnowledgeRag).content = value.cover
        ? value.chunk.content
        : (message.content as IKnowledgeRag).content + value.chunk.content;
    }
  }

  /**
   * 处理消息快照事件
   * 用于同步多端消息状态
   */
  handleMessagesSnapshotEvent(event: IMessagesSnapshotEvent) {
    if (event.messages && event.messages.length > 0) {
      this.messageModule.list.value = event.messages.map(transferMessageApi2Message);
    }
  }

  /**
   * 处理原始事件
   * 透传底层 AI 服务的原始事件
   */
  handleRawEvent(_event: IRawEvent) {
    // console.log('Raw:', _event);
  }

  /**
   * 自定义事件 处理参考文档事件
   */
  handleReferenceDocumentCustomEvent(event: ICustomEvent) {
    // 可以在这里处理参考文档事件
    this.messageModule.plusMessage({
      role: MessageRole.Activity,
      activityType: ActivityType.ReferenceDocument,
      content: event.value as IReferenceDocument,
      status: MessageStatus.Complete,
    });
  }

  /**
   * 处理运行错误事件
   */
  handleRunErrorEvent(event: IRunErrorEvent) {
    // 先把最后一个loading消息标记为complete
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message) {
      message.status = MessageStatus.Complete;
    }
    // 然后创建一个错误消息
    this.messageModule.plusMessage({
      role: MessageRole.Assistant,
      content: event.message,
      status: MessageStatus.Error,
    });
  }

  /**
   * 处理运行完成事件
   */
  handleRunFinishedEvent(event: IRunFinishedEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message) {
      message.status = MessageStatus.Complete;
    }
    // 如果是中断消息，则创建一个中断消息
    if (event.outcome?.type === RunFinishedOutcomeType.Interrupt) {
      this.messageModule.plusMessage({
        role: MessageRole.Interrupt,
        content: event,
        status: MessageStatus.Pending,
      });
    }
    // 二次返回，直接更新消息内容
    if (event.outcome?.type === RunFinishedOutcomeType.Success) {
      message.content = event;
    }
  }

  /**
   * 处理运行开始事件
   */
  handleRunStartedEvent(_event: IRunStartedEvent) {
    // 运行开始，可以在这里初始化相关状态
  }

  /**
   * 处理状态增量更新事件
   */
  handleStateDeltaEvent(_event: IStateDeltaEvent) {
    // 可以在这里实现 JSON Patch 逻辑
    // console.log('StateDelta:', event);
  }

  /**
   * 处理状态快照事件
   */
  handleStateSnapshotEvent(_event: IStateSnapshotEvent) {
    // console.log('StateSnapshot:', event);
  }

  /**
   * 处理步骤完成事件
   */
  handleStepFinishedEvent(_event: IStepFinishedEvent) {
    // console.log('StepFinished:', _event);
  }

  /**
   * 处理步骤开始事件
   */
  handleStepStartedEvent(_event: IStepStartedEvent) {
    // console.log('StepStarted:', _event);
  }

  /**
   * 自定义事件 处理临时消息，转换为 AI 文本消息
   */
  handleTempMessageCustomEvent(event: ICustomEvent) {
    const value = event.value as ITempMessageCustomValue;
    this.messageModule.plusMessage({
      role: MessageRole.Assistant,
      content: value.message,
      status: value.status,
    });
  }

  /**
   * 自定义事件 处理审批结果
   */
  handleApprovalResultCustomEvent(event: ICustomEvent) {
    const value = event.value as IApprovalResultCustomValue;
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message) {
      message.content = value;
      message.status = MessageStatus.Complete;
    }
  }

  /**
   * 处理文本消息块事件
   */
  handleTextMessageChunkEvent(event: ITextMessageChunkEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message) {
      message.content += event.delta || '';
    } else {
      this.messageModule.plusMessage({
        role: event.role as MessageRole.Assistant,
        content: event.delta || '',
        status: MessageStatus.Complete,
        messageId: event.messageId,
      });
    }
  }

  /**
   * 处理文本消息内容事件（流式输出）
   */
  handleTextMessageContentEvent(event: ITextMessageContentEvent) {
    const message = this.messageModule.getMessageByMessageId(event.messageId);
    if (message) {
      message.content += event.delta;
    }
  }

  /**
   * 处理文本消息结束事件
   */
  handleTextMessageEndEvent(event: ITextMessageEndEvent) {
    const message = this.messageModule.getMessageByMessageId(event.messageId);
    if (message) {
      message.status = MessageStatus.Complete;
    }
  }

  /**
   * 处理文本消息开始事件
   */
  handleTextMessageStartEvent(event: ITextMessageStartEvent) {
    this.messageModule.plusMessage({
      role: event.role as MessageRole.Assistant,
      content: '',
      status: MessageStatus.Streaming,
      messageId: event.messageId,
    });
  }

  /**
   * 处理思考结束事件
   */
  handleThinkingEndEvent(event: IThinkingEndEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message && message.role === MessageRole.Reasoning) {
      message.duration = event.duration;
      message.status = MessageStatus.Complete;
    }
  }

  /**
   * 处理思考开始事件
   */
  handleThinkingStartEvent(_event: IThinkingStartEvent) {
    this.messageModule.plusMessage({
      role: MessageRole.Reasoning,
      content: [],
      status: MessageStatus.Streaming,
    });
  }

  /**
   * 处理思考文本消息内容事件
   */
  handleThinkingTextMessageContentEvent(event: IThinkingTextMessageContentEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message && message.role === MessageRole.Reasoning) {
      message.content[message.content.length - 1] += event.delta;
    }
  }

  /**
   * 处理思考文本消息结束事件
   */
  handleThinkingTextMessageEndEvent(_event: IThinkingTextMessageEndEvent) {
    // console.log(_event);
  }

  /**
   * 处理思考文本消息开始事件
   */
  handleThinkingTextMessageStartEvent(_event: IThinkingTextMessageStartEvent) {
    const message = this.messageModule.getCurrentLoadingMessage();
    if (message && message.role === MessageRole.Reasoning) {
      message.content.push('');
    }
  }

  /**
   * 处理工具调用参数事件
   */
  handleToolCallArgsEvent(event: IToolCallArgsEvent) {
    this.messageModule.list.value.forEach(item => {
      if (item.role === MessageRole.Assistant && item.toolCalls) {
        item.toolCalls.forEach(toolCall => {
          if (toolCall.id === event.toolCallId) {
            toolCall['function'].arguments += event.delta;
          }
        });
      }
    });
  }

  /**
   * 处理工具调用块事件
   */
  handleToolCallChunkEvent(_event: IToolCallChunkEvent) {}

  /**
   * 处理工具调用结束事件
   */
  handleToolCallEndEvent(event: IToolCallEndEvent) {
    this.messageModule.list.value.forEach(item => {
      if (item.role === MessageRole.Assistant && item.toolCalls) {
        if (item.toolCalls.some(toolCall => toolCall.id === event.toolCallId)) {
          item.status = MessageStatus.Complete;
        }
      }
    });
  }

  /**
   * 处理工具调用结果事件
   */
  handleToolCallResultEvent(event: IToolCallResultEvent) {
    this.messageModule.plusMessage({
      role: MessageRole.Tool,
      content: event.content,
      duration: event.duration,
      status: MessageStatus.Complete,
      toolCallId: event.toolCallId,
      messageId: event.messageId,
    });
  }

  /**
   * 处理工具调用开始事件
   */
  handleToolCallStartEvent(event: IToolCallStartEvent) {
    this.messageModule.plusMessage({
      role: MessageRole.Assistant,
      content: '',
      status: MessageStatus.Streaming,
      toolCalls: [
        {
          id: event.toolCallId,
          type: MessageType.Function,
          function: {
            mcpName: event.mcpName,
            name: event.toolCallName,
            arguments: '',
            description: event.description,
          },
        },
      ],
    });
  }

  injectMessageModule(message: IMessageModule) {
    this.messageModule = message;
  }

  onDone() {
    // 回调给上层
    this.onDoneCallback?.();
  }

  onError(error: Error) {
    // 创建一个错误消息
    this.messageModule.plusMessage({
      role: MessageRole.Assistant,
      content: error.message,
      status: MessageStatus.Error,
    });
    // 回调给上层
    this.onErrorCallback?.(error);
  }

  onMessage(message: unknown) {
    const event = message as IEvent;
    // 回调给上层
    this.onMessageCallback?.(event);
    // 处理事件
    switch (event.type) {
      case EventType.ActivityDelta:
        this.handleActivityDeltaEvent(event);
        break;
      case EventType.ActivitySnapshot:
        this.handleActivitySnapshotEvent(event);
        break;
      case EventType.Custom:
        this.handleCustomEvent(event);
        break;
      case EventType.MessagesSnapshot:
        this.handleMessagesSnapshotEvent(event);
        break;
      case EventType.Raw:
        this.handleRawEvent(event);
        break;
      case EventType.RunError:
        this.handleRunErrorEvent(event);
        break;
      case EventType.RunFinished:
        this.handleRunFinishedEvent(event);
        break;
      case EventType.RunStarted:
        this.handleRunStartedEvent(event);
        break;
      case EventType.StateDelta:
        this.handleStateDeltaEvent(event);
        break;
      case EventType.StateSnapshot:
        this.handleStateSnapshotEvent(event);
        break;
      case EventType.StepFinished:
        this.handleStepFinishedEvent(event);
        break;
      case EventType.StepStarted:
        this.handleStepStartedEvent(event);
        break;
      case EventType.TextMessageChunk:
        this.handleTextMessageChunkEvent(event);
        break;
      case EventType.TextMessageContent:
        this.handleTextMessageContentEvent(event);
        break;
      case EventType.TextMessageEnd:
        this.handleTextMessageEndEvent(event);
        break;
      case EventType.TextMessageStart:
        this.handleTextMessageStartEvent(event);
        break;
      case EventType.ThinkingEnd:
        this.handleThinkingEndEvent(event);
        break;
      case EventType.ThinkingStart:
        this.handleThinkingStartEvent(event);
        break;
      case EventType.ThinkingTextMessageContent:
        this.handleThinkingTextMessageContentEvent(event);
        break;
      case EventType.ThinkingTextMessageEnd:
        this.handleThinkingTextMessageEndEvent(event);
        break;
      case EventType.ThinkingTextMessageStart:
        this.handleThinkingTextMessageStartEvent(event);
        break;
      case EventType.ToolCallArgs:
        this.handleToolCallArgsEvent(event);
        break;
      case EventType.ToolCallChunk:
        this.handleToolCallChunkEvent(event);
        break;
      case EventType.ToolCallEnd:
        this.handleToolCallEndEvent(event);
        break;
      case EventType.ToolCallResult:
        this.handleToolCallResultEvent(event);
        break;
      case EventType.ToolCallStart:
        this.handleToolCallStartEvent(event);
        break;
      default:
        break;
    }
  }

  onStart() {
    this.onStartCallback?.();
  }
}
