const MAX_STRING = 24;
const MAX_JSON = 48;

interface ShortcutLike {
  name: string;
  components: { default?: unknown }[];
}

function isShortcutLike(value: unknown): value is ShortcutLike {
  return (
    !!value &&
    typeof value === 'object' &&
    typeof (value as { name?: unknown }).name === 'string' &&
    Array.isArray((value as { components?: unknown }).components)
  );
}

/** 把 expose 方法的参数压缩成一眼能看懂的摘要 */
export function describeArg(value: unknown): string {
  if (value === undefined) return 'undefined';
  if (typeof value === 'string') {
    const clipped = value.length > MAX_STRING ? `${value.slice(0, MAX_STRING)}…` : value;
    return JSON.stringify(clipped).replace(/\\n/g, '↵');
  }
  if (typeof value === 'function') return 'fn';
  if (isShortcutLike(value)) {
    const prefilled = value.components.some(c => c.default !== undefined && c.default !== null && c.default !== '');
    return `cmd「${value.name}」${prefilled ? ' /* 已预填 */' : ''}`;
  }
  if (typeof value === 'object' && value !== null) {
    const entries = Object.entries(value).map(([k, v]) => `${k}: ${typeof v === 'object' ? '…' : JSON.stringify(v)}`);
    const text = `{ ${entries.join(', ')} }`;
    return text.length > MAX_JSON ? `${text.slice(0, MAX_JSON)}… }` : text;
  }
  return String(value);
}

export function describeCall(method: string, args: unknown[]): string {
  let trimmed = args;
  while (trimmed.length && trimmed[trimmed.length - 1] === undefined) {
    trimmed = trimmed.slice(0, -1);
  }
  return `${method}(${trimmed.map(describeArg).join(', ')})`;
}
