import { ref } from 'vue';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { createMockChatHelper } from '../../__tests__/helpers';
import { pingSaasUrl, runAgentBootstrap } from '../agent-bootstrap';

describe('agent-bootstrap', () => {
  describe('pingSaasUrl', () => {
    beforeEach(() => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response()));
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it('should fetch saasUrl with GET and credentials include', () => {
      pingSaasUrl('https://saas.example.com/');

      expect(fetch).toHaveBeenCalledWith(`${window.location.protocol}//saas.example.com/`, {
        method: 'GET',
        credentials: 'include',
      });
    });

    it('should align saasUrl protocol with current page protocol', () => {
      pingSaasUrl('https://saas.example.com');

      expect(fetch).toHaveBeenCalledWith(`${window.location.protocol}//saas.example.com/`, {
        method: 'GET',
        credentials: 'include',
      });
    });

    it('should ignore fetch errors', async () => {
      vi.mocked(fetch).mockRejectedValueOnce(new Error('network error'));

      expect(() => pingSaasUrl('https://saas.example.com/')).not.toThrow();

      await vi.waitFor(() => {
        expect(fetch).toHaveBeenCalled();
      });
    });
  });

  describe('runAgentBootstrap', () => {
    beforeEach(() => {
      vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response()));
    });

    afterEach(() => {
      vi.unstubAllGlobals();
    });

    it('should call getAgentInfo and getSessions in parallel', async () => {
      const chatHelper = createMockChatHelper();

      await runAgentBootstrap(chatHelper);

      expect(chatHelper.agent.getAgentInfo).toHaveBeenCalled();
      expect(chatHelper.session.getSessions).toHaveBeenCalled();
    });

    it('should ping saasUrl when agent info contains saasUrl', async () => {
      const chatHelper = createMockChatHelper();
      chatHelper.agent.info = ref({ saasUrl: 'https://saas.example.com/' }) as typeof chatHelper.agent.info;

      await runAgentBootstrap(chatHelper);

      expect(fetch).toHaveBeenCalledWith(`${window.location.protocol}//saas.example.com/`, {
        method: 'GET',
        credentials: 'include',
      });
    });

    it('should not ping when saasUrl is missing', async () => {
      const chatHelper = createMockChatHelper();
      chatHelper.agent.info = ref({ agentName: 'test-agent' }) as typeof chatHelper.agent.info;

      await runAgentBootstrap(chatHelper);

      expect(fetch).not.toHaveBeenCalled();
    });
  });
});
