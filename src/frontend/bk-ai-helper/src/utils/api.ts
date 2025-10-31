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

/**
 * API 请求配置
 */
export interface ApiConfig {
  baseUrl: string
  headers?: Record<string, string>
  prompt?: string
}

/**
 * 聊天完成请求参数
 */
export interface ChatCompletionRequest {
  chat_prompts: ChatPrompt[]
  execute_kwargs: {
    stream: boolean
  }
}

/**
 * 聊天完成响应数据
 */
export interface ChatCompletionResponse {
  // 根据实际返回结构定义
  result: boolean
  data: {
    choices: {
      delta: {
        content: string
      }
    }[]
  }
}

/**
 * 聊天提示词接口
 */
export interface ChatPrompt {
  content: string
  role: string
}

/**
 * 发送聊天完成请求
 * @param content - 用户输入的内容
 * @param config - API 配置
 * @returns 聊天完成响应
 */
export async function sendChatRequest(content: string, config: ApiConfig): Promise<ChatCompletionResponse> {
  const url = `${config.baseUrl}/chat_completion/`

  const chatPrompts = [
    {
      role: "user",
      content,
    },
  ]

  if (config.prompt) {
    chatPrompts.unshift({ role: "system", content: config.prompt })
  }

  const requestData: ChatCompletionRequest = {
    chat_prompts: chatPrompts,
    execute_kwargs: {
      stream: false,
    },
  }

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...config.headers,
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(requestData),
  })

  if (!response.ok) {
    const errorMessage = `HTTP error! status: ${response.status}`
    throw new Error(errorMessage)
  }

  return await response.json()
}
