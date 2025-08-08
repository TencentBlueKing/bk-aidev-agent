import DOMPurify from 'dompurify';
import hljs from 'highlight.js';
import MarkdownIt from 'markdown-it';
import MarkdownItCodeCopy from 'markdown-it-copy-code';
import { computed, type Ref } from 'vue';

import MarkdownItLinkBlank from '../plugins/markdown-it-link-blank';
import mermaidPlugin from '../plugins/markdown-it-mermaid';

/**
 * Markdown 渲染 composable
 * 提供统一的 markdown 渲染功能，与 render-message 保持一致
 */
export function useMarkdown() {
  // 创建与 render-message 相同配置的 markdown 实例
  const md = new MarkdownIt({
    html: true,
    breaks: true,
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

  /**
   * 渲染 markdown 文本
   * @param text markdown 文本
   * @returns 渲染后的 HTML
   */
  const renderMarkdown = (text: string): string => {
    if (!text) return '';

    try {
      const rendered = md.render(text);
      // 使用 DOMPurify 净化内容以防止 XSS
      const sanitized = DOMPurify.sanitize(rendered, {
        USE_PROFILES: { html: true },
        FORBID_TAGS: ['script', 'iframe', 'object', 'embed', 'form', 'input'],
        FORBID_ATTR: ['onerror', 'onload', 'onclick', 'onmouseover'],
      });
      // 移除末尾的空白段落标签
      return sanitized.replace(/\s*<\/p>\s*$/, '</p>');
    } catch (error) {
      console.warn('Markdown rendering failed:', error);
      // 如果渲染失败，返回转义后的纯文本
      return text.replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }
  };

  /**
   * 创建响应式的 markdown 渲染计算属性
   * @param source 源文本的 ref
   * @returns 渲染后的 HTML 计算属性
   */
  const createMarkdownRenderer = (source: Ref<string>) => {
    return computed(() => renderMarkdown(source.value));
  };

  return {
    renderMarkdown,
    createMarkdownRenderer,
  };
}
