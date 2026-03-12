import type { Config as DOMPurifyConfig } from 'dompurify';

/**
 * 允许的自定义 URI 协议列表
 * 在此处添加业务需要的自定义协议即可全局生效
 */
const CUSTOM_URI_PROTOCOLS = ['wxwork', 'weixin', 'dingtalk', 'wework'];

const STANDARD_URI_PROTOCOLS = ['https?', 'ftps?', 'mailto', 'tel', 'callto', 'sms', 'cid', 'xmpp'];

/**
 * 构建 DOMPurify 允许的 URI 正则
 * 基于默认的标准协议白名单，扩展自定义协议支持
 * 同时通过白名单机制阻止 javascript: / vbscript: / data: 等危险协议
 */
const ALLOWED_URI_REGEXP = new RegExp(
  `^(?:(?:${[...STANDARD_URI_PROTOCOLS, ...CUSTOM_URI_PROTOCOLS].join('|')}):|[^a-z]|[a-z+.\\-]+(?:[^a-z+.\\-:]|$))`,
  'i',
);

const FORBID_TAGS = ['script', 'iframe', 'object', 'embed', 'form', 'input'] as const;

const FORBID_ATTR = ['onerror', 'onload', 'onclick', 'onmouseover'] as const;

/**
 * 基础 HTML 净化配置（用于 greeting 等简单 markdown 渲染场景）
 */
export const baseSanitizeConfig: DOMPurifyConfig = {
  USE_PROFILES: { html: true },
  ALLOWED_URI_REGEXP,
  FORBID_TAGS: [...FORBID_TAGS],
  FORBID_ATTR: [...FORBID_ATTR],
};

/**
 * 消息渲染净化配置（用于聊天消息，额外支持 SVG 标签和属性）
 */
export const messageSanitizeConfig: DOMPurifyConfig = {
  USE_PROFILES: { html: true, svg: true },
  ALLOWED_URI_REGEXP,
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
  FORBID_TAGS: [...FORBID_TAGS],
  FORBID_ATTR: [...FORBID_ATTR],
};
