/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */

import { type ComputedRef, type Ref, computed, ref, watch } from 'vue';

import type { ModelSelectionConfig } from './types';
import type { IAgentModule, ILlmItem, ISession, ISessionModule, ReasoningEffort } from '@blueking/chat-helper';

/** 拖动滑块会连续跨档，写入会话前合并为最后一档 */
const REASONING_PERSIST_DELAY_MS = 300;

/**
 * 启用模型选择但无可用模型时抛出
 *
 * 用于阻断建会话：宁可失败并上报，也不把「前端选不上的 model」写给后端
 */
export class ModelUnavailableError extends Error {
  constructor(message = '当前没有可用模型，无法创建会话') {
    super(message);
    this.name = 'ModelUnavailableError';
  }
}

/**
 * 模型选择管理器
 *
 * 职责（模型相关状态与规则的唯一归属）：
 * - 持有可用模型列表与当前选中项
 * - 保证「选中项」与「写给后端的 model」都落在可用列表内
 * - 作为 session.model 写回后端的唯一出口
 *
 * 由 AIBlueking 创建并与内嵌 ChatBot 共享同一实例，使外壳层（会话创建）
 * 与聊天层（模型切换）读到同一份选中状态，无需反向读取子组件。
 */
export class ModelSelectionManager {
  private _isLoading: Ref<boolean>;
  private _models: Ref<ILlmItem[]>;
  private _reasoningEffort: Ref<ReasoningEffort | null>;
  private _selectedLlmCode: Ref<string | undefined>;
  private _selectedModelName: ComputedRef<string>;
  private _selectedModelSupportsVision: ComputedRef<boolean>;

  private agentModule: IAgentModule | null;
  /** 已同步过思考深度的会话；sessionCode 变化时才用详情覆盖本地档位 */
  private boundSessionCode: string | undefined;
  private config: ModelSelectionConfig;
  /** 进行中的加载，供共享实例的多方调用复用 */
  private loadPromise: null | Promise<void> = null;
  /** 按 sessionCode 记录在途的 model 写回，用于合并重复写回 */
  private pendingPersist = new Map<string, { llmCode: string; promise: Promise<void> }>();
  private reasoningPersistTimer: ReturnType<typeof setTimeout> | null = null;
  /** 被新档位或切会话取代的那次防抖写回，用它结束调用方的 Promise */
  private resolveSupersededPersist: (() => void) | null = null;
  private sessionModule: ISessionModule | null;

  /** 默认模型：property.default 优先，否则首项 */
  private defaultModelCode(): string | undefined {
    const list = this._models.value;
    return (list.find(m => m.property?.default) ?? list[0])?.llm_code;
  }

  /** 模型切换写回完成后，本地档位仍为空时采用服务端算出的生效档 */
  private applyServerReasoningIfUnset(sessionCode: string): void {
    if (this._reasoningEffort.value) {
      return;
    }
    const current = this.sessionModule?.current?.value;
    if (!current || current.sessionCode !== sessionCode || this.boundSessionCode !== sessionCode) {
      return;
    }
    this._reasoningEffort.value = current.effectiveReasoningEffort ?? null;
  }

  private cancelReasoningPersist(): void {
    if (this.reasoningPersistTimer) {
      clearTimeout(this.reasoningPersistTimer);
      this.reasoningPersistTimer = null;
    }
    this.resolveSupersededPersist?.();
    this.resolveSupersededPersist = null;
  }

  /** 当前选中是否仍在可用模型列表中 */
  private hasValidSelection(): boolean {
    const code = this._selectedLlmCode.value;
    return !!code && this._models.value.some(m => m.llm_code === code);
  }

  /** sessionModule 存在但 current 尚未就绪时，不落 default，避免挡住 session.model */
  private isSessionPending(): boolean {
    return this.sessionModule != null && this.sessionModule.current?.value == null;
  }

  private scheduleReasoningPersist(effort: ReasoningEffort): Promise<void> {
    this.cancelReasoningPersist();
    return new Promise<void>((resolve, reject) => {
      this.resolveSupersededPersist = resolve;
      this.reasoningPersistTimer = setTimeout(() => {
        this.reasoningPersistTimer = null;
        this.resolveSupersededPersist = null;
        this.flushReasoningPersist(effort).then(resolve, reject);
      }, REASONING_PERSIST_DELAY_MS);
    });
  }

  private selectedModel(): ILlmItem | undefined {
    const code = this._selectedLlmCode.value;
    if (!code) {
      return undefined;
    }
    return this._models.value.find(item => item.llm_code === code);
  }

  /**
   * 进入会话或模型列表就绪时同步选中项。
   * 思考深度只在 sessionCode 变化时用 effectiveReasoningEffort 覆盖，避免刷新详情冲掉用户刚选的档。
   */
  private syncFromSession(session?: ISession | null): void {
    const code = session?.sessionCode;
    if (code !== this.boundSessionCode) {
      this.boundSessionCode = code;
      this.cancelReasoningPersist();
      this._reasoningEffort.value = session?.effectiveReasoningEffort ?? null;
    }
    this.applySessionModel(session?.model);
  }

  constructor(
    agentModule: IAgentModule | null,
    sessionModule: ISessionModule | null = null,
    config: ModelSelectionConfig = {},
  ) {
    this.agentModule = agentModule;
    this.sessionModule = sessionModule;
    this.config = config;

    this._models = ref<ILlmItem[]>([]);
    this._selectedLlmCode = ref<string | undefined>(undefined);
    this._reasoningEffort = ref<ReasoningEffort | null>(null);
    this._isLoading = ref(false);
    this._selectedModelName = computed(() => {
      const code = this._selectedLlmCode.value;
      if (!code) {
        return '';
      }
      return this._models.value.find(m => m.llm_code === code)?.llm_name ?? '';
    });
    this._selectedModelSupportsVision = computed(() => {
      const code = this._selectedLlmCode.value;
      if (!code) {
        return false;
      }
      const model = this._models.value.find(m => m.llm_code === code);
      return Boolean(model?.property?.support_vision);
    });

    // 仅在 sessionCode 变化时同步模型与思考深度（同一会话的 updateSession 改写 current 引用时不覆盖用户选中）
    if (this.enabled && this.sessionModule) {
      watch(
        () => this.sessionModule!.current?.value?.sessionCode,
        () => {
          this.syncFromSession(this.sessionModule!.current?.value);
        },
      );
    }
  }

  /** 是否启用模型选择；关闭时不解析、不校验，也不视为异常 */
  get enabled(): boolean {
    return this.config.enabled !== false;
  }

  /** 模型列表加载中 */
  get isLoading(): Ref<boolean> {
    return this._isLoading;
  }

  /** 可用模型列表 */
  get models(): Ref<ILlmItem[]> {
    return this._models;
  }

  /** 当前模型生效的思考深度；null 时选择器按模型 default_effort 展示 */
  get reasoningEffort(): Ref<ReasoningEffort | null> {
    return this._reasoningEffort;
  }

  /** 当前选中模型的 llm_code */
  get selectedLlmCode(): Ref<string | undefined> {
    return this._selectedLlmCode;
  }

  /** 当前选中模型的 llm_name（ModelSelector v-model 绑定展示名） */
  get selectedModelName(): ComputedRef<string> {
    return this._selectedModelName;
  }

  /** 当前选中模型是否支持 vision（图生文能力标签，不再用于附件入口） */
  get selectedModelSupportsVision(): ComputedRef<boolean> {
    return this._selectedModelSupportsVision;
  }

  /**
   * 按 session.model 同步选中：
   * - 命中列表 → 选中
   * - 空 / 未知 → 保留有效选中；否则 default / 首项
   */
  applySessionModel(modelCode?: string): void {
    const list = this._models.value;
    if (list.length === 0) {
      this._selectedLlmCode.value = undefined;
      return;
    }
    if (this.isSessionPending()) {
      return;
    }
    if (modelCode && list.some(m => m.llm_code === modelCode)) {
      this._selectedLlmCode.value = modelCode;
      return;
    }
    if (this.hasValidSelection()) {
      return;
    }
    this._selectedLlmCode.value = this.defaultModelCode();
  }

  /**
   * 确保模型列表已就绪（幂等）
   *
   * 建会话前调用：已有列表直接返回，进行中则复用同一 Promise，
   * 避免外壳层与内嵌 ChatBot 重复拉取。
   */
  ensureLoaded(): Promise<void> {
    if (!this.enabled || this._models.value.length > 0) {
      return Promise.resolve();
    }
    if (this.loadPromise) {
      return this.loadPromise;
    }
    this.loadPromise = this.loadModels().finally(() => {
      this.loadPromise = null;
    });
    return this.loadPromise;
  }

  /**
   * 拉取可用模型列表；已有 agent.models 时复用
   *
   * 失败不抛出（列表置空）：是否阻断由调用方按场景决定，
   * 建会话场景由 resolveModelForSession 抛 ModelUnavailableError。
   */
  async loadModels(options: { force?: boolean } = {}): Promise<void> {
    this._isLoading.value = true;
    try {
      const cached = this.agentModule?.models?.value;
      if (!options.force && Array.isArray(cached) && cached.length > 0) {
        this._models.value = [...cached];
      } else if (typeof this.agentModule?.getLlms === 'function') {
        const list = await this.agentModule.getLlms();
        this._models.value = Array.isArray(list) ? list : [];
      } else {
        this._models.value = [];
      }
      this.syncFromSession(this.sessionModule?.current?.value);
    } catch (error) {
      console.error('[ModelSelectionManager] Failed to load models:', error);
      this._models.value = [];
      this._selectedLlmCode.value = undefined;
    } finally {
      this._isLoading.value = false;
    }
  }

  /**
   * 将 model 写回 session（session.model 与 sessionCode 同级）
   *
   * 唯一写回出口：模型切换与「复用空会话」都走此处。
   * @param session 目标会话，缺省为当前会话；复用空会话时需在 switch 前写回
   */
  async persistSessionModel(llmCode?: string, session?: ISession | null): Promise<void> {
    const target = session ?? this.sessionModule?.current?.value;
    if (!target?.sessionCode || !llmCode || target.model === llmCode) {
      return;
    }
    const { sessionCode } = target;
    // 选择模型时 v-model 与 change 事件会各写回一次，请求未返回前 target.model 仍是旧值，
    // 这里按「会话 + 模型」合并在途请求
    const inFlight = this.pendingPersist.get(sessionCode);
    if (inFlight?.llmCode === llmCode) {
      return inFlight.promise;
    }
    const promise = Promise.resolve(
      this.sessionModule!.updateSession({
        ...target,
        model: llmCode,
      }),
    )
      .then(() => {
        this.applyServerReasoningIfUnset(sessionCode);
      })
      .finally(() => {
        if (this.pendingPersist.get(sessionCode)?.promise === promise) {
          this.pendingPersist.delete(sessionCode);
        }
      });
    this.pendingPersist.set(sessionCode, { llmCode, promise });
    return promise;
  }

  /**
   * 解析建会话 / 写回时使用的 model，保证结果落在可用列表内
   *
   * @param preferred 期望使用的 llm_code；不在列表内时忽略并回退
   * @returns 未启用模型选择时原样透传 preferred（不做校验，缺省即不写 model）
   * @throws ModelUnavailableError 启用模型选择但无可用模型
   */
  resolveModelForSession(preferred?: string): string | undefined {
    if (!this.enabled) {
      return preferred;
    }
    const list = this._models.value;
    if (list.length === 0) {
      throw new ModelUnavailableError();
    }
    if (preferred && list.some(m => m.llm_code === preferred)) {
      return preferred;
    }
    if (this.hasValidSelection()) {
      return this._selectedLlmCode.value;
    }
    return this.defaultModelCode();
  }

  /**
   * 使用外部传入的模型列表（跳过接口拉取）
   */
  setModels(models: ILlmItem[]): void {
    this._models.value = models;
    this.syncFromSession(this.sessionModule?.current?.value);
  }

  /**
   * 按模型选项设置选中（@model-change 回调）。
   * 换模型时清空本地档位，与选择器「换模型即回到默认档」一致；新档位由随后的 commitReasoningEffort 写入。
   */
  setSelectedModel(model: ILlmItem | null | undefined): void {
    const next = model?.llm_code;
    if (next !== this._selectedLlmCode.value) {
      this.setReasoningEffort(null);
    }
    this._selectedLlmCode.value = next;
  }

  /**
   * 按展示名设置选中模型（ModelSelector v-model 为 llm_name）
   */
  setSelectedModelByName(llmName: string): void {
    const next = llmName ? this._models.value.find(item => item.llm_name === llmName)?.llm_code : undefined;
    if (next !== this._selectedLlmCode.value) {
      this.setReasoningEffort(null);
    }
    this._selectedLlmCode.value = next;
  }

  /**
   * 同步选择器 v-model。清空（切换模型）时取消尚未发出的档位写回。
   */
  setReasoningEffort(effort: ReasoningEffort | null): void {
    this._reasoningEffort.value = effort;
    if (!effort) {
      this.cancelReasoningPersist();
    }
  }

  /**
   * 用户在描述卡片里选定档位。先更新本地值，防抖后再单独写入会话。
   * 被后续档位或切会话取代时 resolve；写回失败时 reject，本地档位保持不变（下一轮对话仍按它发送）。
   */
  commitReasoningEffort(effort: ReasoningEffort): Promise<void> {
    this._reasoningEffort.value = effort;
    return this.scheduleReasoningPersist(effort);
  }

  /**
   * 本轮 chat_completion 要带的档位。
   * 小鲸不读会话偏好，未显式选择时用当前模型的 default_effort，模型不支持时传 null。
   */
  resolveReasoningEffortForChat(): ReasoningEffort | null {
    if (this._reasoningEffort.value) {
      return this._reasoningEffort.value;
    }
    // 已选中模型时以该模型的默认档为准。换模型会先清空本地档位，
    // 此时会话里还是旧模型的 effective，不能拿来发给新模型。
    const model = this.enabled ? this.selectedModel() : undefined;
    if (model) {
      return this.defaultEffortOf(model);
    }
    return this.sessionModule?.current?.value?.effectiveReasoningEffort ?? null;
  }

  private defaultEffortOf(model: ILlmItem): ReasoningEffort | null {
    const reasoning = model.property?.reasoning;
    const efforts = reasoning?.supported_efforts ?? [];
    if (efforts.length === 0) {
      return null;
    }
    if (reasoning?.default_effort && efforts.some(item => item.key === reasoning.default_effort)) {
      return reasoning.default_effort;
    }
    return efforts[0]?.key ?? null;
  }

  private async flushReasoningPersist(effort: ReasoningEffort): Promise<void> {
    const sessionCode = this.sessionModule?.current?.value?.sessionCode;
    const update = this.sessionModule?.updateReasoningEffort;
    if (!sessionCode || typeof update !== 'function') {
      return;
    }
    if (this._reasoningEffort.value !== effort) {
      return;
    }

    const modelWrite = this.pendingPersist.get(sessionCode);
    if (modelWrite) {
      await modelWrite.promise.catch(() => undefined);
    }
    if (!this.isStillCurrent(sessionCode, effort)) {
      return;
    }

    const updated = await update(sessionCode, effort);
    if (!this.isStillCurrent(sessionCode, effort)) {
      return;
    }
    if (updated?.effectiveReasoningEffort) {
      this._reasoningEffort.value = updated.effectiveReasoningEffort;
    }
  }

  /** 写回期间用户没有再改档，也没有切走会话 */
  private isStillCurrent(sessionCode: string, effort: ReasoningEffort): boolean {
    return this._reasoningEffort.value === effort && this.sessionModule?.current?.value?.sessionCode === sessionCode;
  }
}
