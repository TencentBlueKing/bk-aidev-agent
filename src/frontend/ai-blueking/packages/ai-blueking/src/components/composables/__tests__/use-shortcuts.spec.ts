import { describe, it, expect, vi } from 'vitest';
import { ref, computed, defineComponent, shallowRef } from 'vue';
import { mount } from '@vue/test-utils';

import {
  createErrorReporterParams,
  createMockChatHelper,
  createMockEmit,
  createMockShortcut,
} from '../../../__tests__/helpers';

import { useShortcuts } from '../use-shortcuts';
import type { UseShortcutsParams } from '../use-shortcuts';
import type { ChatBotProps } from '../../types';

function withSetup(composableFn: () => any) {
  let result: any;
  const Comp = defineComponent({
    setup() {
      result = composableFn();
      return () => null;
    },
  });
  const wrapper = mount(Comp);
  return { result, wrapper };
}

function createParams(overrides: Partial<UseShortcutsParams> = {}): UseShortcutsParams {
  const emit = overrides.emit ?? createMockEmit();
  return {
    props: {} as ChatBotProps,
    emit,
    reportError: createErrorReporterParams(emit).reportError,
    chatHelper: shallowRef(createMockChatHelper()),
    shortcutManager: shallowRef({
      effectiveShortcuts: computed(() => []),
      shortcuts: computed(() => []),
      setShortcuts: vi.fn(),
      setAgentShortcuts: vi.fn(),
    } as any),
    doSendMessage: vi.fn().mockResolvedValue(undefined),
    selectedShortcut: ref(null),
    ...overrides,
  };
}

describe('useShortcuts', () => {
  describe('selectShortcutWithText', () => {
    it('should set component default and formModel when fillBackKey + text', () => {
      const params = createParams();
      const shortcut = createMockShortcut({
        components: [{ key: 'input', name: 'Input', type: 'textarea', fillBack: true }],
      });

      const { result, wrapper } = withSetup(() => useShortcuts(params));
      result.selectShortcutWithText(shortcut, 'selected text');

      expect(params.selectedShortcut.value).toBeTruthy();
      expect((params.selectedShortcut.value as any).formModel.input).toBe('selected text');
      const inputComp = (params.selectedShortcut.value as any).components?.find((c: any) => c.key === 'input');
      expect(inputComp?.default).toBe('selected text');

      wrapper.unmount();
    });

    it('should set component default via enable_fill_back and fill_back_component_key', () => {
      const params = createParams();
      const shortcut = createMockShortcut({
        enable_fill_back: true,
        fill_back_component_key: 'input',
        components: [{ key: 'input', name: 'Input', type: 'textarea', fillBack: false }],
      });

      const { result, wrapper } = withSetup(() => useShortcuts(params));
      result.selectShortcutWithText(shortcut, 'text via fill_back');

      expect((params.selectedShortcut.value as any).formModel.input).toBe('text via fill_back');
      wrapper.unmount();
    });

    it('should spread shortcut data without fillBackKey', () => {
      const params = createParams();
      const shortcut = createMockShortcut({
        components: [{ key: 'input', name: 'Input', type: 'textarea', fillBack: false }],
      });

      const { result, wrapper } = withSetup(() => useShortcuts(params));
      result.selectShortcutWithText(shortcut);

      expect(params.selectedShortcut.value).toBeTruthy();
      expect(params.selectedShortcut.value!.id).toBe('shortcut-1');
      expect(params.selectedShortcut.value!.formModel).toEqual({});
      wrapper.unmount();
    });
  });

  describe('buildShortcutProperty', () => {
    it('should construct correct property structure with cite/command/context', () => {
      const params = createParams();
      const { result, wrapper } = withSetup(() => useShortcuts(params));

      const shortcut = createMockShortcut({
        id: 'cmd-1',
        alias: 'My Alias',
        components: [
          { key: 'input', name: 'Input Field', type: 'textarea' },
          { key: 'lang', name: 'Language', type: 'select' },
        ],
      });
      const formModel = { input: 'hello world', lang: 'python' };

      const property = result.buildShortcutProperty(shortcut, formModel);

      expect(property.extra.command).toBe('cmd-1');
      expect(property.extra.cite.title).toBe('My Alias');
      expect(property.extra.cite.type).toBe('structured');
      expect(property.extra.cite.data).toEqual([
        { key: 'Input Field', value: 'hello world' },
        { key: 'Language', value: 'python' },
      ]);
      expect(property.extra.context).toHaveLength(2);
      expect(property.extra.context[0]).toMatchObject({
        input: 'hello world',
        context_type: 'textarea',
        __key: 'input',
        __value: 'hello world',
      });
      wrapper.unmount();
    });

    it('should use name as cite title when alias is not provided', () => {
      const params = createParams();
      const { result, wrapper } = withSetup(() => useShortcuts(params));

      const shortcut = createMockShortcut({ alias: undefined, name: 'Test Shortcut' });
      const property = result.buildShortcutProperty(shortcut, {});

      expect(property.extra.cite.title).toBe('Test Shortcut');
      wrapper.unmount();
    });
  });

  describe('getShortcutFromMessage', () => {
    it('should return shortcut from extra.shortcut', () => {
      const params = createParams();
      const { result, wrapper } = withSetup(() => useShortcuts(params));

      const shortcutData = { id: 's1', name: 'Test' };
      const message = { property: { extra: { shortcut: shortcutData } } };

      expect(result.getShortcutFromMessage(message)).toEqual(shortcutData);
      wrapper.unmount();
    });

    it('should find shortcut from effectiveShortcuts by extra.command', () => {
      const matchingShortcut = createMockShortcut({ id: 'cmd-1' });
      const params = createParams({
        shortcutManager: shallowRef({
          effectiveShortcuts: computed(() => [matchingShortcut]),
          shortcuts: computed(() => []),
          setShortcuts: vi.fn(),
          setAgentShortcuts: vi.fn(),
        } as any),
      });
      const { result, wrapper } = withSetup(() => useShortcuts(params));

      const message = { property: { extra: { command: 'cmd-1' } } };
      expect(result.getShortcutFromMessage(message)).toEqual(matchingShortcut);
      wrapper.unmount();
    });

    it('should return null when no shortcut or command in extra', () => {
      const params = createParams();
      const { result, wrapper } = withSetup(() => useShortcuts(params));

      expect(result.getShortcutFromMessage({ property: {} })).toBeNull();
      expect(result.getShortcutFromMessage({})).toBeNull();
      wrapper.unmount();
    });
  });

  describe('handleShortcutSubmit', () => {
    it('should call doSendMessage with property and close shortcut panel', async () => {
      const params = createParams();
      const shortcut = createMockShortcut();
      params.selectedShortcut.value = shortcut as any;

      const { result, wrapper } = withSetup(() => useShortcuts(params));

      await result.handleShortcutSubmit({ input: 'value' });

      expect(params.doSendMessage).toHaveBeenCalledWith('Test Shortcut', {
        property: expect.objectContaining({ extra: expect.any(Object) }),
      });
      expect(params.selectedShortcut.value).toBeNull();
      wrapper.unmount();
    });

    it('should restore previousShortcut on error', async () => {
      const doSendMessage = vi.fn().mockRejectedValue(new Error('send failed'));
      const params = createParams({ doSendMessage });
      const shortcut = createMockShortcut();
      params.selectedShortcut.value = shortcut as any;

      const { result, wrapper } = withSetup(() => useShortcuts(params));

      await result.handleShortcutSubmit({ input: 'value' });

      expect(params.selectedShortcut.value).toEqual(shortcut);
      expect(params.emit).toHaveBeenCalledWith('error', expect.any(Error));
      wrapper.unmount();
    });

    it('should do nothing when no selectedShortcut', async () => {
      const params = createParams();
      params.selectedShortcut.value = null;

      const { result, wrapper } = withSetup(() => useShortcuts(params));
      await result.handleShortcutSubmit({});

      expect(params.doSendMessage).not.toHaveBeenCalled();
      wrapper.unmount();
    });
  });

  describe('handleSelectShortcut', () => {
    it('should call selectShortcutWithText and emit shortcut-click', () => {
      const params = createParams();
      const shortcut = createMockShortcut({
        components: [{ key: 'input', name: 'Input', type: 'textarea', fillBack: true }],
      });

      const { result, wrapper } = withSetup(() => useShortcuts(params));
      result.handleSelectShortcut(shortcut, 'some text');

      expect(params.selectedShortcut.value).toBeTruthy();
      expect(params.emit).toHaveBeenCalledWith('shortcut-click', {
        shortcut: expect.any(Object),
        source: 'main',
      });
      wrapper.unmount();
    });
  });

  describe('handleCloseShortcut', () => {
    it('should set selectedShortcut to null', () => {
      const params = createParams();
      params.selectedShortcut.value = createMockShortcut() as any;

      const { result, wrapper } = withSetup(() => useShortcuts(params));
      result.handleCloseShortcut();

      expect(params.selectedShortcut.value).toBeNull();
      wrapper.unmount();
    });
  });
});
