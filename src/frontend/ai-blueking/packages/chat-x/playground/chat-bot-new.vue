<template>
  <div class="button-container">
    <!-- <button
      class="delete-message-button"
      @click="handleDeleteMessage"
    >
      delete message
    </button> -->
    <!-- 侧栏展开/收起已交由外部控制，playground 用按钮模拟业务方入口 -->
    <ToolBtn
      :description="asideCollapsed ? '展开侧栏' : '收起侧栏'"
      @click="asideCollapsed = !asideCollapsed"
    >
      <CollapsedAsideIcon />
    </ToolBtn>
  </div>
  <div class="chat-bot-new">
    <ChatContainer
      v-model:aside-collapsed="asideCollapsed"
      v-model:cite="cite"
      v-model:render-mode="chatMode"
      v-model:selected-model="selectedModel"
      v-model:selected-shortcut="selectedShortcut"
      :enable-selection="false"
      :execution-tab-visible="true"
      :message-tools="customMessageTools"
      :messages="messages"
      :model-value="userInput"
      :models="MOCK_MODELS"
      :on-agent-action="handleAgentAction"
      :on-artifact-click="mockArtifactClick"
      :on-custom-tab-change="handleCustomTabChange"
      :on-interrupt-resume="handleInterruptResume"
      :on-send-message="handleSendMessage"
      :on-stop-sending="handleStopSending"
      :on-upload="handleUpload"
      :on-user-input-confirm="handleUserInputConfirm"
      :on-user-shortcut-confirm="handleUserShortcutConfirm"
      :opening-remark="''"
      :prompts="MOCK_PROMPTS"
      :resize-props="{
        initialDivide: 600,
      }"
      :resources="MOCK_RESOURCES"
      :shortcuts="shortcuts"
      :size="'small'"
      :support-upload="true"
      :timezone="timezone"
      :update-tools="customUpdateTools"
      @confirm-share="handleConfirmShare"
      @delete-shortcut="handleDeleteShortcut"
      @model-change="handleModelChange"
      @select-shortcut="handleSelectShortcut"
      @shortcut-close="handleShortcutClose"
      @shortcut-submit="handleShortcutSubmit"
      @stop-streaming="handleStopStreaming"
      @update:model-value="handleUpdateInputValue"
    >
      <!-- <template #group="{ group }">
        <div class="group-messagesxxxx">
          <div
            v-for="(message, index) in group.messages"
            :key="index"
          >
            <MessageRender
              :key="index"
              :message="message"
              :on-input-confirm="
                (content: UserMessage['content'], docSchema: TagSchema) =>
                  handleUserInputConfirm(message, content, docSchema)
              "
              :on-interrupt-resume="handleInterruptResume"
              :on-shortcut-confirm="
                (formModel: Record<string, unknown>) => handleUserShortcutConfirm(message, formModel)
              "
            >
              <template #answeredQuestion="{ item }">
                <div>{{ JSON.stringify(item) }}</div>
              </template>
            </MessageRender>
          </div>
        </div>
      </template> -->
      <!-- <template #message="{ message, messageToolsStatus, onInterruptResume }">
        <template v-if="message.role === MessageRole.User">
          <MessageRender :message="message"> </MessageRender>
        </template>
        <div
          v-else
          class="xxxxx"
        >
          <template
            v-if="
              message.role === MessageRole.Interrupt && message.content.result?.reason === InterruptReason.UserQuestion
            "
          >
            <InterruptMessageRender
              v-bind="message"
              :on-interrupt-resume="onInterruptResume"
            >
              <template #answeredQuestion="{ item }">
                <div>
                  <div>
                    <span> -------- {{ JSON.stringify(item) }} </span>
                  </div>
                </div>
              </template>
            </InterruptMessageRender>
          </template>
          <MessageRender
            v-else
            :message="message"
            :message-tools-status="messageToolsStatus"
            :on-interrupt-resume="onInterruptResume"
          >
            <template #codeHeader="{ language }">
              <span
                class="code-header-action"
                @click="handleCodeInsert(language)"
              >
                插入
              </span>
              <span
                class="code-header-action"
                @click="handleCodeApply(language)"
              >
                应用
              </span>
            </template>
          </MessageRender>
        </div>
      </template> -->
      <!-- 自定义作答态：用下拉选择替代默认的选项列表，选中后通过 setAnswer 回传已组装答案 -->
      <!-- <template #interruptQuestion="{ question, setAnswer, answer }">
        <div v-if="question.multiSelect">
          <Select
            :model-value="answer?.answer.at(0)?.label"
            @change="
              (value: string) =>
                setAnswer(
                  value
                    ? {
                        question: question.question,
                        multiSelect: question.multiSelect,
                        answer: [{ label: value, description: value }],
                      }
                    : undefined,
                )
            "
          >
            <Select.Option
              v-for="option in question.options ?? []"
              :id="option.label"
              :key="option.label"
              :name="option.description"
            >
            </Select.Option>
          </Select>
        </div>
        <div v-else>
          <UserQuestionChoice
            :on-answer="setAnswer"
            :question="question"
          />
        </div>
      </template> -->
    </ChatContainer>
  </div>
</template>

<script setup lang="ts">
  import { ref as deepRef, onMounted, shallowRef } from 'vue';

  // import { Select } from 'bkui-vue';
  import {
    type ActivityMessage,
    type AssistantMessage,
    type IModelOption,
    type Message,
    type OnInterruptResume,
    type ToolMessage,
    type UserMessage,
    AgentIcon,
    ChatContainer,
    CollapsedAsideIcon,
    CopyIcon,
    DownloadIcon,
    EditIcon,
    MessageContentType,
    MessageRender,
    MessageRole,
    MessageStatus,
    RenderMode,
    UserQuestionChoice,
  } from '../src';
  import ToolBtn from '../src/components/ai-buttons/tool-btn/tool-btn.vue';
  import CustomTabContent from './custom-tab-content.vue';
  import { MOCK_USER_QUESTION_PENDING_MESSAGES } from './interrupt';
  import { streamContent } from './markdown';
  import {
    MOCK_INFO_MESSAGES,
    MOCK_MESSAGES,
    MOCK_MODELS,
    MOCK_PROMPTS,
    MOCK_RESOURCES,
    MOCK_TOOLCALL_STATUS_MESSAGES,
    mockArtifactClick,
  } from './mock';
  import { uploadFileToSession } from './upload-file';

  import type { CustomTab, IAiSlashMenuItem, Shortcut, TagSchema } from '../src/types';
  import type { IToolBtn } from '../src/types/tool';

  import '../src/styles/global.scss';

  const chatMode = shallowRef<RenderMode>(RenderMode.Chat);
  const openingRemark = shallowRef(`你好，我是小鲸
我是由蓝鲸智云开发的智能助手
我可以帮助你完成各种任务`);
  const cite = shallowRef('');
  const asideCollapsed = shallowRef(true);
  const userInput = shallowRef<string | TagSchema>('');
  const selectedShortcut = deepRef<null | Shortcut>(null);
  // 模型选择器：默认选中首个模型（值为 llm_name）
  const selectedModel = shallowRef<string>(MOCK_MODELS[0].llm_name);
  const handleModelChange = (model: IModelOption) => {
    console.log('model change:', model);
  };
  // Info 分隔提示 + ToolCall 各状态 + 含 toolCalls 的会话 mock + 待回答 UserQuestion
  const messages = deepRef<Message[]>([
    ...MOCK_INFO_MESSAGES,
    ...MOCK_TOOLCALL_STATUS_MESSAGES,
    ...(MOCK_MESSAGES as Message[]),
    // ...MOCK_USER_QUESTION_PENDING_MESSAGES,
  ]);

  const handleInterruptResume: OnInterruptResume = (payload, interrupt) => {
    // 取消审批与流程节点重试 / 跳过复用同一回调，业务侧按 payload.operation 分流处理
    console.log('[playground] interrupt resume', payload, interrupt);
  };
  const timezone = shallowRef('America/New_York');

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
        {
          name: '分析维度',
          key: 'analysis_dimensions',
          type: 'checkboxGroup',
          required: false,
          fillBack: false,
          props: {
            modelValue: ['trace', 'metrics'],
            options: [
              { label: '链路 Trace', value: 'trace' },
              { label: '指标 Metrics', value: 'metrics' },
              { label: '日志 Log', value: 'log' },
            ],
          },
        },
        {
          name: '输出粒度',
          key: 'output_granularity',
          type: 'radioGroup',
          required: true,
          fillBack: false,
          props: {
            modelValue: 'summary',
            options: [
              { label: '摘要', value: 'summary' },
              { label: '详细', value: 'detail' },
            ],
          },
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
          placeholder: '请输入要翻译的内容',
          required: false,
          fillBack: true,
        },
      ],
    },
    {
      name: '深度思考',
      id: 'deep_thinking',
      icon: () => CopyIcon,
    },
    {
      name: '重新生成',
      id: 'regenerate',
      icon: () => AgentIcon,
    },
    {
      name: '日志查询',
      id: 'log_query',
      icon: () => EditIcon,
      description: '根据关键词和时间范围查询应用日志',
      components: [
        {
          name: '应用名称',
          key: 'app_name',
          type: 'text',
          placeholder: '请输入应用名称',
          required: true,
          fillBack: true,
        },
        {
          name: '关键词',
          key: 'keyword',
          type: 'text',
          placeholder: '请输入日志关键词',
          required: true,
          fillBack: false,
        },
        {
          name: '日志条数',
          key: 'log_count',
          type: 'number',
          default: '50',
          min: 1,
          max: 500,
          required: false,
          fillBack: false,
        },
      ],
    },
    {
      name: '告警策略配置',
      id: 'alert_config',
      icon: () => AgentIcon,
      description: '快速配置告警策略规则',
      components: [
        {
          name: '策略名称',
          key: 'strategy_name',
          type: 'text',
          placeholder: '请输入策略名称',
          required: true,
          fillBack: false,
        },
        {
          name: '告警级别',
          key: 'alert_level',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: '致命', value: 'fatal' },
            { label: '预警', value: 'warning' },
            { label: '提醒', value: 'info' },
          ],
        },
        {
          name: '是否启用',
          key: 'enabled',
          type: 'switcher',
          default: true,
          required: false,
          fillBack: false,
        },
      ],
    },
    {
      name: '代码审查',
      id: 'code_review',
      icon: () => CopyIcon,
      description: '对代码片段进行审查和优化建议',
      components: [
        {
          name: '代码内容',
          key: 'code_content',
          type: 'textarea',
          rows: 6,
          placeholder: '请粘贴需要审查的代码',
          required: true,
          fillBack: true,
        },
        {
          name: '编程语言',
          key: 'language',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: 'JavaScript', value: 'javascript' },
            { label: 'TypeScript', value: 'typescript' },
            { label: 'Python', value: 'python' },
            { label: 'Go', value: 'go' },
            { label: 'Java', value: 'java' },
          ],
        },
      ],
    },
    {
      name: 'SQL 生成',
      id: 'sql_generator',
      icon: () => EditIcon,
      description: '根据自然语言描述生成 SQL 查询语句',
      components: [
        {
          name: '查询描述',
          key: 'query_desc',
          type: 'textarea',
          rows: 3,
          placeholder: '例如：查询最近7天活跃用户数',
          required: true,
          fillBack: true,
        },
        {
          name: '数据库类型',
          key: 'db_type',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: 'MySQL', value: 'mysql' },
            { label: 'PostgreSQL', value: 'postgresql' },
            { label: 'ClickHouse', value: 'clickhouse' },
          ],
        },
      ],
    },
    {
      name: '性能诊断',
      id: 'perf_diagnosis',
      icon: () => AgentIcon,
      description: '分析应用性能瓶颈并给出优化建议',
    },
    {
      name: '文档生成',
      id: 'doc_generator',
      icon: () => CopyIcon,
      description: '根据代码自动生成 API 文档',
      components: [
        {
          name: '模块名称',
          key: 'module_name',
          type: 'text',
          placeholder: '请输入模块名称',
          required: true,
          fillBack: false,
        },
        {
          name: '文档格式',
          key: 'doc_format',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: 'Markdown', value: 'markdown' },
            { label: 'OpenAPI', value: 'openapi' },
            { label: 'HTML', value: 'html' },
          ],
        },
        {
          name: '包含示例',
          key: 'include_examples',
          type: 'switcher',
          default: true,
          required: false,
          fillBack: false,
        },
      ],
    },
    {
      name: '容器编排',
      id: 'container_orchestration',
      icon: () => EditIcon,
      description: '生成 Kubernetes 部署配置文件',
      components: [
        {
          name: '服务名称',
          key: 'service_name',
          type: 'text',
          placeholder: '请输入服务名称',
          required: true,
          fillBack: false,
        },
        {
          name: '副本数量',
          key: 'replicas',
          type: 'number',
          default: '3',
          min: 1,
          max: 50,
          required: true,
          fillBack: false,
        },
        {
          name: '资源规格',
          key: 'resource_spec',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: '小型 (1C2G)', value: 'small' },
            { label: '中型 (2C4G)', value: 'medium' },
            { label: '大型 (4C8G)', value: 'large' },
            { label: '超大型 (8C16G)', value: 'xlarge' },
          ],
        },
        {
          name: '开启自动扩缩容',
          key: 'auto_scaling',
          type: 'switcher',
          default: false,
          required: false,
          fillBack: false,
        },
      ],
    },
    {
      name: '数据可视化',
      id: 'data_visualization',
      icon: () => AgentIcon,
      description: '将数据转换为图表展示',
      components: [
        {
          name: '图表类型',
          key: 'chart_type',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: '折线图', value: 'line' },
            { label: '柱状图', value: 'bar' },
            { label: '饼图', value: 'pie' },
            { label: '散点图', value: 'scatter' },
            { label: '热力图', value: 'heatmap' },
          ],
        },
        {
          name: '数据源',
          key: 'data_source',
          type: 'textarea',
          rows: 4,
          placeholder: '请粘贴 JSON 格式的数据',
          required: true,
          fillBack: false,
        },
      ],
    },
    {
      name: '接口压测',
      id: 'api_stress_test',
      icon: () => EditIcon,
      description: '对 API 接口进行压力测试',
      components: [
        {
          name: '接口地址',
          key: 'api_url',
          type: 'text',
          placeholder: '请输入接口 URL',
          required: true,
          fillBack: false,
        },
        {
          name: '并发数',
          key: 'concurrency',
          type: 'number',
          default: '100',
          min: 1,
          max: 10000,
          required: true,
          fillBack: false,
        },
        {
          name: '持续时间(秒)',
          key: 'duration',
          type: 'number',
          default: '30',
          min: 5,
          max: 600,
          required: true,
          fillBack: false,
        },
      ],
    },
    {
      name: '单元测试生成',
      id: 'unit_test_gen',
      icon: () => CopyIcon,
      description: '为函数或组件自动生成单元测试',
      components: [
        {
          name: '源代码',
          key: 'source_code',
          type: 'textarea',
          rows: 6,
          placeholder: '请粘贴需要生成测试的源代码',
          required: true,
          fillBack: true,
        },
        {
          name: '测试框架',
          key: 'test_framework',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: 'Vitest', value: 'vitest' },
            { label: 'Jest', value: 'jest' },
            { label: 'Mocha', value: 'mocha' },
          ],
        },
      ],
    },
    {
      name: '正则表达式',
      id: 'regex_helper',
      icon: () => EditIcon,
      description: '根据需求描述生成正则表达式',
    },
    {
      name: 'Git 提交总结',
      id: 'git_commit_summary',
      icon: () => CopyIcon,
      description: '分析 Git 提交记录并生成总结报告',
      components: [
        {
          name: '仓库地址',
          key: 'repo_url',
          type: 'text',
          placeholder: '请输入仓库地址',
          required: true,
          fillBack: false,
        },
        {
          name: '天数',
          key: 'days',
          type: 'number',
          default: '7',
          min: 1,
          max: 90,
          required: false,
          fillBack: false,
        },
      ],
    },
    {
      name: '环境变量管理',
      id: 'env_manager',
      icon: () => AgentIcon,
      description: '管理和同步多环境配置变量',
      components: [
        {
          name: '环境',
          key: 'environment',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: '开发环境', value: 'dev' },
            { label: '测试环境', value: 'test' },
            { label: '预发布环境', value: 'staging' },
            { label: '生产环境', value: 'prod' },
          ],
        },
        {
          name: '变量内容',
          key: 'env_content',
          type: 'textarea',
          rows: 5,
          placeholder: '请输入 KEY=VALUE 格式的环境变量，每行一个',
          required: true,
          fillBack: false,
        },
        {
          name: '加密敏感字段',
          key: 'encrypt_sensitive',
          type: 'switcher',
          default: true,
          required: false,
          fillBack: false,
        },
      ],
    },
    {
      name: '知识库问答',
      id: 'knowledge_qa',
      icon: () => AgentIcon,
      description: '基于企业知识库进行智能问答',
    },
    {
      name: 'CI/CD 流水线',
      id: 'cicd_pipeline',
      icon: () => EditIcon,
      description: '配置持续集成/持续部署流水线',
      components: [
        {
          name: '项目名称',
          key: 'pipeline_project',
          type: 'text',
          placeholder: '请输入项目名称',
          required: true,
          fillBack: false,
        },
        {
          name: '触发方式',
          key: 'trigger_type',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: '代码推送', value: 'push' },
            { label: 'MR/PR 合并', value: 'merge' },
            { label: '定时触发', value: 'cron' },
            { label: '手动触发', value: 'manual' },
          ],
        },
        {
          name: '部署环境',
          key: 'deploy_env',
          type: 'select',
          required: true,
          fillBack: false,
          options: [
            { label: '开发', value: 'dev' },
            { label: '测试', value: 'test' },
            { label: '生产', value: 'prod' },
          ],
        },
        {
          name: '构建超时(分钟)',
          key: 'build_timeout',
          type: 'number',
          default: '30',
          min: 5,
          max: 120,
          required: false,
          fillBack: false,
        },
      ],
    },
  ]);

  const MOCK_NODE_DETAIL = {
    task_id: 943095,
    node_id: 'ne56746104da3a758d43386fc5786064',
    basic_info: {
      auto_retry: { enable: false, interval: 0, times: 1 },
      error_ignorable: false,
      node_name: 'qwen3-8b',
      optional: true,
      retryable: true,
      skippable: true,
      stage_name: '',
      template_name: 'weilun-test1',
      timeout_config: { action: 'forced_fail', enable: false, seconds: 10 },
    },
    inputs: {
      _loop: 1,
      _inner_loop: 1,
      uniform_api_plugin_url: 'https://your-api-gateway.example.com/openapi/aidev/gateway/llm/v1/chat/completions',
      uniform_api_plugin_method: 'POST',
      uniform_api_plugin_credential_key: 'agent_credential',
      model: 'qwen3-8b',
      messages: [
        { role: 'system', content: '' },
        { role: 'user', content: '你是谁' },
      ],
      stream: false,
    },
    outputs: [
      { key: '_result', preset: false, value: true },
      { key: '_loop', preset: false, value: 1 },
      { key: '_inner_loop', preset: false, value: 1 },
      { key: 'status_code', preset: false, value: 200 },
      {
        key: 'data',
        preset: false,
        value: {
          id: 'chatcmpl-CNfyEERECMKKwfYi3xWs8a',
          object: 'chat.completion',
          model: 'qwen3-8b',
          choices: [{ index: 0, message: { role: 'assistant', content: '我是通义千问...' }, finish_reason: 'stop' }],
          usage: { prompt_tokens: 15, total_tokens: 297, completion_tokens: 282 },
        },
      },
    ],
    plugin_output: [
      {
        key: 'data',
        name: '响应内容',
        schema: { description: 'HTTP 请求响应内容，内部结构不固定', enum: [], properties: {}, type: 'object' },
        type: 'object',
      },
      {
        key: 'status_code',
        name: '状态码',
        schema: { description: 'HTTP 请求响应状态码', enum: [], type: 'int' },
        type: 'int',
      },
      {
        key: '_result',
        name: '执行结果',
        schema: { description: '执行结果的布尔值，True or False', enum: [], type: 'boolean' },
        type: 'boolean',
      },
      {
        key: '_loop',
        name: '循环次数',
        schema: { description: '循环执行次数', enum: [], type: 'int' },
        type: 'int',
      },
      {
        key: '_inner_loop',
        name: '当前流程循环次数',
        schema: { description: '在当前流程节点循环执行次数', enum: [], type: 'int' },
        type: 'int',
      },
    ],
  };

  const handleCustomTabChange = async () => {
    await new Promise(resolve => setTimeout(resolve, 3500));
    return MOCK_NODE_DETAIL;
  };

  /**
   * ChatContainer `getSideRenderComponent` 与侧栏 `<component :is="...">` 配合使用：
   * - 返回 `undefined`：使用 `addCustomTab` 时 `data.component`（如 FlowAgent 里的 BkFlowNodeDetail）。
   * - 返回 VNode：用 `createElement`（即 `h`）挂自定义根，例如 `createElement(CustomTabContent, props)`；
   *   `props` 与 `tab.data.props` 一致（含 node_name、task_id、loading、data 等）。
   * 将下方开关改为 `true` 时侧栏使用 `./custom-tab-content.vue` 覆盖默认的 BkFlowNodeDetail。
   */
  // const PLAYGROUND_GET_SIDE_VNODE_DEMO = true;

  // const getSideRenderComponent = (createElement: typeof h, props?: Record<string, unknown>) => {
  //   // if (!PLAYGROUND_GET_SIDE_VNODE_DEMO) {
  //   //   return undefined;
  //   // }
  //   const raw = props ?? {};
  //   const taskIdRaw = raw.task_id;
  //   const taskId =
  //     typeof taskIdRaw === 'number'
  //       ? taskIdRaw
  //       : typeof taskIdRaw === 'string' && taskIdRaw !== ''
  //         ? Number(taskIdRaw)
  //         : undefined;
  //   return createElement(CustomTabContent, {
  //     loading: Boolean(raw.loading),
  //     nodeId: typeof raw.node_id === 'string' ? raw.node_id : '',
  //     nodeName: typeof raw.node_name === 'string' ? raw.node_name : '',
  //     taskId: Number.isFinite(taskId as number) ? (taskId as number) : undefined,
  //     taskName: typeof raw.task_name === 'string' ? raw.task_name : '',
  //     data:
  //       typeof raw.data === 'object' && raw.data !== null && !Array.isArray(raw.data)
  //         ? (raw.data as Record<string, unknown>)
  //         : {},
  //   });
  // };

  // const getSideTabRenderComponent = (createElement: typeof h, tab: CustomTab<Record<string, unknown>>) => {
  //   if (tab.name === '634859') {
  //     return createElement('div', {}, 'dddd');
  //   }
  //   return undefined;
  // };

  // ── 自定义 AI 消息工具栏 mock ────────────────────────────────
  // 合并语义：以内置工具为基底，按 id 覆盖同名项、追加新项，其余保留
  // 主工具组：新增「保存」按钮（自定义图标），并覆盖内置 copy 的 tooltip 文案；cite/rebuild/share 保留
  const customMessageTools: IToolBtn[] = [
    // triggerSelection: 点击后复用 share 的多选态，确认走 confirmShare
    { id: 'save', name: '保存', description: '保存该回答', icon: DownloadIcon, triggerSelection: true },
    { id: 'copy', description: '复制全文（自定义文案）' },
    // hidden 标记可移除内置按钮：这里隐藏「分享」
    { id: 'share', hidden: true },
  ];
  // 反馈工具组：在内置 like/unlike/delete 基础上追加「收藏」按钮
  const customUpdateTools: IToolBtn[] = [
    { id: 'collect', name: '收藏', description: '收藏到我的空间', icon: EditIcon },
  ];

  const handleAgentAction = async (tool: IToolBtn) => {
    console.log('agent action:', tool);
    await new Promise(resolve => setTimeout(resolve, 2000));
    if (tool.id === 'save') {
      console.log('保存该回答');
      return;
    }
    if (tool.id === 'collect') {
      console.log('收藏到我的空间');
      return;
    }
    if (tool.id === 'like' || tool.id === 'unlike') {
      return tool.id === 'like'
        ? ['MCP/工具调用准确', '文档召回准确', '知识匹配精准', '响应迅速及时']
        : ['MCP/工具调用不准确', '文档召回不准确', '知识匹配不精准', '响应不够及时'];
    }
  };

  const handleSendMessage = async (message: UserMessage['content'], docSchema: TagSchema) => {
    console.log('send message:', message, 'docSchema:', docSchema);
    userInput.value = [[]];
    messages.value.push({
      id: `user_${Date.now()}`,
      role: MessageRole.User,
      content: message,
      messageId: `user_${Date.now()}`,
      status: MessageStatus.Complete,
    } as UserMessage);
    await new Promise(resolve => setTimeout(resolve, 5000));
  };

  const handleStopSending = async () => {
    console.log('stop sending');
  };

  // 多选态确认：source 为来源按钮对象，据此区分 share / save 等场景
  const handleConfirmShare = (selectedMessages: Message[], source?: IToolBtn) => {
    console.log('confirm selection, source:', source, 'selected messages:', selectedMessages);
    if (source?.id === 'save') {
      console.log('保存选中的消息');
    }
  };

  const handleUpload = async (file: File) => {
    const response = await uploadFileToSession({
      file,
      sessionCode: 'demo_session',
      accessToken: import.meta.env.VITE_ACCESS_TOKEN || '',
    });
    console.log('upload response:', response);
    return response?.data as { download_url?: string };
  };

  const handleUserInputConfirm = async (message: Message, content: UserMessage['content'], docSchema: TagSchema) => {
    console.log('user input confirm:', message, content, docSchema);
  };

  const handleUserShortcutConfirm = async (message: Message, formModel: Record<string, unknown>) => {
    console.log('user shortcut confirm:', message, formModel);
  };

  const handleSelectShortcut = (shortcut: Shortcut) => {
    console.log('select shortcut:', shortcut);
    selectedShortcut.value = { ...shortcut };
  };

  const handleDeleteShortcut = () => {
    selectedShortcut.value = null;
    userInput.value = '';
  };

  const handleShortcutClose = () => {
    selectedShortcut.value = null;
    userInput.value = '';
  };

  const handleShortcutSubmit = (formModel: Record<string, unknown>) => {
    console.log('shortcut submit:', formModel);
    selectedShortcut.value = null;
    userInput.value = '';
  };

  const handleStopStreaming = () => {
    console.log('stop streaming');
  };

  const handleCodeInsert = (language: string) => {
    console.log('insert code, language:', language);
  };

  const handleCodeApply = (language: string) => {
    console.log('apply code, language:', language);
  };

  const handleUpdateInputValue = (value: string | TagSchema, selectedResourceList: IAiSlashMenuItem[]) => {
    console.log('update input value:', value, 'resources:', selectedResourceList);
    userInput.value = value;
  };

  const handleDeleteMessage = () => {
    console.log('delete message');
    messages.value = [];
  };
</script>

<style lang="scss">
  .button-container {
    position: fixed;
    top: 10px;
    left: 10px;
  }

  .chat-bot-new {
    display: flex;
    width: 1200px;

    // min-width: 400px;
    height: 90vh;
    background: #fff;
    border-radius: 2px;
    box-shadow: 0 2px 12px 0 #0003;

    .code-header-action {
      padding: 2px 8px;
      font-size: 12px;
      color: #979ba5;
      cursor: pointer;
      border-radius: 2px;

      &:hover {
        color: #3a84ff;
        background: #3a84ff1a;
      }
    }
  }
</style>
