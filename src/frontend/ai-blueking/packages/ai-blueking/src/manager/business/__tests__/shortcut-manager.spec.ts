import { describe, it, expect, vi, beforeEach } from 'vitest';

import { ShortcutManager } from '../shortcut-manager';
import type { IShortcut } from '../types';

function makeShortcut(id: string, label = `Shortcut ${id}`): IShortcut {
  return { id, label } as IShortcut;
}

describe('ShortcutManager', () => {
  let manager: ShortcutManager;
  let mockEventEmitter: { emit: ReturnType<typeof vi.fn> };

  beforeEach(() => {
    vi.clearAllMocks();
    mockEventEmitter = { emit: vi.fn() };
    manager = new ShortcutManager(mockEventEmitter);
  });

  describe('effectiveShortcuts priority', () => {
    it('should return empty array when no shortcuts are set', () => {
      expect(manager.effectiveShortcuts.value).toEqual([]);
      expect(manager.hasShortcuts).toBe(false);
      expect(manager.count).toBe(0);
    });

    it('should return props shortcuts when set', () => {
      const shortcuts = [makeShortcut('1'), makeShortcut('2')];
      manager.setShortcuts(shortcuts);

      expect(manager.effectiveShortcuts.value).toEqual(shortcuts);
      expect(manager.count).toBe(2);
      expect(manager.hasShortcuts).toBe(true);
    });

    it('should return agent shortcuts when no props shortcuts exist', () => {
      const agentShortcuts = [makeShortcut('a1'), makeShortcut('a2')];
      manager.setAgentShortcuts(agentShortcuts);

      expect(manager.effectiveShortcuts.value).toEqual(agentShortcuts);
    });

    it('should prioritize props shortcuts over agent shortcuts', () => {
      const propsShortcuts = [makeShortcut('p1')];
      const agentShortcuts = [makeShortcut('a1')];
      manager.setShortcuts(propsShortcuts);
      manager.setAgentShortcuts(agentShortcuts);

      expect(manager.effectiveShortcuts.value).toEqual(propsShortcuts);
    });
  });

  describe('setShortcuts', () => {
    it('should replace existing props shortcuts', () => {
      manager.setShortcuts([makeShortcut('1')]);
      manager.setShortcuts([makeShortcut('2'), makeShortcut('3')]);

      expect(manager.effectiveShortcuts.value).toEqual([makeShortcut('2'), makeShortcut('3')]);
    });
  });

  describe('getShortcutById', () => {
    it('should return the matching shortcut', () => {
      const s1 = makeShortcut('s1');
      const s2 = makeShortcut('s2');
      manager.setShortcuts([s1, s2]);

      expect(manager.getShortcutById('s2')).toEqual(s2);
    });

    it('should return undefined when not found', () => {
      manager.setShortcuts([makeShortcut('s1')]);

      expect(manager.getShortcutById('nonexistent')).toBeUndefined();
    });
  });

  describe('constructor with initial props shortcuts', () => {
    it('should accept initial shortcuts via constructor', () => {
      const initial = [makeShortcut('init1')];
      const mgr = new ShortcutManager(null, initial);

      expect(mgr.effectiveShortcuts.value).toEqual(initial);
      expect(mgr.hasShortcuts).toBe(true);
    });
  });
});
