type RuntimeGlobalKey = 'BK_AIDEV_API_URL' | 'BK_AIDEV_URL';

type RuntimeGlobalsWindow = Window & Partial<Record<RuntimeGlobalKey, string>>;

export function getRuntimeGlobal(key: RuntimeGlobalKey): string {
  if (typeof window === 'undefined') {
    return '';
  }

  const value = (window as RuntimeGlobalsWindow)[key];
  return typeof value === 'string' ? value : '';
}
