import { reactive } from 'vue';

import type { RecipeRecords, RecordedRequest, TimelineKind } from './types';

export const MAX_RECORDS_PER_RECIPE = 200;

export function formatClock(date: Date): string {
  const pad = (n: number, size = 2) => String(n).padStart(size, '0');
  return `${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}.${pad(date.getMilliseconds(), 3)}`;
}

export interface DemoRecorder {
  records: Record<string, RecipeRecords>;
  get(recipeId: string): RecipeRecords;
  addEvent(recipeId: string, kind: TimelineKind, text: string): void;
  addRequest(recipeId: string, req: Omit<RecordedRequest, 'id' | 'time'>): number;
  updateRequest(recipeId: string, id: number, patch: Partial<Pick<RecordedRequest, 'status' | 'sse'>>): void;
  clear(recipeId?: string): void;
}

/** 按配方归档的事件 / 请求时间线 */
export function createDemoRecorder(now: () => Date = () => new Date()): DemoRecorder {
  const records = reactive<Record<string, RecipeRecords>>({});
  let seq = 0;

  const get = (recipeId: string): RecipeRecords => {
    if (!records[recipeId]) records[recipeId] = { events: [], requests: [] };
    return records[recipeId];
  };

  const trim = <T>(list: T[]) => {
    if (list.length > MAX_RECORDS_PER_RECIPE) list.splice(0, list.length - MAX_RECORDS_PER_RECIPE);
  };

  return {
    records,
    get,
    addEvent(recipeId, kind, text) {
      seq += 1;
      const list = get(recipeId).events;
      list.push({ id: seq, time: formatClock(now()), kind, text });
      trim(list);
    },
    addRequest(recipeId, req) {
      seq += 1;
      const list = get(recipeId).requests;
      list.push({ ...req, id: seq, time: formatClock(now()) });
      trim(list);
      return seq;
    },
    updateRequest(recipeId, id, patch) {
      const target = get(recipeId).requests.find(r => r.id === id);
      if (target) Object.assign(target, patch);
    },
    clear(recipeId) {
      const ids = recipeId ? [recipeId] : Object.keys(records);
      for (const id of ids) {
        const r = get(id);
        r.events.splice(0);
        r.requests.splice(0);
      }
    },
  };
}
