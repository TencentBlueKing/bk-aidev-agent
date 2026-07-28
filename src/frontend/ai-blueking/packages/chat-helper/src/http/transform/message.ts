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

import { ActivityType, MessageRole, MessageType } from '../../message/type';

import type {
  IActivityMessage,
  IActivityMessageApi,
  IAssistantMessage,
  IAssistantMessageApi,
  IBinaryInputContent,
  IBinaryInputContentApi,
  IDeveloperMessage,
  IDeveloperMessageApi,
  IGuideMessage,
  IGuideMessageApi,
  IHiddenAssistantMessage,
  IHiddenAssistantMessageApi,
  IHiddenGuideMessage,
  IHiddenGuideMessageApi,
  IHiddenMessage,
  IHiddenMessageApi,
  IHiddenSystemMessage,
  IHiddenSystemMessageApi,
  IHiddenUserMessage,
  IHiddenUserMessageApi,
  IInfoMessage,
  IInfoMessageApi,
  IInputContent,
  IInputContentApi,
  IKnowledgeRag,
  IKnowledgeRagApi,
  IMessage,
  IMessageApi,
  IMessageArtifact,
  IPauseMessage,
  IPauseMessageApi,
  IPlaceholderMessage,
  IPlaceholderMessageApi,
  IReasoningMessage,
  IReasoningMessageApi,
  IReferenceDocument,
  IReferenceDocumentApi,
  ISystemMessage,
  ISystemMessageApi,
  ITemplateAssistantMessage,
  ITemplateAssistantMessageApi,
  ITemplateGuideMessage,
  ITemplateGuideMessageApi,
  ITemplateHiddenMessage,
  ITemplateHiddenMessageApi,
  ITemplateSystemMessage,
  ITemplateSystemMessageApi,
  ITemplateUserMessage,
  ITemplateUserMessageApi,
  IToolCall,
  IToolCallApi,
  IToolMessage,
  IToolMessageApi,
  IUserMessage,
  IUserMessageApi,
} from '../../message/type';

/**
 * 将 API 返回的消息数据转换为前端使用的消息数据
 * @param data API 返回的消息数据
 * @returns 前端使用的消息数据
 */
export const transferMessageApi2Message = (data: IMessageApi): IMessage => {
  const baseMessage = {
    id: data.id,
    messageId: data.message_id,
    name: data.name,
    role: data.role,
    sessionCode: data.session_code,
    status: data.status,
  };

  // 处理不同类型的消息
  switch (data.role) {
    case MessageRole.Activity: {
      const activityData = data as IActivityMessageApi;
      const transferReferenceDocumentApi2ReferenceDocument = (doc: IReferenceDocumentApi): IReferenceDocument =>
        doc.map(item => ({
          name: item.name,
          originFileUrl: item.origin_file_url,
          url: item.url,
        }));

      let content: IActivityMessage['content'];
      switch (activityData.activity_type) {
        case ActivityType.ReferenceDocument:
          content = transferReferenceDocumentApi2ReferenceDocument(activityData.content as IReferenceDocumentApi);
          break;
        case ActivityType.KnowledgeRag: {
          const ragContent = activityData.content as IKnowledgeRagApi;
          content = {
            content: ragContent.content,
            referenceDocument: transferReferenceDocumentApi2ReferenceDocument(ragContent.reference_document),
          };
          break;
        }
        case ActivityType.FlowAgent:
        case ActivityType.ArtifactsGenerated:
        default:
          content = activityData.content as IActivityMessage['content'];
          break;
      }

      const result: IActivityMessage = {
        ...baseMessage,
        activityType: activityData.activity_type,
        content,
        property: activityData.property,
        role: activityData.role,
      };
      return result;
    }

    case MessageRole.Assistant: {
      const assistantData = data as IAssistantMessageApi;
      const result: IAssistantMessage = {
        ...baseMessage,
        content: assistantData.content,
        property: assistantData.property,
        role: assistantData.role,
        toolCalls: assistantData.tool_calls?.map((toolCall: IToolCallApi): IToolCall => {
          return {
            function: {
              arguments: toolCall['function'].arguments,
              name: toolCall['function'].name,
              description: toolCall['function'].description,
              mcpName: toolCall['function'].mcp_name,
            },
            id: toolCall.id,
            type: toolCall.type,
          };
        }),
      };
      return result;
    }

    case MessageRole.Developer: {
      const developerData = data as IDeveloperMessageApi;
      const result: IDeveloperMessage = {
        ...baseMessage,
        content: developerData.content,
        role: developerData.role,
      };
      return result;
    }

    case MessageRole.Guide: {
      const guideData = data as IGuideMessageApi;
      const result: IGuideMessage = {
        ...baseMessage,
        content: guideData.content,
        role: guideData.role,
      };
      return result;
    }

    case MessageRole.Hidden: {
      const hiddenData = data as IHiddenMessageApi;
      const result: IHiddenMessage = {
        ...baseMessage,
        content: hiddenData.content,
        role: hiddenData.role,
      };
      return result;
    }

    case MessageRole.HiddenAssistant: {
      const hiddenAssistantData = data as IHiddenAssistantMessageApi;
      const result: IHiddenAssistantMessage = {
        ...baseMessage,
        content: hiddenAssistantData.content,
        role: hiddenAssistantData.role,
      };
      return result;
    }

    case MessageRole.HiddenGuide: {
      const hiddenGuideData = data as IHiddenGuideMessageApi;
      const result: IHiddenGuideMessage = {
        ...baseMessage,
        content: hiddenGuideData.content,
        role: hiddenGuideData.role,
      };
      return result;
    }

    case MessageRole.HiddenSystem: {
      const hiddenSystemData = data as IHiddenSystemMessageApi;
      const result: IHiddenSystemMessage = {
        ...baseMessage,
        content: hiddenSystemData.content,
        role: hiddenSystemData.role,
      };
      return result;
    }

    case MessageRole.HiddenUser: {
      const hiddenUserData = data as IHiddenUserMessageApi;
      const result: IHiddenUserMessage = {
        ...baseMessage,
        content: hiddenUserData.content,
        role: hiddenUserData.role,
      };
      return result;
    }

    case MessageRole.Info: {
      const infoData = data as IInfoMessageApi;
      const result: IInfoMessage = {
        ...baseMessage,
        content: infoData.content,
        role: infoData.role,
      };
      return result;
    }

    case MessageRole.Pause: {
      const pauseData = data as IPauseMessageApi;
      const result: IPauseMessage = {
        ...baseMessage,
        content: pauseData.content,
        role: pauseData.role,
      };
      return result;
    }

    case MessageRole.Placeholder: {
      const placeholderData = data as IPlaceholderMessageApi;
      const result: IPlaceholderMessage = {
        ...baseMessage,
        content: placeholderData.content,
        role: placeholderData.role,
      };
      return result;
    }

    case MessageRole.Reasoning: {
      const reasoningData = data as IReasoningMessageApi;
      const result: IReasoningMessage = {
        ...baseMessage,
        content: reasoningData.content,
        duration: reasoningData.duration,
        role: reasoningData.role,
      };
      return result;
    }

    case MessageRole.System: {
      const systemData = data as ISystemMessageApi;
      const result: ISystemMessage = {
        ...baseMessage,
        content: systemData.content,
        role: systemData.role,
      };
      return result;
    }

    case MessageRole.TemplateAssistant: {
      const templateAssistantData = data as ITemplateAssistantMessageApi;
      const result: ITemplateAssistantMessage = {
        ...baseMessage,
        content: templateAssistantData.content,
        role: templateAssistantData.role,
      };
      return result;
    }

    case MessageRole.TemplateGuide: {
      const templateGuideData = data as ITemplateGuideMessageApi;
      const result: ITemplateGuideMessage = {
        ...baseMessage,
        content: templateGuideData.content,
        role: templateGuideData.role,
      };
      return result;
    }

    case MessageRole.TemplateHidden: {
      const templateHiddenData = data as ITemplateHiddenMessageApi;
      const result: ITemplateHiddenMessage = {
        ...baseMessage,
        content: templateHiddenData.content,
        role: templateHiddenData.role,
      };
      return result;
    }

    case MessageRole.TemplateSystem: {
      const templateSystemData = data as ITemplateSystemMessageApi;
      const result: ITemplateSystemMessage = {
        ...baseMessage,
        content: templateSystemData.content,
        role: templateSystemData.role,
      };
      return result;
    }

    case MessageRole.TemplateUser: {
      const templateUserData = data as ITemplateUserMessageApi;
      const result: ITemplateUserMessage = {
        ...baseMessage,
        content: templateUserData.content,
        role: templateUserData.role,
      };
      return result;
    }

    case MessageRole.Tool: {
      const toolData = data as IToolMessageApi;
      const result: IToolMessage = {
        ...baseMessage,
        content: toolData.content,
        duration: toolData.duration,
        error: toolData.error,
        role: toolData.role,
        toolCallId: toolData.tool_call_id,
      };
      return result;
    }

    case MessageRole.User: {
      const userData = data as IUserMessageApi;
      const userContent = userData.content;
      const result: IUserMessage = {
        ...baseMessage,
        content: Array.isArray(userContent)
          ? userContent.map((item: IInputContentApi): IInputContent => {
              if (item.type === MessageType.Binary) {
                const binaryItem = item as IBinaryInputContentApi;
                return {
                  data: binaryItem.data,
                  filename: binaryItem.filename,
                  id: binaryItem.id,
                  mimeType: binaryItem.mime_type,
                  type: binaryItem.type,
                  url: binaryItem.url,
                } satisfies IBinaryInputContent;
              }
              return item;
            })
          : userContent,
        property: userData.property,
        role: userData.role,
      };
      return result;
    }

    case MessageRole.Interrupt: {
      const result = {
        ...baseMessage,
        ...data,
      };
      return result;
    }
  }
};

/**
 * 将前端使用的消息数据转换为 API 使用的消息数据
 * @param data 前端使用的消息数据
 * @returns API 使用的消息数据
 */
export const transferMessage2MessageApi = (data: IMessage): IMessageApi => {
  const baseMessage = {
    id: data.id,
    message_id: data.messageId,
    name: data.name,
    role: data.role,
    session_code: data.sessionCode,
    status: data.status,
  };

  // 处理不同类型的消息
  switch (data.role) {
    case MessageRole.Activity: {
      const activityData = data as IActivityMessage;
      const transferReferenceDocument2ReferenceDocumentApi = (doc: IReferenceDocument): IReferenceDocumentApi =>
        doc.map(item => ({
          name: item.name,
          origin_file_url: item.originFileUrl,
          url: item.url,
        }));

      let content: IActivityMessageApi['content'];
      switch (activityData.activityType) {
        case ActivityType.ReferenceDocument:
          content = transferReferenceDocument2ReferenceDocumentApi(activityData.content as IReferenceDocument);
          break;
        case ActivityType.KnowledgeRag: {
          const ragContent = activityData.content as IKnowledgeRag;
          content = {
            content: ragContent.content,
            reference_document: transferReferenceDocument2ReferenceDocumentApi(ragContent.referenceDocument),
          };
          break;
        }
        case ActivityType.FlowAgent:
        case ActivityType.ArtifactsGenerated:
        default:
          content = activityData.content as IActivityMessageApi['content'];
          break;
      }

      const result: IActivityMessageApi = {
        ...baseMessage,
        activity_type: activityData.activityType,
        content,
        property: activityData.property,
        role: activityData.role,
      };
      return result;
    }

    case MessageRole.Assistant: {
      const assistantData = data as IAssistantMessage;
      const result: IAssistantMessageApi = {
        ...baseMessage,
        property: assistantData.property,
        content: assistantData.content,
        role: assistantData.role,
        tool_calls: assistantData.toolCalls?.map((toolCall: IToolCall): IToolCallApi => {
          return {
            function: {
              arguments: toolCall['function'].arguments,
              name: toolCall['function'].name,
              description: toolCall['function'].description,
              mcp_name: toolCall['function'].mcpName,
            },
            id: toolCall.id,
            type: toolCall.type,
          };
        }),
      };
      return result;
    }

    case MessageRole.Developer: {
      const developerData = data as IDeveloperMessage;
      const result: IDeveloperMessageApi = {
        ...baseMessage,
        content: developerData.content,
        role: developerData.role,
      };
      return result;
    }

    case MessageRole.Guide: {
      const guideData = data as IGuideMessage;
      const result: IGuideMessageApi = {
        ...baseMessage,
        content: guideData.content,
        role: guideData.role,
      };
      return result;
    }

    case MessageRole.Hidden: {
      const hiddenData = data as IHiddenMessage;
      const result: IHiddenMessageApi = {
        ...baseMessage,
        content: hiddenData.content,
        role: hiddenData.role,
      };
      return result;
    }

    case MessageRole.HiddenAssistant: {
      const hiddenAssistantData = data as IHiddenAssistantMessage;
      const result: IHiddenAssistantMessageApi = {
        ...baseMessage,
        content: hiddenAssistantData.content,
        role: hiddenAssistantData.role,
      };
      return result;
    }

    case MessageRole.HiddenGuide: {
      const hiddenGuideData = data as IHiddenGuideMessage;
      const result: IHiddenGuideMessageApi = {
        ...baseMessage,
        content: hiddenGuideData.content,
        role: hiddenGuideData.role,
      };
      return result;
    }

    case MessageRole.HiddenSystem: {
      const hiddenSystemData = data as IHiddenSystemMessage;
      const result: IHiddenSystemMessageApi = {
        ...baseMessage,
        content: hiddenSystemData.content,
        role: hiddenSystemData.role,
      };
      return result;
    }

    case MessageRole.HiddenUser: {
      const hiddenUserData = data as IHiddenUserMessage;
      const result: IHiddenUserMessageApi = {
        ...baseMessage,
        content: hiddenUserData.content,
        role: hiddenUserData.role,
      };
      return result;
    }

    case MessageRole.Info: {
      const infoData = data as IInfoMessage;
      const result: IInfoMessageApi = {
        ...baseMessage,
        content: infoData.content,
        role: infoData.role,
      };
      return result;
    }

    case MessageRole.Pause: {
      const pauseData = data as IPauseMessage;
      const result: IPauseMessageApi = {
        ...baseMessage,
        content: pauseData.content,
        role: pauseData.role,
      };
      return result;
    }

    case MessageRole.Placeholder: {
      const placeholderData = data as IPlaceholderMessage;
      const result: IPlaceholderMessageApi = {
        ...baseMessage,
        content: placeholderData.content,
        role: placeholderData.role,
      };
      return result;
    }

    case MessageRole.Reasoning: {
      const reasoningData = data as IReasoningMessage;
      const result: IReasoningMessageApi = {
        ...baseMessage,
        content: reasoningData.content,
        duration: reasoningData.duration,
        role: reasoningData.role,
      };
      return result;
    }

    case MessageRole.System: {
      const systemData = data as ISystemMessage;
      const result: ISystemMessageApi = {
        ...baseMessage,
        content: systemData.content,
        role: systemData.role,
      };
      return result;
    }

    case MessageRole.TemplateAssistant: {
      const templateAssistantData = data as ITemplateAssistantMessage;
      const result: ITemplateAssistantMessageApi = {
        ...baseMessage,
        content: templateAssistantData.content,
        role: templateAssistantData.role,
      };
      return result;
    }

    case MessageRole.TemplateGuide: {
      const templateGuideData = data as ITemplateGuideMessage;
      const result: ITemplateGuideMessageApi = {
        ...baseMessage,
        content: templateGuideData.content,
        role: templateGuideData.role,
      };
      return result;
    }

    case MessageRole.TemplateHidden: {
      const templateHiddenData = data as ITemplateHiddenMessage;
      const result: ITemplateHiddenMessageApi = {
        ...baseMessage,
        content: templateHiddenData.content,
        role: templateHiddenData.role,
      };
      return result;
    }

    case MessageRole.TemplateSystem: {
      const templateSystemData = data as ITemplateSystemMessage;
      const result: ITemplateSystemMessageApi = {
        ...baseMessage,
        content: templateSystemData.content,
        role: templateSystemData.role,
      };
      return result;
    }

    case MessageRole.TemplateUser: {
      const templateUserData = data as ITemplateUserMessage;
      const result: ITemplateUserMessageApi = {
        ...baseMessage,
        content: templateUserData.content,
        role: templateUserData.role,
      };
      return result;
    }

    case MessageRole.Tool: {
      const toolData = data as IToolMessage;
      const result: IToolMessageApi = {
        ...baseMessage,
        content: toolData.content,
        duration: toolData.duration,
        error: toolData.error,
        role: toolData.role,
        tool_call_id: toolData.toolCallId,
      };
      return result;
    }

    case MessageRole.User: {
      const userData = data as IUserMessage;
      const userContent = userData.content;
      const result: IUserMessageApi = {
        ...baseMessage,
        content: Array.isArray(userContent)
          ? userContent.map((item: IInputContent): IInputContentApi => {
              if (item.type === MessageType.Binary) {
                const binaryItem = item as IBinaryInputContent;
                return {
                  data: binaryItem.data,
                  filename: binaryItem.filename,
                  id: binaryItem.id,
                  mime_type: binaryItem.mimeType,
                  type: binaryItem.type,
                  url: binaryItem.url,
                } satisfies IBinaryInputContentApi;
              }
              return item;
            })
          : userContent,
        property: userData.property,
        role: userData.role,
      };
      return result;
    }

    case MessageRole.Interrupt: {
      const result = {
        ...baseMessage,
        ...data,
      };
      return result;
    }
  }
};

/**
 * 将历史/快照中的 artifacts_generated activity 合并到前一条 Assistant 的 property.artifacts，
 * 并过滤掉该 activity（UI 只从 Assistant.property.artifacts 渲染）。
 * 实时 SSE 已写过 property.artifacts；历史回填依赖此归一化。
 */
export const mergeArtifactsActivityIntoMessages = (messages: IMessage[]): IMessage[] => {
  const result: IMessage[] = [];

  for (const message of messages) {
    if (message.role !== MessageRole.Activity) {
      result.push(message);
      continue;
    }

    const activity = message as IActivityMessage;
    if (activity.activityType !== ActivityType.ArtifactsGenerated) {
      result.push(message);
      continue;
    }

    const artifacts = (activity.content as { artifacts?: IMessageArtifact[] } | undefined)?.artifacts;

    // status=empty 或无产物：丢弃 activity，不渲染
    if (!artifacts?.length) {
      continue;
    }

    const activityTurnId = activity.property?.turn_id;
    let matchedByTurn = -1;
    let nearestAssistant = -1;

    for (let i = result.length - 1; i >= 0; i -= 1) {
      if (result[i].role !== MessageRole.Assistant) {
        continue;
      }
      const candidate = result[i] as IAssistantMessage;
      if (nearestAssistant < 0) {
        nearestAssistant = i;
      }
      if (activityTurnId && candidate.property?.turn_id === activityTurnId) {
        matchedByTurn = i;
        break;
      }
    }

    const targetIndex = matchedByTurn >= 0 ? matchedByTurn : nearestAssistant;
    if (targetIndex >= 0) {
      const assistant = result[targetIndex] as IAssistantMessage;
      result[targetIndex] = {
        ...assistant,
        property: {
          ...assistant.property,
          artifacts,
        },
      };
    }
    // 始终丢弃 artifacts_generated activity
  }

  return result;
};
