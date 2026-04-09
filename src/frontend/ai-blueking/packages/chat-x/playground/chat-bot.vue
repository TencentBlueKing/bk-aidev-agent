<template>
  <div
    class="ai-blueking-container"
    :style="{
      flexDirection: customPlacement === 'right' ? 'row-reverse' : 'row',
    }"
  >
    <div
      :id="rawMessageSlotId"
      class="ai-blueking-container-slot"
      :style="{
        [customPlacement === 'left' ? 'borderRightColor' : 'borderLeftColor']: '#f0f1f5',
      }"
    ></div>
    <div class="chat-bot">
      <!-- Chat Message列表 -->
      <MessageContainer
        :messages="messages"
        :on-action="handleAction"
        :on-user-input-confirm="handleUserInputConfirm"
        :on-user-shortcut-confirm="handleUserShortcutConfirm"
        :selected-messages="selectedMessages"
        @update:selected-messages="handleUpdateSelectedMessages"
      >
        <template #default="{ message, messageToolsStatus }">
          <MessageRender
            :message="message"
            :message-tools-status="messageToolsStatus"
            :on-action="handleAction"
          />
        </template>
      </MessageContainer>
      <!-- 快捷指令Form 与 Chat Input 互斥渲染 -->
      <ShortcutRender
        v-if="selectedShortcut?.components?.length"
        v-bind="selectedShortcut"
        @close="handleCloseShortcut"
        @submit="handleSubmitShortcut"
      />
      <template v-else>
        <ChatInput
          cite="sadf';asdkfkadsjflkjasdlfkjas;kldfj;lkasdjflkadsjf;klasdjf;klasdf"
          :model-value="userInput"
          :on-send-message="handleSendMessage"
          :on-stop-sending="handleStopSending"
          :on-upload="handleUpload"
          :prompts="MOCK_PROMPTS"
          :resources="MOCK_RESOURCES"
          :shortcut-id="selectedShortcut?.id"
          :shortcuts="shortcuts"
          @delete-shortcut="handleDeleteShortcut"
          @select-shortcut="handleSelectShortcut"
          @update:model-value="handleUpdateInputValue"
        >
        </ChatInput>
      </template>
    </div>
  </div>
  <!-- 快捷指令划选弹窗 -->
  <AiSelection
    v-model:visible="aiSelectionVisible"
    :max-shortcut-count="2"
    :shortcuts="shortcuts"
    @select-shortcut="handleSelectShortcut"
    @selection-change="handleSelectionChange"
  />
</template>

<script setup lang="ts">
  import { ref as deepRef, onMounted, shallowRef } from 'vue';

  import { AgentIcon, CopyIcon, EditIcon, MessageContainer, MessageToolsStatus } from '../src';

  // import CustomMessage from './custom-message/custom-message.vue';
  // import { streamConten } from './markdown';
  declare global {
    interface AIBluekingContentMap {
      custom: {
        data: {
          content: string;
          id: string;
          name: string;
          slot?: string;
        };
        type: 'custom';
      };
    }
    interface AIBluekingMessageMap {
      custom: BaseMessage<
        'custom',
        {
          content: string;
          id: string;
          name: string;
          slot?: string;
        }
      >;
    }
  }

  // import { t } from '../lang/lang';
  import {
    type AssistantMessage,
    type BaseMessage,
    type Message,
    type UserMessage,
    AiSelection,
    ChatInput,
    MessageRender,
    MessageRole,
    MessageStatus,
    ShortcutRender,
    useGlobalConfig,
  } from '../src';
  import { streamContent } from './markdown';
  // import CustomContent from './custom-content.vue';
  // import { AIBluekingIcon, CopyIcon, ShareIcon } from './icons';
  import { MOCK_PROMPTS, MOCK_RESOURCES } from './mock';
  import { uploadFileToSession } from './upload-file';

  import type { Shortcut, TagSchema } from '../src/types';
  import type { IToolBtn } from '../src/types/tool';

  import '../src/styles/global.scss';
  withDefaults(
    defineProps<{
      customPlacement?: 'left' | 'right';
    }>(),
    {
      customPlacement: 'left',
    },
  );

  const aiSelectionVisible = shallowRef(false);
  const userInput = shallowRef<string | TagSchema>([
    [
      {
        type: 'text',
        text: '你好 啊 ',
      },
      {
        type: 'tag',
        data: {
          type: 'tool',
          label: '工具1',
          value: '工具1',
        },
      },
      {
        type: 'text',
        text: ' 你好 啊 ',
      },
    ],
  ]);
  const selectedShortcut = deepRef<null | Shortcut>(null);
  const messages = deepRef<Message[]>([
    {
      id: 107,
      role: 'user',
      sessionCode: 'new_session_1770040871957',
      status: 'complete',
      content: '云桌面黑屏怎么处理',
      property: null,
    },
    {
      role: 'activity',
      activityType: 'knowledge_rag',
      content: {
        content: '开始召回知识\n重排召回结果中\n完成召回并分类\n',
        referenceDocument: [
          {
            originFile: 'https://example.com/knowledge/cloud-desktop/black-screen',
            url: 'https://example.com/docs/cloud-desktop-black-screen',
            name: '【云桌面】云桌面启动后黑屏',
          },
          {
            originFile: 'https://example.com/knowledge/cloud-desktop/stgame-error',
            url: 'https://example.com/docs/cloud-desktop-stgame-error',
            name: '【云桌面】无法打开云桌面，提示STGameOpt遇到未知错误',
          },
          {
            originFile: 'https://example.com/knowledge/cloud-desktop/disconnect',
            url: 'https://example.com/docs/cloud-desktop-disconnect',
            name: '【云桌面】云桌面正常使用出现闪退，再次登录提示"与服务器断开连接"',
          },
          {
            originFile: 'https://example.com/knowledge/cloud-desktop/dual-window',
            url: 'https://example.com/docs/cloud-desktop-dual-window',
            name: '【云桌面】本地环境出现两个START窗口',
          },
          {
            originFile: 'https://example.com/knowledge/cloud-desktop/no-response',
            url: 'https://example.com/docs/cloud-desktop-no-response',
            name: '【云桌面】蓝盾客户端启动云桌面无反应',
          },
          {
            originFile: 'https://example.com/knowledge/cloud-desktop/notes',
            url: 'https://example.com/docs/cloud-desktop-notes',
            name: '【云桌面】云桌面使用注意事项',
          },
        ],
      },
      status: 'streaming',
    },
    {
      role: 'assistant',
      content: '尝试重新云桌面；如权限，联系PM协助处理。重启，客户端"求助"获取人工服务',
      status: 'complete',
      messageId: 'lc_run--019c1ea9-1bc2-76d2-9c70-6d0056a27e3d',
    },
    {
      role: 'user',
      content: '你好啊adsfasdfasdf',
      status: 'complete',
      messageId: 'lc_run--019c1ea9-1bc2-76d2-9c70-6d0056a27e3d',
    },
  ]);
  const shortcuts = shallowRef<Shortcut[]>([
    {
      name: 'Trace 分析',
      id: 'trace_analysis',
      icon: () => EditIcon,
      components: [
        {
          name: '项目名称',
          key: 'project_name',
          type: 'text',
          default: '',
          placeholder: '请输入项目名称',
          required: true,
          fillBack: true,
          fillRegx: /^[a-zA-Z0-9]+$/,
        },
        {
          name: '数量',
          key: 'quantity',
          default: '10',
          type: 'number',
          min: 1,
          max: 100,
          required: true,
          fillBack: false,
        },
        {
          name: '项目描述',
          key: 'description',
          type: 'textarea',
          rows: 4,
          required: false,
          fillBack: false,
        },
        {
          name: '项目类型',
          key: 'project_type',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: '类型A', value: 'A' },
            { label: '类型B', value: 'B' },
          ],
        },
      ],
    },
    {
      name: '翻译',
      id: 'translate',
      icon: () => CopyIcon,
      components: [
        {
          name: '内容',
          key: 'content',
          type: 'textarea',
          default: '',
          placeholder: '请输入项目名称',
          required: false,
          fillBack: true,
        },
      ],
    },
    {
      name: '输入AI',
      id: 'input_ai_1',
      icon: () => CopyIcon,
    },
    {
      name: '深度思考',
      id: 'input_ai_2',
      icon: () => CopyIcon,
    },
    {
      name: '重新生成',
      id: 'input_ai_3',
      icon: () => AgentIcon,
    },
    {
      name: '引用',
      id: 'input_ai_4',
      icon: () => CopyIcon,
    },
    {
      name: '点赞',
      id: 'input_ai_5',
      icon: () => AgentIcon,
    },
    {
      name: '不满意',
      id: 'input_ai_6',
      icon: () => AgentIcon,
    },
    {
      name: '删除',
      id: 'input_ai_7',
      icon: () => AgentIcon,
    },
    {
      name: '输入AI',
      id: 'input_ai_8',
      icon: () => AgentIcon,
    },
  ]);
  const selectedMessages = shallowRef<Message[]>([]);
  const { rawMessageSlotId } = useGlobalConfig();

  const handleAction = async (tool: IToolBtn) => {
    console.log('tool: ', tool);
    await new Promise(resolve => setTimeout(resolve, 2000));
    if (tool.id === 'like' || tool.id === 'unlike') {
      return tool.id === 'like'
        ? [
            'MCP/工具调用准确',
            'MCP/工具功能执行到位',
            '文档召回准确',
            '知识匹配精准',
            '指令执行准确',
            '快捷操作高效',
            '响应迅速及时',
            '回答即时流畅',
          ]
        : [
            'MCP/工具调用不准确',
            'MCP/工具功能执行不到位',
            '文档召回不准确',
            '知识匹配不精准',
            '指令执行不准确',
            '快捷操作不高效',
            '响应不迅速及时',
            '回答不即时流畅',
          ];
    }
  };
  const handleSelectionChange = (text: string) => {
    console.log('Selection changed:', text);
  };

  const handleSelectShortcut = (shortcut: Shortcut, text?: string) => {
    console.log('shortcut: ', shortcut, text);
    userInput.value = text || '';
    selectedShortcut.value = {
      ...shortcut,
    };
  };
  const handleDeleteShortcut = () => {
    selectedShortcut.value = null;
    userInput.value = '';
  };
  const handleCloseShortcut = () => {
    selectedShortcut.value = null;
    userInput.value = '';
  };
  const handleSendMessage = async (message: UserMessage['content'], docSchema: TagSchema) => {
    console.log('value: ', message, 'docSchema: ', docSchema);
    userInput.value = [[]];
    messages.value.push({
      id: 'aaa',
      role: MessageRole.User,
      content: message,
      messageId: 'aaa',
      status: MessageStatus.Complete,
      // property: {
      //   extra: {
      //     cite: {
      //       data: [
      //         {
      //           key: 'test',
      //           value: 'test',
      //         },
      //       ],
      //       type: 'structured',
      //       title: '我是谁',
      //     },
      //     command: 'test',
      //     context: [
      //       {
      //         __key: 'testes',
      //         testes: 'test',
      //         __label: 'test',
      //         __value: 'test',
      //         context_type: 'text',
      //       },
      //       {
      //         context_test: 'vk',
      //       },
      //     ],
      //   },
      // },
    } as UserMessage);
    await new Promise(resolve => setTimeout(resolve, 5000));
  };
  const handleStopSending = async () => {
    console.log('stop sending');
  };
  const handleSubmitShortcut = (formModel: Record<string, unknown>) => {
    console.log('formModel: ', formModel);
    selectedShortcut.value = null;
    userInput.value = '';
  };
  const handleUpload = async (file: File) => {
    const response = await uploadFileToSession({
      file,
      sessionCode: 'demo_session',
      accessToken: import.meta.env.VITE_ACCESS_TOKEN || '',
    });
    console.log('response: ', response);
    return response?.data as { download_url?: string };
  };
  const handleUserInputConfirm = async (message: Message, content: UserMessage['content'], docSchema: TagSchema) => {
    console.log('message: ', message, 'content: ', content, 'docSchema: ', docSchema);
  };
  const handleUserShortcutConfirm = async (message: Message, formModel: Record<string, unknown>) => {
    console.log('message: ', message, 'formModel: ', formModel);
  };
  const handleUpdateSelectedMessages = (mes?: Message[]) => {
    console.log('selectedMessages: ', mes);
    selectedMessages.value = mes ?? [];
    setTimeout(() => {
      selectedMessages.value = [];
    }, 3000);
  };
  const handleUpdateInputValue = (value: string | TagSchema, selectedResourceList: IAiSlashMenuItem[]) => {
    console.log('value: ', value, 'selectedResourceList: ', selectedResourceList);
    userInput.value = value;
  };
  onMounted(() => {
    // let index = 0;
    let content = '';
    const chunkSize = 1000000000000000;
    // 使用普通模板字符串，LaTeX 命令需要双反斜杠转义
    let rawContent = String.raw`${streamContent}`;
    const interval = setInterval(() => {
      // content += markdownContentList[index] + '\n';
      content += streamContent.slice(content.length, content.length + chunkSize);
      let status = MessageStatus.Streaming;
      // if (index === markdownContentList.length - 1) {
      //   status = MessageStatus.Complete;
      // } else {
      //   status = MessageStatus.Streaming;
      // }
      status = content.length >= streamContent.length ? MessageStatus.Complete : MessageStatus.Streaming;
      const message = messages.value.find(message => message.id === 'bbb');
      if (message) {
        message.content = content;
        message.status = status;
      } else {
        messages.value.push({
          id: 'bbb',
          role: MessageRole.Assistant,
          messageId: 'bbb',
          status,
          content,
        } as AssistantMessage);
      }
      // index++;
      if (content.length >= streamContent.length) {
        clearInterval(interval);
      }
    }, 16);
  });
</script>

<style lang="scss">
  .ai-blueking-container {
    display: flex;
    min-width: 400px;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 2px 12px 0 #0003;

    .chat-bot {
      display: flex;
      flex: 1;
      flex-direction: column;
      align-items: center;
      min-width: 200px;
      max-width: 700px;
      height: 80vh;
      margin: 10px;
    }

    &-slot {
      width: fit-content;
      max-width: 50%;
      overflow: auto;
      background: #f5f7fa;
      border: 1px solid transparent;

      &:empty {
        border: none;
      }
    }
  }
</style>
