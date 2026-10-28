import { toValue, type MaybeRefOrGetter } from 'vue';
import type { IRequestOptions } from '@blueking/ai-blueking';

export interface ResolvedRequestOptions {
  headers: () => Record<string, string>;
  data: () => Record<string, unknown>;
  /** 必须是值（getter 属性）：函数 / ref 形态的 context 会被静默丢弃 */
  readonly context?: IRequestOptions['context'];
}

/** IRequestOptions 的 headers / data 可以是值、ref 或无参函数 */
const resolveField = <T>(value: unknown): T | undefined => toValue(value as MaybeRefOrGetter<T>) ?? undefined;

/**
 * 把配方自己的 requestOptions 叠加到运行时的 requestOptions 上（运行时的 Mock 头在前，配方的同名字段覆盖）。
 * headers / data 为函数、context 为 getter，组件每次请求时读取，因此配方侧 ref / computed 的变化会自动生效。
 */
export function mergeRequestOptions(
  base: ResolvedRequestOptions,
  extra: MaybeRefOrGetter<IRequestOptions | undefined>,
): ResolvedRequestOptions {
  const current = () => toValue(extra) ?? {};
  return {
    headers: () => ({ ...base.headers(), ...(resolveField<Record<string, string>>(current().headers) ?? {}) }),
    data: () => ({ ...base.data(), ...(resolveField<Record<string, unknown>>(current().data) ?? {}) }),
    get context() {
      return resolveField<IRequestOptions['context']>(current().context) ?? base.context;
    },
  };
}
