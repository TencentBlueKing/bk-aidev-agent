import { beforeEach, describe, expect, it, vi } from 'vitest';

import { createMockEmit } from '../../../__tests__/helpers';
import { useErrorReporter } from '../use-error-reporter';

const { mockMessage } = vi.hoisted(() => ({
  mockMessage: vi.fn(),
}));

vi.mock('bkui-vue', () => ({
  Message: mockMessage,
}));

vi.mock('../../../lang', () => ({
  t: (key: string) => key,
}));

describe('useErrorReporter', () => {
  beforeEach(() => {
    vi.spyOn(console, 'error').mockImplementation(() => {});
    mockMessage.mockClear();
  });

  describe('reportError 归一化', () => {
    it('should pass through Error instances unchanged', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit);
      const error = new Error('boom');

      expect(reportError(error)).toBe(error);
      expect(emit).toHaveBeenCalledWith('error', error);
    });

    it('should wrap string rejections into an Error', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit);

      reportError('会话不存在');

      const [, reported] = emit.mock.calls[0];
      expect(reported).toBeInstanceOf(Error);
      expect(reported.message).toBe('会话不存在');
    });

    it('should use message field when a plain object is thrown', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit);

      reportError({ code: 'ERR', message: '会话已过期' });

      expect(emit.mock.calls[0][1].message).toBe('会话已过期');
    });

    it('should serialize objects without a message field', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit);

      reportError({ code: 40001 });

      expect(emit.mock.calls[0][1].message).toBe('{"code":40001}');
    });
  });

  describe('去重', () => {
    it('should emit error only once for the same Error instance', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit);
      const error = new Error('boom');

      reportError(error, 'first');
      reportError(error, 'second');

      expect(emit).toHaveBeenCalledTimes(1);
    });

    it('should emit error for distinct instances sharing a message', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit);

      reportError(new Error('boom'));
      reportError(new Error('boom'));

      expect(emit).toHaveBeenCalledTimes(2);
    });
  });

  describe('errorToast', () => {
    it('should toast error.message by default', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit);

      reportError(new Error('Bad Request'));

      expect(mockMessage).toHaveBeenCalledWith({
        message: 'Bad Request',
        theme: 'error',
      });
    });

    it('should use fallback message when error.message is empty', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit);

      reportError(new Error(''));

      expect(mockMessage).toHaveBeenCalledWith({
        message: '请求失败',
        theme: 'error',
      });
    });

    it('should not toast when errorToast is false', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit, { errorToast: false });

      reportError(new Error('Bad Request'));

      expect(emit).toHaveBeenCalledTimes(1);
      expect(mockMessage).not.toHaveBeenCalled();
    });

    it('should toast only once for the same Error instance', () => {
      const emit = createMockEmit();
      const { reportError } = useErrorReporter(emit);
      const error = new Error('Bad Request');

      reportError(error, 'first');
      reportError(error, 'second');

      expect(mockMessage).toHaveBeenCalledTimes(1);
    });

    it('should follow getter errorToast value', () => {
      const emit = createMockEmit();
      let enabled = true;
      const { reportError } = useErrorReporter(emit, { errorToast: () => enabled });

      reportError(new Error('first'));
      expect(mockMessage).toHaveBeenCalledTimes(1);

      enabled = false;
      reportError(new Error('second'));
      expect(mockMessage).toHaveBeenCalledTimes(1);
    });
  });

  describe('managerErrorBridge', () => {
    it.each(['chat-error', 'receive-error', 'session-error'])('should forward %s to the error emit', event => {
      const emit = createMockEmit();
      const { managerErrorBridge } = useErrorReporter(emit);
      const error = new Error('stop failed');

      managerErrorBridge.emit(event, { action: 'stop', error });

      expect(emit).toHaveBeenCalledWith('error', error);
    });

    it('should ignore non-error business events', () => {
      const emit = createMockEmit();
      const { managerErrorBridge } = useErrorReporter(emit);

      managerErrorBridge.emit('send-message', { content: 'hello' });
      managerErrorBridge.emit('receive-end', {});
      managerErrorBridge.emit('session-switched', { session: null });

      expect(emit).not.toHaveBeenCalled();
    });

    // 业务管理器普遍「emit 失败事件后 rethrow」，桥接与调用点 catch 会拿到同一个实例
    it('should emit error once when the bridge and a call-site catch report the same error', () => {
      const emit = createMockEmit();
      const { managerErrorBridge, reportError } = useErrorReporter(emit);
      const error = new Error('stop failed');

      managerErrorBridge.emit('chat-error', { action: 'stop', error });
      reportError(error, 'Failed to stop generation');

      expect(emit).toHaveBeenCalledTimes(1);
      expect(mockMessage).toHaveBeenCalledTimes(1);
    });
  });
});
