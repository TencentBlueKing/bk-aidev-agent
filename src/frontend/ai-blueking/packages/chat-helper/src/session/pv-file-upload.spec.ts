/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { describe, expect, it } from 'vitest';

import { isPvFileUploadSupported } from './pv-file-upload';

describe('isPvFileUploadSupported', () => {
  it.each([
    [undefined, false],
    ['', false],
    ['not-a-version', false],
    ['2.2.2rc17', false],
    ['2.2.2rc24', false],
    ['2.2.1', false],
    ['2.2.2b4', false],
    ['2.2.2-beta.4', false],
  ])('treats %s as legacy upload', (version, expected) => {
    expect(isPvFileUploadSupported(version)).toBe(expected);
  });

  it.each([
    ['2.2.2rc25', true],
    ['2.2.2-rc.25', true],
    ['2.2.2-rc25', true],
    ['2.2.2rc26', true],
    ['2.2.2', true],
    ['2.3.0', true],
    ['2.2.3rc1', true],
  ])('treats %s as pv_files upload', (version, expected) => {
    expect(isPvFileUploadSupported(version)).toBe(expected);
  });
});
