import { describe, it, expect, vi, beforeEach } from 'vitest';
import { nextTick, ref } from 'vue';

import { ModelSelectionManager, ModelUnavailableError } from '../model-selection-manager';

import type { ILlmItem } from '@blueking/chat-helper';

const sampleModels: ILlmItem[] = [
  {
    id: 1,
    llm_code: 'hy3-preview',
    llm_name: '混元3',
    llm_type: 'chat.completion',
    max_token_size: 32768,
    property: { default: true },
    space_auth_mode: '',
    user_auth_mode: '',
  },
  {
    id: 2,
    llm_code: 'deepseek',
    llm_name: 'DeepSeek',
    llm_type: 'chat.completion',
    max_token_size: 64000,
    property: {},
    space_auth_mode: '',
    user_auth_mode: '',
  },
];

function createMocks() {
  const mockAgentModule = {
    getLlms: vi.fn().mockResolvedValue(sampleModels),
    models: ref<ILlmItem[]>([]),
    isModelsLoading: ref(false),
  };
  const mockSessionModule = {
    current: ref<{ model?: string; sessionCode: string; sessionName: string } | null>({
      sessionCode: 'session-1',
      sessionName: 'chat',
    }),
    updateSession: vi.fn().mockResolvedValue(undefined),
  };
  return { mockAgentModule, mockSessionModule };
}

describe('ModelSelectionManager', () => {
  let mocks: ReturnType<typeof createMocks>;
  let manager: ModelSelectionManager;

  beforeEach(() => {
    vi.clearAllMocks();
    mocks = createMocks();
    manager = new ModelSelectionManager(
      mocks.mockAgentModule as never,
      mocks.mockSessionModule as never,
    );
  });

  it('should load models and select default', async () => {
    await manager.loadModels({ force: true });

    expect(mocks.mockAgentModule.getLlms).toHaveBeenCalled();
    expect(manager.models.value).toEqual(sampleModels);
    expect(manager.selectedLlmCode.value).toBe('hy3-preview');
  });

  it('should reuse cached agent.models without calling getLlms', async () => {
    mocks.mockAgentModule.models.value = sampleModels;

    await manager.loadModels();

    expect(mocks.mockAgentModule.getLlms).not.toHaveBeenCalled();
    expect(manager.selectedLlmCode.value).toBe('hy3-preview');
  });

  it('should resolve preferred when it is in the list', () => {
    manager.setModels(sampleModels);

    expect(manager.resolveModelForSession('deepseek')).toBe('deepseek');
  });

  it('should fall back to selected / default when preferred is not in the list', () => {
    manager.setModels(sampleModels);
    manager.setSelectedModelByName('DeepSeek');

    expect(manager.resolveModelForSession('not-in-list')).toBe('deepseek');
  });

  it('should throw ModelUnavailableError when enabled but list is empty', () => {
    expect(() => manager.resolveModelForSession('deepseek')).toThrow(ModelUnavailableError);
  });

  it('should pass through preferred when model select is disabled', () => {
    manager = new ModelSelectionManager(
      mocks.mockAgentModule as never,
      mocks.mockSessionModule as never,
      { enabled: false },
    );

    expect(manager.resolveModelForSession('any-model')).toBe('any-model');
    expect(manager.resolveModelForSession()).toBeUndefined();
  });

  it('should persist session model only when different', async () => {
    mocks.mockSessionModule.current.value = {
      sessionCode: 'session-1',
      sessionName: 'chat',
      model: 'hy3-preview',
    };

    await manager.persistSessionModel('deepseek');
    expect(mocks.mockSessionModule.updateSession).toHaveBeenCalledWith(
      expect.objectContaining({ sessionCode: 'session-1', model: 'deepseek' }),
    );

    mocks.mockSessionModule.updateSession.mockClear();
    await manager.persistSessionModel('deepseek', {
      sessionCode: 'session-1',
      sessionName: 'chat',
      model: 'deepseek',
    });
    expect(mocks.mockSessionModule.updateSession).not.toHaveBeenCalled();
  });

  it('should merge concurrent persists for the same session and model', async () => {
    mocks.mockSessionModule.current.value = {
      sessionCode: 'session-1',
      sessionName: 'chat',
      model: 'hy3-preview',
    };

    await Promise.all([manager.persistSessionModel('deepseek'), manager.persistSessionModel('deepseek')]);

    expect(mocks.mockSessionModule.updateSession).toHaveBeenCalledTimes(1);
  });

  it('should not merge persists when the target model differs', async () => {
    mocks.mockSessionModule.current.value = {
      sessionCode: 'session-1',
      sessionName: 'chat',
      model: 'hy3-preview',
    };

    await Promise.all([manager.persistSessionModel('deepseek'), manager.persistSessionModel('gpt-4')]);

    expect(mocks.mockSessionModule.updateSession).toHaveBeenCalledTimes(2);
  });

  it('should follow session.model when sessionCode changes', async () => {
    manager.setModels(sampleModels);
    manager.setSelectedModelByName('DeepSeek');
    expect(manager.selectedLlmCode.value).toBe('deepseek');

    mocks.mockSessionModule.current.value = {
      sessionCode: 'session-2',
      sessionName: 'history',
      model: 'hy3-preview',
    };
    await nextTick();

    expect(manager.selectedLlmCode.value).toBe('hy3-preview');
  });

  it('ensureLoaded should be idempotent and share in-flight promise', async () => {
    let resolveLlms!: (value: ILlmItem[]) => void;
    mocks.mockAgentModule.getLlms.mockReturnValue(
      new Promise<ILlmItem[]>(resolve => {
        resolveLlms = resolve;
      }),
    );

    const p1 = manager.ensureLoaded();
    const p2 = manager.ensureLoaded();
    expect(p1).toBe(p2);

    resolveLlms(sampleModels);
    await p1;
    await p2;

    expect(mocks.mockAgentModule.getLlms).toHaveBeenCalledTimes(1);
    expect(manager.selectedLlmCode.value).toBe('hy3-preview');

    await manager.ensureLoaded();
    expect(mocks.mockAgentModule.getLlms).toHaveBeenCalledTimes(1);
  });
});
