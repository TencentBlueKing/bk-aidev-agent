<template>
  <li
    ref="messageMainRef"
    :class="[message.role, 'message-main']"
  >
    <div
      v-if="message?.property?.extra?.cite"
      class="ai-cite-container"
    >
      <AiCite :text="message.property.extra.cite" />
    </div>
    <div :class="`message-content-container ${message.role}`">
      <template v-if="[SessionContentRole.User, SessionContentRole.System].includes(message.role)">
        <BkTextEditor
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
            class="markdown-message"
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
            v-html="renderValue"
            :class="{
              'markdown-message': true,
              loading: message.status === SessionContentStatus.Loading,
            }"
          ></span>
        </p>
      </template>
      <div
        v-if="!isEdit && message.status !== SessionContentStatus.Loading"
        class="message-tool"
      >
        <i
          class="bkai-icon bkai-fuzhi"
          @click="handleCopy"
        />
        <i
          class="bkai-icon bkai-yinyong"
          @click="setCiteText(message.content)"
        />
        <i
          v-if="message.role === SessionContentRole.Ai"
          class="bkai-icon bkai-zhongxinshengcheng"
          @click="handleRegenerate"
        />
        <template v-if="message.role === SessionContentRole.User">
          <i
            class="bkai-icon bkai-bianji"
            @click="isEdit = true"
          />
        </template>
        <i
          class="bkai-icon bkai-shanchu"
          @click="handleDelete"
        />
      </div>
    </div>
  </li>
</template>

<script lang="ts" setup>
  import { computed, onMounted, ref, watch, defineEmits, onBeforeUnmount } from 'vue';

  import { SessionContentRole, type ISessionContent, SessionContentStatus } from '@blueking/ai-ui-sdk';
  import { Message } from 'bkui-vue';
  import mermaidPlugin from "@agoose77/markdown-it-mermaid";
  import dayjs from 'dayjs';
  import hljs from 'highlight.js';
  import MarkdownIt from 'markdown-it';
  import MarkdownItCodeCopy from 'markdown-it-code-copy';

  import defaultUserLogo from '../assets/images/ai-user.png';
  import AiCite from '../components/ai-cite.vue';
  import { usePopup } from '../composables/use-popup-props';
  import { useSelect } from '../composables/use-select-pop';
  import { useTooltip } from '../composables/use-tippy';
  import { t } from '../lang';
  import MarkdownItLinkBlank from '../plugins/markdown-it-link-blank';
  import { createDeleteConfirm, closeAllDeleteConfirms } from '../utils/delete-confirm';
  import BkTextEditor from './text-editor.vue';

  // 类型定义
  interface Props {
    message: ISessionContent;
    userPhoto?: string;
    showTime?: boolean;
    index: number;
  }

  const emit = defineEmits<{
    regenerate: [index: number];
    resend: [index: number, value: { message: string; cite: string }];
    delete: [index: number];
  }>();

  // Props 定义
  const props = withDefaults(defineProps<Props>(), {
    userPhoto: defaultUserLogo,
    showTime: false,
  });

  // 状态管理
  const isEdit = ref(false);
  const messageMainRef = ref<HTMLElement | null>(null);
  // 组合式函数
  const { enablePopup } = usePopup();
  const { setCiteText } = useSelect(enablePopup);
  const { createTooltipsForSelector, destroyAll } = useTooltip({
    placement: 'top',
    arrow: true,
    appendTo: 'parent',
    delay: [0, 0],
  });

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
    .use(MarkdownItCodeCopy, {
      iconClass: 'bkai-icon bkai-fuzhi',
      buttonClass: 'ai-blueking-copy-button',
    })
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
    const dom = md.render(props.message.content);
    return dom.replace(/\s*<\/p>\s*$/, '</p>');
  });

  const timeMessage = computed(() => {
    if (!props.message.time) return '';

    const time = dayjs(props.message.time);
    const now = dayjs();
    return now.isSame(time, 'year') ? time.format('MM-DD HH:mm:ss') : time.format('YYYY-MM-DD HH:mm:ss');
  });

  // 事件处理
  const handleEditMessage = (value: string) => {
    isEdit.value = false;
    emit('resend', props.index, { message: value, cite: props.message.cite || '' });
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(props.message.content);
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

  // 工具提示初始化
  const initTooltips = () => {
    destroyAll();
    createTooltipsForSelector('.message-tool .bkai-fuzhi', t('复制'));
    createTooltipsForSelector('.message-tool .bkai-zhongxinshengcheng', t('重新生成'));
    createTooltipsForSelector('.message-tool .bkai-yinyong', t('引用'));
    createTooltipsForSelector('.message-tool .bkai-bianji', t('编辑'));
    createTooltipsForSelector('.message-tool .bkai-shanchu', t('删除'));
  };

  // 生命周期钩子
  onMounted(() => {
    setTimeout(initTooltips, 0);
  });

  // 监听器
  watch(
    () => props.message,
    () => {
      setTimeout(initTooltips, 0);
    },
    { deep: true },
  );

  watch(isEdit, newValue => {
    if (!newValue) {
      setTimeout(initTooltips, 0);
    }
  });

  onBeforeUnmount(() => {
    closeAllDeleteConfirms();
  });
</script>

<style lang="scss">
  /* stylelint-disable declaration-no-important */
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
      float: right;
    }

    &:after {
      display: table;
      clear: both;
      content: '';
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
        gap: 10px;
        align-items: center;
        color: #979ba5;
        opacity: 0;

        i {
          margin-right: 0;
          font-size: 16px;
          cursor: pointer;
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
    padding: 10px 12px;
    margin: 0;
    font-size: 14px;
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
      font-size: 14px;
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

    .markdown-message {
      width: 100%;
      height: 100%;
      font-size: 14px;
      color: #313238;

      h1,
      h2,
      h3,
      h4,
      h5 {
        height: auto;
        margin: 10px 0;
        font-family: -apple-system, 'PingFang SC', 'Helvetica Neue', Helvetica, Arial, 'Lantinghei SC',
          'Hiragino Sans GB', 'Microsoft Yahei', sans-serif;
        font-size: 14px;
        font-weight: bold;
        line-height: 1.5;
        color: #34383e;
      }

      h1 {
        font-size: 28px;
      }

      h2 {
        font-size: 20px;
      }

      h3 {
        font-size: 16px;
      }

      h4 {
        font-size: 14px;
      }

      h5 {
        font-size: 14px;
      }

      em {
        font-style: italic;
      }

      div,
      p,
      font,
      span,
      li {
        line-height: 1.5;
      }

      p {
        margin: 0;
      }

      table,
      table p {
        margin: 0;
      }

      table {
        width: 100%;
        max-width: 100%;
        margin-top: 10px;
        margin-bottom: 10px;
        border-spacing: 0;
        border-collapse: collapse;

        th {
          padding: 8px;
          font-weight: bold;
          text-align: left;
          background-color: #f5f7fa;
          border-bottom: 2px solid #e8e8e8;
        }

        td {
          padding: 8px;
          vertical-align: top;
          border-top: 1px solid #e8e8e8;
          border-bottom: 1px solid #e8e8e8;
        }

        tr:nth-child(even) {
          background-color: #fafbfd;
        }

        thead {
          background-color: #f5f7fa;
        }
      }

      ul,
      ol {
        padding-left: 40px;
        margin: 10px 0 10px;
        text-indent: 0;
      }

      ul {
        list-style: disc;

        & > li {
          line-height: 1.8;
          white-space: normal;
          list-style: disc;
        }
      }

      ol {
        list-style: decimal;

        & > li {
          line-height: 1.8;
          white-space: normal;
          list-style: decimal;
        }
      }

      li > ul {
        margin-bottom: 10px;
      }

      li ol {
        padding-left: 20px !important;
      }

      ul ul,
      ul ol,
      ol ol,
      ol ul {
        margin-bottom: 0;
        margin-left: 20px;
      }

      pre,
      code {
        padding: 0 3px 2px;
        font-family: Monaco, Menlo, Consolas, 'Courier New', monospace;
        font-size: 14px;
        border-radius: 3px;
      }

      code {
        padding: 2px 4px;
        color: #24292e;
        background-color: rgba(27, 31, 35, 0.05);
      }

      a {
        color: #3a84ff;
        text-decoration: none;
        cursor: pointer;
      }

      img {
        width: 100%;
      }

      pre {
        display: block;
        padding: 9.5px;
        margin: 0 0 10px;
        font-family: Consolas, monospace, tahoma, Arial;
        font-size: 13px;
        word-break: break-all;
        word-wrap: break-word;
        white-space: pre-wrap;
        background-color: #333;
        border-radius: 2px;

        code {
          padding: 0;
          color: #fff;
          white-space: pre-wrap;
          background-color: transparent;
          border: 0;
        }
      }

      blockquote {
        padding: 0 0 0 12px;
        margin: 0 0 20px;
        border-left: 5px solid #dfdfdf;

        ::before,
        ::after {
          content: '';
        }

        p {
          margin-bottom: 0;
          font-size: 14px;
          font-weight: 300;
          line-height: 25px;
        }

        small {
          display: block;
          line-height: 20px;
          color: #999;

          ::before {
            content: '\2014 \00A0';
          }
        }
      }
    }

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
