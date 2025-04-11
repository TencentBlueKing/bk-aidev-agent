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
import { getCookieByName } from '../utils';

export const lang = getCookieByName('blueking_language') || 'zh-cn';

export const langData = {
  小鲸: 'BK GPT',
  向下收缩: 'shrink down',
  向上扩展: 'expand upward',
  清空聊天记录: 'Empty chat records',
  关闭: 'close',
  '内容正在执行中，请执行完成后再发送':
    'The content is being executed, please send it after the execution is completed.',
  发送: 'Send',
  '您可以键入 “/” 查看更多Prompt': 'You can type "/" to see more Prompts',
  请输入: 'Please input',
  返回最新: 'Latest',
  终止生成: 'Stop',
  向上滚动加载更多记录: 'Scroll up to load more records',
  日: ' sunday',
  一: ' monday',
  二: ' tuesday',
  三: ' wednesday',
  四: ' thursday',
  五: ' friday',
  六: ' saturday',
  昨天: 'yesterday',
  本周: 'this week',
  上周: 'last week',
  复制成功: 'Copy success',
  您选择的文本内容: 'The text content you selected',
  问小鲸: 'Ask BK GPT',
  想对选中的文本做什么: 'What do you want to do with the selected text?',
  translateShortcut: `You are a highly skilled AI trained in language translation. I would like you to translate the text delimited by triple quotes (Translation of Chinese into English and other languages into Chinese), ensuring that the translation is colloquial and authentic.
    Only give me the output and nothing else. Do not wrap responses in quotes
    '''
      {{ SELECTED_TEXT }}
    '''
    `,
  explanationShortcut: `You are a professional explainer. Please provide a detailed explanation of "{{ SELECTED_TEXT }}". Your explanation should include: 1) basic meaning and conceptual explanation; 2) practical applications or use cases; 3) if it's a technical term, please provide relevant technical background; 4) where appropriate, provide specific examples to aid understanding. Use clear and accessible language to ensure non-experts can understand. If the word/phrase has multiple meanings, please list the main definitions. Keep your response concise and clear while ensuring completeness and accuracy of information.`,
  翻译: 'translate',
  解释: 'explanation',
  'AI小鲸正在回复，请结束后再清空': 'AI BK GPT is executing, please clear after completion',
  '输入 "/" 唤出 Prompt\n通过 Shift + Enter 进行换行输入':
    'Input "/" to call out Prompt\nUse Shift + Enter to enter a new line',
  '你好，我是小鲸': 'Hello, I am BK GPT',
  '输入你的问题，助你高效的完成工作': 'Input your question, help you complete work efficiently',
  框选内容: 'Selected content',
  '最小化，将缩成锚点': 'Minimize, will shrink to a anchor',
  复制失败: 'Copy failed',
  取消: 'Cancel',
  请输入内容: 'Please input content',
  删除: 'Delete',
  扩展高度: 'Expand height',
  缩小高度: 'Shrink height',
  恢复默认大小: 'Restore default size',
  无匹配结果: 'No matching results',
  'AI 小鲸': 'AI BK GPT',
} as const;

export const zhLangData = {
  translateShortcut: `你是受过语言翻译训练的高技能人工智能。我想让你把用三引号分隔的文本翻译(中文翻译成英文，其他语言翻译成中文)，确保译文口语化、地道。
    只给我输出结果，其他内容一概不要。请勿用引号将回复包起来
    '''
      {{ SELECTED_TEXT }}
    '''`,
  explanationShortcut: `您是一位专业的解释者。请详细解释“{{ SELECTED_TEXT }}”。您的解释应包括 1) 基本含义和概念解释；2) 实际应用或使用案例；3) 如果是技术术语，请提供相关技术背景；4) 适当时提供具体示例，以帮助理解。使用清晰易懂的语言，确保非专业人员也能理解。如果该词/短语有多种含义，请列出主要定义。在确保信息完整性和准确性的同时，请保持答复简洁明了。`,
};

export const t = (key: string) => {
  if (lang !== 'en') return zhLangData[key as keyof typeof zhLangData] || key;
  return langData[key as keyof typeof langData] || key;
};
