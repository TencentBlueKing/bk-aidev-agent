import { describe, expect, it } from 'vitest';

import { collectTurnMessages, collectTurnMessagesByAnchor } from '../message-utils';

const user = (id?: string) => ({ id, role: 'user' });
const assistant = (id: string) => ({ id, role: 'assistant' });
const tool = (id: string) => ({ id, role: 'tool' });

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
