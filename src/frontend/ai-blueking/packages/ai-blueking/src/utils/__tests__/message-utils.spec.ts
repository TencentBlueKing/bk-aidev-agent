import { describe, expect, it } from 'vitest';

import {
  collectTurnMessages,
  collectTurnMessagesByAnchor,
  resolveForkContentId,
  resolveTurnLastContentId,
} from '../message-utils';

const user = (id?: string) => ({ id, role: 'user' });
const assistant = (id: string) => ({ id, role: 'assistant' });
const tool = (id: string) => ({ id, role: 'tool' });

describe('resolveForkContentId', () => {
  it('returns the last numeric id from the end of the group', () => {
    expect(resolveForkContentId([{ id: 'tmp' }, { id: 1052 }, { id: '1053' }])).toBe(1053);
  });

  it('accepts a numeric id at the end', () => {
    expect(resolveForkContentId([{ id: 1052 }])).toBe(1052);
  });

  it('skips streaming ids that are not persisted numbers', () => {
    expect(resolveForkContentId([{ id: 'assistant-tmp' }, { id: 'uuid-like' }])).toBeUndefined();
  });

  it('returns undefined for an empty group', () => {
    expect(resolveForkContentId([])).toBeUndefined();
  });
});

describe('resolveTurnLastContentId', () => {
  const server = [
    { id: 10, role: 'user' },
    { id: 11, role: 'assistant' },
    { id: 20, role: 'user' },
    { id: 21, role: 'reasoning' },
    { id: 22, role: 'assistant' },
  ];

  it('matches the turn by user message id and returns its last persisted id', () => {
    const streamed = { role: 'assistant' };
    const local = [{ id: 10, role: 'user' }, { id: 11, role: 'assistant' }, { id: 20, role: 'user' }, streamed];

    expect(resolveTurnLastContentId(server, local, streamed)).toBe(22);
  });

  it('falls back to the user message ordinal when the user id is still temporary', () => {
    const streamed = { role: 'assistant' };
    const local = [{ id: 10, role: 'user' }, { id: 11, role: 'assistant' }, { id: 'temp_1', role: 'user' }, streamed];

    expect(resolveTurnLastContentId(server, local, streamed)).toBe(22);
  });

  it('returns the user message id when the reply of the turn is not persisted yet', () => {
    const streamed = { messageId: 'stream-a', role: 'assistant' };
    const local = [{ id: 396, role: 'user' }, streamed];

    expect(resolveTurnLastContentId([{ id: 396, role: 'user' }], local, streamed)).toBe(396);
  });

  it('returns undefined when the anchor is not in the local list', () => {
    expect(resolveTurnLastContentId(server, [{ id: 10, role: 'user' }], { role: 'assistant' })).toBeUndefined();
  });
});

describe('collectTurnMessages', () => {
  it('collects from the user message up to the next user message', () => {
    const u1 = user('u1');
    const a1 = assistant('a1');
    const t1 = tool('t1');
    const u2 = user('u2');

    expect(collectTurnMessages([u1, a1, t1, u2, assistant('a2')], u1)).toEqual([u1, a1, t1]);
  });

  it('returns null when the user message is not in the list', () => {
    expect(collectTurnMessages([user('u1')], user('u1'))).toBeNull();
  });
});

describe('collectTurnMessagesByAnchor', () => {
  it('returns the whole turn including messages outside the anchor group', () => {
    const u1 = user('u1');
    const t0 = tool('t0');
    const a1 = assistant('a1');
    const t1 = tool('t1');
    const u2 = user('u2');

    expect(collectTurnMessagesByAnchor([u1, t0, a1, t1, u2], a1)).toEqual([u1, t0, a1, t1]);
  });

  it('returns null when the anchor is missing', () => {
    const u1 = user('u1');
    const a1 = assistant('a1');

    expect(collectTurnMessagesByAnchor([u1, a1], undefined)).toBeNull();
    expect(collectTurnMessagesByAnchor([u1, a1], { ...a1 })).toBeNull();
  });

  it('returns null when no user message precedes the anchor', () => {
    const a1 = assistant('a1');

    expect(collectTurnMessagesByAnchor([a1, user('u1')], a1)).toBeNull();
  });

  it('returns null instead of jumping to an earlier turn when the nearest user has no id', () => {
    const a1 = assistant('a1');

    expect(collectTurnMessagesByAnchor([user('u0'), assistant('a0'), user(), a1], a1)).toBeNull();
  });
});
