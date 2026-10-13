/**
 * 配方片段中每个步骤以 `// ①`（脚本）或 `<!-- ①`（模板）注释开头、以空行结束。
 * 返回该步骤所在的 0 基行区间 [start, end]，用于检查器高亮。
 */
export function findStepRange(source: string, marker: string): [number, number] | null {
  const lines = source.split('\n');
  const start = lines.findIndex(line => {
    const text = line.trimStart();
    return text.startsWith(`// ${marker}`) || text.startsWith(`<!-- ${marker}`);
  });
  if (start < 0) return null;
  let end = start;
  while (end + 1 < lines.length && lines[end + 1].trim() !== '') {
    end += 1;
  }
  return [start, end];
}

/** next 中相对 prev 新增或修改的行（0 基），用于生成型源码的变化高亮 */
export function diffLines(prev: string, next: string): number[] {
  const before = new Set(prev.split('\n'));
  return next.split('\n').flatMap((line, index) => (before.has(line) ? [] : [index]));
}
