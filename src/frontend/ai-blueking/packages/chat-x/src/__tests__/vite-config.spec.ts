import { describe, expect, it } from 'vitest';

import configFactory from '../../vite.config';

import type { UserConfig } from 'vite';

describe('chat-x vite config', () => {
  it('uses bk as the default BKUI SCSS prefix for standalone builds', () => {
    const config = configFactory({ command: 'build', mode: 'production' }) as UserConfig;

    expect(config.css?.preprocessorOptions?.scss?.additionalData).toContain('$bk-prefix: bk;');
  });
});
