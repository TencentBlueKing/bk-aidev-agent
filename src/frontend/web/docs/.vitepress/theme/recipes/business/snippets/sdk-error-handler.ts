/** 与 AIBlueking @sdk-error 的负载结构一致 */
export interface SdkError {
  apiName: 'chat' | 'getAgentInfo' | 'init' | 'session' | 'share';
  code: number;
  message: string;
  data: unknown;
  source?: 'business' | 'http' | 'protocol';
  action?: string;
}

export interface BusinessNotice {
  level: 'warning' | 'error';
  text: string;
}

/** code 目前恒为 -1；HTTP 状态码在原始错误 data.response.status 中 */
export function httpStatusOf(error: SdkError): number | undefined {
  return (error.data as { response?: { status?: number } } | null)?.response?.status;
}

// ① 把 sdk-error 转成业务自己的提示：配合 :error-toast="false" 关闭内置 toast
export function toBusinessNotice(error: SdkError): BusinessNotice {
  if (httpStatusOf(error) === 401) return { level: 'warning', text: '登录已失效，请刷新页面后重新登录。' };
  if (error.apiName === 'init' || error.apiName === 'getAgentInfo') {
    return { level: 'error', text: '智能助手暂时不可用，请稍后重试。' };
  }
  if (error.apiName === 'chat') return { level: 'error', text: `回复生成失败：${error.message}` };
  return { level: 'error', text: error.message || '操作失败，请稍后重试。' };
}

// 用法：<AIBlueking :url="apiUrl" :error-toast="false" @sdk-error="notice = toBusinessNotice($event)" />
