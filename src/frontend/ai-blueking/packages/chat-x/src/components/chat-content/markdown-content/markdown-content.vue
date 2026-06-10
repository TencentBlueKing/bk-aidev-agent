<template>
  <div class="ai-markdown-content">
    <template v-if="status === MessageStatus.Error">
      <CommonErrorContent :content="content" />
    </template>
    <template v-else>
      <div
        class="ai-markdown-body"
        :data-theme="'light'"
      >
        <template
          v-for="(groupedToken, index) in groupedTokens"
          :key="index"
        >
          <template v-if="hasMermaidToken(groupedToken)">
            <MermaidContent
              :key="index"
              :token="groupedToken"
              @mounted="handleTokenMounted"
            />
          </template>
          <template v-else-if="hasLatexToken(groupedToken)">
            <LatexContent
              :key="index"
              :token="groupedToken"
              @mounted="handleTokenMounted"
            />
          </template>
          <template v-else-if="hasCodeToken(groupedToken)">
            <CodeContent
              :key="index"
              :token="groupedToken"
              @mounted="handleTokenMounted"
            >
              <template #header="{ language, token }">
                <slot
                  name="codeHeader"
                  v-bind="{ language, token }"
                />
              </template>
            </CodeContent>
          </template>
          <template v-else>
            <VNodeRenderer
              :key="index"
              :options="vnodeOptions"
              :tokens="groupedToken"
              @vue:mounted="handleTokenMounted"
            />
          </template>
        </template>
      </div>
    </template>
  </div>
</template>
<script setup lang="ts">
  import { type VNode, shallowRef, watch } from 'vue';

  import dompurify, { type Config as DOMPurifyConfig } from 'dompurify';
  import throttle from 'lodash/throttle';
  import markdownItFootnote from 'markdown-it-footnote';
  import markdownItIns from 'markdown-it-ins';
  import markdownItMark from 'markdown-it-mark';
  import markdownItSub from 'markdown-it-sub';
  import markdownItSup from 'markdown-it-sup';
  import markdownItTaskCheckbox from 'markdown-it-task-checkbox';

  import { MessageStatus } from '../../../ag-ui/types/constants';
  import { useContainerScrollConsumer } from '../../../composables';
  import MarkdownIt from '../../../markdown-it/index';
  import { markdownItBkInlineStyle, markdownItLatex, markdownItMermaid } from '../../../plugins';
  import { markdownItContainer } from '../../../plugins/markdown-container';
  // import { markdownAnimationAttrs } from '../../../plugins/markdown-animation-attrs';
  import { completeMarkdownSyntax } from '../../../utils/stream-markdown-completer';
  import { CodeContent, MermaidContent } from '../../markdown-token';
  import LatexContent from '../../markdown-token/latex-content/latex-content.vue';
  import CommonErrorContent from '../common-error-content/common-error-content.vue';
  import VNodeRenderer from '../vnode-renderer';

  import type { Token } from 'markdown-it/index.js';

  import './markdown-content.css';
  import 'katex/dist/katex.min.css';

  // DOMPurify 配置：允许 KaTeX 生成的标签和属性
  const domPurifyConfig: DOMPurifyConfig = {
    ADD_TAGS: ['semantics', 'mrow', 'mi', 'mo', 'mn', 'msup', 'msub', 'mfrac', 'mtext', 'annotation'],
    ADD_ATTR: ['xmlns', 'mathvariant', 'encoding', 'style'],
  };

  defineSlots<{
    codeHeader: (props: { language: string; token: Token[] }) => null | undefined | VNode;
  }>();

  const props = defineProps<{
    content?: string;
    status?: MessageStatus;
  }>();

  const containerScrollConsumer = useContainerScrollConsumer();

  const groupedTokens = shallowRef<Token[][]>([]);
  const md = new MarkdownIt()
    // .use(markdownAnimationAttrs)
    .use(markdownItBkInlineStyle)
    .use(markdownItFootnote)
    .use(markdownItIns)
    .use(markdownItMark)
    .use(markdownItSub)
    .use(markdownItSup)
    .use(markdownItTaskCheckbox)
    .use(markdownItMermaid)
    .use(markdownItLatex, {
      katexOptions: {
        strict: false,
      },
    })
    .use(markdownItContainer, /^hljs-(left|center|right)$/);
  const vnodeOptions = {
    html: true,
    mditOptions: md.options,
    renderer: md.renderer,
    sanitize: (html: string) => dompurify.sanitize(html, domPurifyConfig),
  };

  // 检查 token 组中是否包含 mermaid 代码块
  const hasMermaidToken = (tokens: Token[]): boolean => {
    return tokens.some(token => {
      if (token.type === 'fence') {
        const info = token.info ? token.info.trim() : '';
        return info === 'mermaid';
      }
      return false;
    });
  };

  // 检查 token 组中是否包含代码块（fence 或 code_block）
  // 注意：mermaid 代码块已在 hasMermaidToken 中处理，这里要排除
  const hasCodeToken = (tokens: Token[]): boolean => {
    return tokens.some(token => {
      if (token.type === 'fence') {
        const info = token.info ? token.info.trim() : '';
        // 排除 mermaid，它由专门的 MermaidContent 处理
        return info !== 'mermaid';
      }
      if (token.type === 'code_block') {
        return true;
      }
      return false;
    });
  };

  const hasLatexToken = (tokens: Token[]): boolean => {
    const checkToken = (token: Token): boolean => {
      if (token.type === 'math_inline' || token.type === 'math_block') {
        return true;
      }
      // 递归检查 children（用于 inline token）
      if (token.children && token.children.length > 0) {
        return token.children.some(checkToken);
      }
      return false;
    };
    return tokens.some(checkToken);
  };
  const groupTokens = (tokens: Token[]): Token[][] => {
    const result: Token[][] = [];
    // 栈中存储当前正在构建的独立 tag group（每个元素是一个 Token 数组，代表一个完整的 tag DOM）
    const stack: Token[][] = [];
    // 栈中存储每个 group 对应的 tag，用于匹配 open/close
    const tagStack: (null | string)[] = [];

    for (const token of tokens) {
      if (!token) {
        continue;
      }

      // 处理 open token (nesting === 1) - 开始一个新的独立 tag group
      if (token.nesting === 1) {
        const tag = token.tag || token.type.replace('_open', '');
        // 创建一个新的独立 group，包含这个 open token
        const newGroup: Token[] = [token];

        // 如果栈为空，说明这是顶层独立 tag，直接添加到结果中
        if (stack.length === 0) {
          result.push(newGroup);
        }
        // 如果栈不为空，说明这是嵌套在另一个 tag 内部的独立 tag
        // 新 group 已经创建，但暂时不添加到父 group，等它完整后再处理

        // 将新 group 压入栈，表示开始构建这个独立的 tag group
        stack.push(newGroup);
        tagStack.push(tag);
      }
      // 处理 close token (nesting === -1) - 完成当前的独立 tag group
      else if (token.nesting === -1) {
        if (stack.length === 0) {
          // 没有对应的 open，创建一个只包含 close token 的独立 group
          result.push([token]);
          continue;
        }

        const currentGroup = stack[stack.length - 1];
        const expectedTag = tagStack[tagStack.length - 1];
        const actualTag = token.tag || token.type.replace('_close', '');

        if (currentGroup && expectedTag === actualTag) {
          // tag 匹配，将 close token 添加到当前 group，完成这个独立的 tag group
          currentGroup.push(token);

          // 弹出已完成的独立 tag group
          const closedGroup = stack.pop();
          tagStack.pop();

          // 如果栈中还有父 group，说明这个已完成的 group 是嵌套在父 tag 内部的
          // 将完整的子 group 添加到父 group 中
          if (stack.length > 0 && closedGroup) {
            const parentGroup = stack[stack.length - 1];
            if (parentGroup) {
              // 将完整的子 group（包括 open 和 close token）添加到父 group
              parentGroup.push(...closedGroup);
            }
          }
          // 如果栈为空，说明这是顶层独立 tag group，已经在 result 中了，不需要额外处理
        } else if (currentGroup) {
          // tag 不匹配，仍然添加到当前 group（可能是嵌套结构问题）
          currentGroup.push(token);
        }
      }
      // 处理普通 token (nesting === 0) 或 inline token
      else {
        if (stack.length === 0) {
          // 没有正在构建的独立 tag group，创建一个只包含这个 token 的独立 group
          result.push([token]);
        } else {
          // 添加到当前正在构建的独立 tag group
          const currentGroup = stack[stack.length - 1];
          if (currentGroup) {
            currentGroup.push(token);
          }
        }
      }
    }

    // 处理未闭合的独立 tag group（理论上不应该发生，但为了健壮性）
    // 将栈中剩余的 groups 添加到结果中
    while (stack.length > 0) {
      const unclosedGroup = stack.pop();
      if (unclosedGroup && unclosedGroup.length > 0) {
        // 如果栈中还有父 group，添加到父 group；否则添加到 result
        if (stack.length > 0) {
          const parentGroup = stack[stack.length - 1];
          if (parentGroup) {
            parentGroup.push(...unclosedGroup);
          }
        } else {
          result.push(unclosedGroup);
        }
      }
      tagStack.pop();
    }

    return result;
  };
  /**
   * 节流的 Markdown 解析函数
   * 流式输入时每 5ms 最多解析一次，减少解析开销
   */
  const parseMarkdownContent = throttle(
    (content?: string) => {
      if (!content) {
        groupedTokens.value = [];
        return;
      }
      // 流式渲染时对不完整的 markdown 语法进行补全
      const { content: completedContent, isIncomplete } = completeMarkdownSyntax(content);
      // 如果内容处于不完整状态（正在输入 LaTeX 命令），
      // 保持之前的渲染结果，避免闪烁或显示无效内容
      if (isIncomplete && groupedTokens.value.length > 0) {
        return;
      }
      const tokens = md.parse(completedContent, {});

      const list = groupTokens(tokens);
      for (const group of list) {
        const firstToken = group.at(0);
        if (firstToken) {
          if (!firstToken.attrs) {
            firstToken.attrs = [];
          }
          firstToken.attrs.push(['class', 'ai-blueking-markdown-fade-in']);
        }
      }
      groupedTokens.value = list;
    },
    5,
    {
      leading: true,
      trailing: true,
    },
  );

  watch(() => props.content, parseMarkdownContent, {
    immediate: true,
  });
  /**
   * 处理 token 挂载后的滚动
   * 使用更长的节流间隔（800ms），且只在最后触发
   * 这样可以减少滚动过程中的性能开销，避免频繁的布局计算
   */
  const handleTokenMounted = throttle(
    () => {
      if (containerScrollConsumer?.value?.autoScrollEnabled !== false) {
        containerScrollConsumer?.value?.toScrollBottom?.();
      }
    },
    100,
    {
      leading: true,
      trailing: true,
    },
  );
</script>
<style lang="scss">
  /* stylelint-disable custom-property-pattern */

  .ai-markdown-content {
    width: 100%;
    height: 100%;

    // 使用 CSS contain 限制重排范围，提升流式渲染性能
    // layout: 元素的内部布局不影响外部
    // style: 某些属性的效果不会逃离元素
    contain: layout style;

    .ai-markdown-body {
      // 内容包含：限制布局、绘制和样式计算的范围
      contain: content;
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height, 20px);

      // light 主题作为默认值，优先级高于 github-markdown.css 的 @media 查询
      background-color: transparent;

      table {
        width: 100%;
      }

      pre code.hljs {
        background-color: #282c34;
      }

      .hljs-left {
        text-align: left;
      }

      .hljs-center {
        text-align: center;
      }

      .hljs-right {
        text-align: right;
      }
    }
  }
</style>
