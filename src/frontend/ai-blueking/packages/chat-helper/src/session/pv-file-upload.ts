/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

/** 含此版本起走 pv_files/upload；更早版本继续走旧 upload/{fileName}/ */
export const PV_FILE_UPLOAD_MIN_SDK_VERSION = '2.2.2rc25';

type PreKind = 'a' | 'b' | 'final' | 'rc';

interface ParsedSdkVersion {
  major: number;
  minor: number;
  patch: number;
  pre: PreKind;
  preNum: number;
}

const PRE_RANK: Record<PreKind, number> = {
  a: 0,
  b: 1,
  rc: 2,
  final: 3,
};

const PRE_ALIAS: Record<string, PreKind> = {
  a: 'a',
  alpha: 'a',
  b: 'b',
  beta: 'b',
  c: 'rc',
  pre: 'rc',
  rc: 'rc',
};

const SDK_VERSION_RE = /^(\d+)\.(\d+)\.(\d+)(?:[-.]?(a|alpha|b|beta|c|pre|rc)[.-]?(\d+))?$/i;

const parseSdkVersion = (raw: string): null | ParsedSdkVersion => {
  const matched = raw.trim().match(SDK_VERSION_RE);
  if (!matched) {
    return null;
  }

  const pre = matched[4] ? PRE_ALIAS[matched[4].toLowerCase()] : 'final';
  return {
    major: Number(matched[1]),
    minor: Number(matched[2]),
    patch: Number(matched[3]),
    pre,
    preNum: matched[5] ? Number(matched[5]) : 0,
  };
};

const compareSdkVersion = (left: ParsedSdkVersion, right: ParsedSdkVersion): number => {
  if (left.major !== right.major) {
    return left.major - right.major;
  }
  if (left.minor !== right.minor) {
    return left.minor - right.minor;
  }
  if (left.patch !== right.patch) {
    return left.patch - right.patch;
  }
  if (PRE_RANK[left.pre] !== PRE_RANK[right.pre]) {
    return PRE_RANK[left.pre] - PRE_RANK[right.pre];
  }
  return left.preNum - right.preNum;
};

/**
 * 仅当能解析出版本且低于 2.2.2rc25 时走旧 upload/{fileName}/。
 * 空字符串、缺省或无法解析一律走 pv_files/upload。
 */
export const isPvFileUploadSupported = (version?: null | string): boolean => {
  const parsed = version ? parseSdkVersion(version) : null;
  const min = parseSdkVersion(PV_FILE_UPLOAD_MIN_SDK_VERSION);
  if (!parsed || !min) {
    return true;
  }
  return compareSdkVersion(parsed, min) >= 0;
};
