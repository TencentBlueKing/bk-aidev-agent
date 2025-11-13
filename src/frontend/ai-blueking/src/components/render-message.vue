<template>
  <li
    v-if="!HIDE_ROLE_LIST.includes(message.role)"
    ref="messageMainRef"
    :class="[message.role, 'message-main']"
  >
    <div class="message-wrapper">
      <!-- 选择模式下的checkbox -->
      <div
        v-if="isSelectMode"
        class="message-checkbox"
      >
        <bk-checkbox
          :model-value="message.id ? isMessageSelected(message.id.toString()) : false"
          @change="handleMessageSelect"
        />
      </div>

      <div class="message-content-wrapper">
        <div
          v-if="message?.property?.extra?.cite"
          class="ai-cite-container"
        >
          <ai-cite
            v-if="!isStructuredCite(message.property.extra.cite)"
            :text="cleanedCiteText"
          />
        </div>
        <div :class="`message-content-container ${message.role}`">
          <ai-cite-structured
            v-if="isStructuredCite(message?.property?.extra?.cite)"
            :cite-data="message?.property?.extra?.cite"
          />
          <template
            v-else-if="[SessionContentRole.User, SessionContentRole.Role].includes(message.role)"
          >
            <bk-text-editor
              v-if="isEdit"
              :auto-focus="true"
              :model-value="message.content"
              @cancel="isEdit = false"
              @submit="handleEditMessage"
            />
            <p
              v-else
              class="message-content user"
            >
              <span
                v-if="timeMessage && props.showTime"
                class="time-message user"
              >
                {{ timeMessage }}
              </span>
              <span
                class="markdown-content"
                v-html="renderValue"
              ></span>
            </p>
          </template>
          <template v-else>
            <p class="message-content ai">
              <span
                v-if="timeMessage && props.showTime"
                class="time-message ai"
              >
                {{ timeMessage }}
              </span>
              <i
                v-if="statusIcon"
                :class="statusIcon"
              ></i>
              <svg
                v-if="message.status === SessionContentStatus.Loading"
                width="14"
                height="14"
                class="loading-message"
                aria-hidden="true"
              >
                <use xlink:href="#bkai-quanquan"></use>
              </svg>
              <span
                v-if="message.status === SessionContentStatus.Fail"
                class="message-wrap"
              >
                {{ message.content }}
              </span>
              <span
                v-else
                :class="{
                  'markdown-content': true,
                  loading: message.status === SessionContentStatus.Loading,
                }"
                v-html="renderValue"
              ></span>
            </p>
          </template>
          <div
            v-if="!isEdit && message.status !== SessionContentStatus.Loading"
            class="message-tool"
          >
            <i
              class="bkai-icon bkai-fuzhi tool-icon"
              @click="handleCopy"
            />
            <template v-if="!readonly">
              <i
                class="bkai-icon bkai-yinyong tool-icon"
                @click="handleCite"
              />
              <i
                v-if="message.role === SessionContentRole.Ai"
                class="bkai-icon bkai-zhongxinshengcheng tool-icon"
                @click="handleRegenerate"
              />
              <template v-if="message.role === SessionContentRole.User">
                <i
                  class="bkai-icon bkai-bianji tool-icon"
                  @click="isEdit = true"
                />
              </template>
              <i
                class="bkai-icon bkai-shanchu tool-icon"
                @click="handleDelete"
              />
              <template v-if="message.role === SessionContentRole.Ai && lastMessageId">
                <i class="split-line" />
                <render-like
                  :api-prefix="apiPrefix"
                  :session-code="message.sessionCode"
                  :session-content-ids="[lastMessageId || 0, message.id || 0]"
                  :space-id="message.spaceId || ''"
                  :rate="message.rate || 0"
                  :popover-options="{
                    zIndex: 999999,
                  }"
                  :tooltip-options="{
                    boundary: 'parent',
                  }"
                  @update-session-content-list="handleUpdateSessionContentList"
                />
                <i
                  class="bkai-icon bkai-fenxiang tool-icon"
                  @click="handleShare"
                />
              </template>
            </template>
          </div>
        </div>
      </div>
    </div>
  </li>
</template>

<script lang="ts" setup>
  import { SessionContentRole, SessionContentStatus } from '@blueking/ai-ui-sdk/enums';
  import { type ISessionContent, type ISessionFeedback } from '@blueking/ai-ui-sdk/types';
  import { Message, Checkbox as BkCheckbox } from 'bkui-vue';
  import dayjs from 'dayjs';
  import DOMPurify from 'dompurify';
  import hljs from 'highlight.js';
  import MarkdownIt from 'markdown-it';
  import MarkdownItCodeCopy from 'markdown-it-copy-code';
  import {
    computed,
    onMounted,
    ref,
    watch,
    defineEmits,
    onBeforeUnmount,
    nextTick,
    inject,
    type ComputedRef,
  } from 'vue';
  import 'markdown-it-copy-code/styles/base.css';
  import 'markdown-it-copy-code/styles/small.css';

  import defaultUserLogo from '../assets/images/ai-user.png';
  import AiCiteStructured from '../components/ai-cite-structured.vue';
  import AiCite from '../components/ai-cite.vue';
  import { useMermaid } from '../composables/use-mermaid';
  import { usePopup } from '../composables/use-popup-props';
  import { useSelect } from '../composables/use-select-pop';
  import { useTooltip } from '../composables/use-tippy';
  import { useInjectSessionStore } from '../composables/use-session-store';
  import type { SessionStore } from '../store/sessionStore';
  import { HIDE_ROLE_LIST } from '../config';
  import { t } from '../lang';
  import MarkdownItLinkBlank from '../plugins/markdown-it-link-blank';
  import mermaidPlugin from '../plugins/markdown-it-mermaid';
  import { createDeleteConfirm, closeAllDeleteConfirms } from '../utils/delete-confirm';
  import { RenderLike } from '@blueking/ai-ui-sdk/components';
  import { removeThinkingSections } from '../utils';

  import BkTextEditor from './text-editor.vue';

  // 类型定义
  interface Props {
    message: ISessionContent;
    userPhoto?: string;
    showTime?: boolean;
    index: number;
    isSelectMode?: boolean;
    lastMessageId?: number;
    isMessageSelected?: (messageId: string) => boolean;
    readonly?: boolean;
  }

  interface CitedData {
    key: string;
    value: string;
  }

  // 类型定义 - 与 ai-cite-structured.vue 中保持一致
  interface StructuredCite {
    type: 'structured';
    title: string;
    data: CitedData[];
    content?: string | object;
    [key: string]: any;
  }

  const emit = defineEmits<{
    regenerate: [index: number];
    resend: [index: number, value: { message: string }];
    delete: [index: number];
    'message-select': [messageId: string];
    'update-session-content': [
      data: { messageId: number | undefined; updates: Partial<ISessionContent> },
    ];
  }>();

  // Props 定义
  const props = withDefaults(defineProps<Props>(), {
    userPhoto: defaultUserLogo,
    showTime: false,
    isSelectMode: false,
    isMessageSelected: () => false,
    readonly: false,
  });

  // 注入会话 store
  const sessionStore = useInjectSessionStore() as SessionStore;

  // 注入动态 URL
  const normalizedUrl = inject<ComputedRef<string>>('normalizedUrl');

  // 将 normalizedUrl 赋值给 apiPrefix
  const apiPrefix = computed(() => normalizedUrl?.value || '');

  // 状态管理
  const isEdit = ref(false);
  const messageMainRef = ref<HTMLElement | null>(null);

  // 检查是否为结构化cite
  const isStructuredCite = (cite: unknown): cite is StructuredCite => {
    return (
      typeof cite === 'object' &&
      cite !== null &&
      'type' in cite &&
      (cite as { type: string }).type === 'structured'
    );
  };

  /**
   * 获取清理后的 cite 文本
   */
  const cleanedCiteText = computed(() => {
    const cite = props.message?.property?.extra?.cite;
    if (!cite || isStructuredCite(cite)) return '';
    return removeThinkingSections(cite);
  });
  // 组合式函数
  const { enablePopup } = usePopup();
  const { setCiteText } = useSelect(enablePopup);
  const { createTooltipsForSelector, destroyAll } = useTooltip({
    placement: 'top',
    arrow: true,
    appendTo: 'parent',
    delay: [0, 0],
  });
  const { initMermaid, processMermaidDiagrams, cleanupMermaidElements } = useMermaid();

  // Markdown 实例
  const md = new MarkdownIt({
    html: true,
    highlight: (str: string, lang: string) => {
      if (lang && hljs.getLanguage(lang)) {
        try {
          return hljs.highlight(str, { language: lang }).value;
        } catch (__) {}
      }
      return '';
    },
  })
    .use(MarkdownItCodeCopy)
    .use(MarkdownItLinkBlank)
    .use(mermaidPlugin);
  // 计算属性
  const statusIcon = computed(() => {
    const iconMap: Record<SessionContentStatus, string> = {
      [SessionContentStatus.Fail]: 'bkai-icon bkai-warning-circle-fill',
      [SessionContentStatus.Loading]: '',
      [SessionContentStatus.Success]: '',
    };
    return props.message?.status ? iconMap[props.message.status] : '';
  });

  const renderValue = computed(() => {
    if (!props.message.content) return '';

    const rendered = md.render(props.message.content);

    // 使用 DOMPurify 净化内容以防止 XSS
    const sanitized = DOMPurify.sanitize(rendered, {
      USE_PROFILES: { html: true, svg: true },
      ADD_TAGS: ['svg', 'g', 'path'],
      ADD_ATTR: [
        'target',
        'xmlns',
        'width',
        'height',
        'viewBox',
        'fill',
        'stroke-linecap',
        'stroke-linejoin',
        'stroke-width',
      ],
      FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input'],
      FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover'],
    });

    // Process mermaid diagrams after DOM update
    nextTick(() => {
      if (messageMainRef.value) {
        processMermaidDiagrams(messageMainRef.value, () => {
          // 在 mermaid 渲染完成后，触发父组件的滚动更新
          // 通过自定义事件通知父组件需要重新滚动
          const event = new CustomEvent('mermaid-rendered', { bubbles: true });
          messageMainRef.value?.dispatchEvent(event);
        });
      }
    });

    return sanitized.replace(/\s*<\/p>\s*$/, '</p>');
  });

  const timeMessage = computed(() => {
    if (!props.message.time) return '';

    const time = dayjs(props.message.time);
    const now = dayjs();
    return now.isSame(time, 'year')
      ? time.format('MM-DD HH:mm:ss')
      : time.format('YYYY-MM-DD HH:mm:ss');
  });

  // 事件处理
  const handleEditMessage = (value: string) => {
    isEdit.value = false;
    emit('resend', props.index, { message: value });
  };

  /**
   * 将结构化数据转换为可读字符串
   * @param cite 结构化引用数据
   * @returns 格式化后的字符串
   */
  const formatStructuredCiteToString = (cite: StructuredCite): string => {
    // 优先使用 content 字段
    if (cite.content) {
      return typeof cite.content === 'string'
        ? cite.content
        : JSON.stringify(cite.content, null, 2);
    }

    // 其次尝试从 data 构建格式化字符串
    if (cite.data && cite.data.length > 0) {
      return `${cite.title}\n${cite.data.map(item => `${item.key}: ${item.value}`).join('\n')}`;
    }

    // 如果没有特定格式，直接转换整个对象
    return JSON.stringify(cite, null, 2);
  };

  /**
   * 获取消息的文本内容，处理结构化数据
   */
  const getMessageTextContent = (): string => {
    const cite = props.message?.property?.extra?.cite;
    if (cite) {
      if (isStructuredCite(cite)) {
        return formatStructuredCiteToString(cite);
      }
      // 如果是普通 cite 文本，返回清理后的文本
      return cleanedCiteText.value;
    }
    // 当 cite 不存在时，需要清理 content 中的思考标签
    return removeThinkingSections(props.message.content);
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(getMessageTextContent());
      Message({
        theme: 'success',
        message: t('复制成功'),
      });
    } catch (err) {
      console.error('复制失败:', err);
      Message({
        theme: 'error',
        message: t('复制失败'),
      });
    }
  };

  const handleCite = () => {
    setCiteText(getMessageTextContent());
  };

  const handleRegenerate = () => {
    emit('regenerate', props.index);
  };

  const handleDelete = (event: MouseEvent) => {
    const target = event.currentTarget as HTMLElement;

    createDeleteConfirm(target, {
      onConfirm: () => {
        emit('delete', props.index);
      },
      onCancel: () => {},
      placement: 'top',
      appendTo: messageMainRef.value as Element,
    });
  };

  const handleUpdateSessionContentList = (feedBack: ISessionFeedback) => {
    // Emit an event to update the session content in the parent component
    // This will allow the parent to update the sessionContents ref properly
    emit('update-session-content', {
      messageId: props.message.id,
      updates: {
        rate: feedBack.rate ?? props.message.rate,
        comment: feedBack.comment ?? props.message.comment,
        labels: feedBack.labels ?? props.message.labels,
      },
    });
  };

  const handleShare = () => {
    const event = new CustomEvent('enter-select-mode', {
      detail: { type: 'share' as const },
    });
    window.dispatchEvent(event);
  };

  /**
   * 处理消息选择事件
   */
  const handleMessageSelect = (_value: boolean) => {
    if (props.message.id !== undefined) {
      emit('message-select', props.message.id.toString());
    }
  };

  // 工具提示初始化
  const initTooltips = () => {
    destroyAll();
    createTooltipsForSelector('.message-tool .bkai-fuzhi', t('复制'));
    createTooltipsForSelector('.message-tool .bkai-zhongxinshengcheng', t('重新生成'));
    createTooltipsForSelector('.message-tool .bkai-yinyong', t('引用'));
    createTooltipsForSelector('.message-tool .bkai-bianji', t('编辑'));
    createTooltipsForSelector('.message-tool .bkai-shanchu', t('删除'));
    createTooltipsForSelector('.message-tool .bkai-fenxiang', t('分享'));
  };

  // 生命周期钩子
  onMounted(() => {
    initMermaid();
    setTimeout(initTooltips, 0);
  });

  // 监听器
  watch(
    () => props.message,
    () => {
      setTimeout(initTooltips, 0);
    },
    { deep: true }
  );

  watch(isEdit, newValue => {
    if (!newValue) {
      setTimeout(initTooltips, 0);
    }
  });

  onBeforeUnmount(() => {
    closeAllDeleteConfirms();
    cleanupMermaidElements();
  });
</script>

<style lang="scss">
  /* stylelint-disable declaration-no-important */
  @use '../styles/markdown.scss';

  @keyframes bkai-loading {
    to {
      transform: rotate(1turn);
    }
  }

  .ai-cite-container {
    max-width: 100%;
    margin-bottom: 2px;
  }

  .ai-clickable {
    cursor: pointer;
  }

  button.ai-clickable {
    color: #fff;
    text-decoration: none;
    background-color: #3a84ff;
    border: 1px solid #3a84ff;
    border-radius: 2px;
    outline: none;

    &:active {
      color: #fff;
      background-color: #2c77f4;
      border-color: #2c77f4;
    }
  }

  .bkai-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    margin-right: 5px;
    font-size: 18px;

    &:hover {
      color: #4d4f56;
    }

    &.bkai-warning-circle-fill {
      font-size: 16px;
      line-height: 22px;
      color: #ea3636;
    }
  }

  .message-main {
    display: flex;
    flex-direction: column;
    align-items: flex-start;

    &.user,
    &.cite {
      justify-content: flex-end;
      align-items: flex-end;
    }

    &:after {
      display: table;
      clear: both;
      content: '';
    }

    .message-wrapper {
      display: flex;
      width: 100%;

      .message-checkbox {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 32px;
      }

      .message-content-wrapper {
        flex: 1;
        width: 0;
      }
    }

    .message-content-container {
      position: relative;
      display: flex;
      flex-direction: column;
      width: 100%;

      &.user {
        align-items: flex-end;
      }

      &.ai {
        align-items: flex-start;
      }

      .message-tool {
        position: absolute;
        bottom: -24px;
        display: flex;
        gap: 8px;
        align-items: center;
        color: #979ba5;
        opacity: 0;

        .tool-icon {
          margin-right: 0;
          font-size: 14px;
          cursor: pointer;
        }

        .split-line {
          width: 1px;
          height: 12px;
          background: #dcdee5;
          margin: 0 5px;
        }

        .select-options .ai-ui-sdk-icon {
          margin-right: 0;
        }

        .select-options .ai-blueking-popper {
          padding: 5px 9px;
        }

        .bkai-icon {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 20px;
          height: 20px;
          border-radius: 4px;

          &:hover {
            color: #4d4f56;
            background: #eaebf0;
          }
        }
      }

      &:hover .message-tool {
        opacity: 1;
      }
    }
  }

  .message-content {
    position: relative;
    display: flex;
    align-items: center;
    padding: 8px 12px;
    margin: 0;
    font-size: 12px;
    line-height: 1.5;
    color: #313238;
    word-break: break-all;
    white-space: pre-wrap;
    border-radius: 4px;

    .time-message {
      position: absolute;
      top: -16px;
      display: none;
      width: 150px;
      font-size: 12px;
      line-height: 12px;
      color: #979ba5;

      &.user {
        right: 0;
        text-align: right;
      }

      &.ai {
        left: 0;
      }
    }

    &:hover .time-message {
      display: block;
    }

    // markdown-content 样式现在从公共样式文件导入

    .message-wrap {
      display: inline-block;
      white-space: pre-wrap;
    }

    &.user {
      background: #e1ecff;
    }

    &.ai {
      align-items: flex-start;
      padding: 0;
      white-space: normal;
    }
  }

  .ai-blueking-copy-button {
    width: 16px;
    height: 16px;
    padding: 0;
    cursor: pointer;
    background: #333;
    border: none;
    outline: none;

    .bkai-fuzhi {
      margin: 0;
      font-size: 16px !important;
      line-height: 1 !important;
      color: #fff;
      opacity: 1 !important;

      &:hover {
        color: #4d4f56;
      }
    }
  }

  .loading-message {
    min-width: 14px;
    margin-top: 2px;
    margin-right: 5px;
    fill: #3a84ff;
    animation: bkai-loading 1s linear infinite;
  }

  code.hljs {
    padding: 3px 5px;
  }

  pre code.hljs {
    display: block;
    padding: 1em;
    overflow-x: auto;
  }

  .hljs {
    color: #abb2bf !important;
    background: #282c34 !important;
  }

  .hljs-comment,
  .hljs-quote {
    font-style: italic !important;
    color: #5c6370 !important;
  }

  .hljs-doctag,
  .hljs-keyword,
  .hljs-formula {
    color: #c678dd !important;
  }

  .hljs-section,
  .hljs-name,
  .hljs-selector-tag,
  .hljs-deletion,
  .hljs-subst {
    color: #e06c75 !important;
  }

  .hljs-literal {
    color: #56b6c2 !important;
  }

  .hljs-string,
  .hljs-regexp,
  .hljs-addition,
  .hljs-attribute,
  .hljs-meta .hljs-string {
    color: #98c379 !important;
  }

  .hljs-attr,
  .hljs-variable,
  .hljs-template-variable,
  .hljs-type,
  .hljs-selector-class,
  .hljs-selector-attr,
  .hljs-selector-pseudo,
  .hljs-number {
    color: #d19a66 !important;
  }

  .hljs-symbol,
  .hljs-bullet,
  .hljs-link,
  .hljs-meta,
  .hljs-selector-id,
  .hljs-title {
    color: #61aeee !important;
  }

  .hljs-built_in,
  .hljs-title.class_,
  .hljs-class .hljs-title {
    color: #e6c07b !important;
  }

  .hljs-emphasis {
    font-style: italic !important;
  }

  .hljs-strong {
    font-weight: bold !important;
  }

  .hljs-link {
    text-decoration: underline !important;
  }
</style>
