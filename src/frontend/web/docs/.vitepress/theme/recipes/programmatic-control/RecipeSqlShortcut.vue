<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/sql-diagnosis.ts"
    kicker="配方 3"
    :source="source"
    title="SQL 报错，让小鲸用快捷指令诊断"
    when="适用：智能体配置了快捷指令，希望把业务页上的参数直接填进去"
  >
    <DemoStage
      app="数据查询平台"
      crumbs="查询历史"
    >
      <div class="demo-card">
        <div class="demo-field-label">执行的 SQL</div>
        <pre class="r3-sql">{{ SQL }}</pre>
        <div class="r3-error">{{ ERROR }}</div>
      </div>
      <div class="demo-card">
        <div class="demo-field-label">触发方式</div>
        <div
          class="r3-modes"
          role="radiogroup"
          aria-label="快捷指令触发方式"
        >
          <button
            v-for="m in MODES"
            :key="m.step"
            type="button"
            role="radio"
            class="r3-mode"
            :aria-checked="mode === m.step"
            :class="{ 'is-on': mode === m.step }"
            @click="selectMode(m.step)"
          >
            <span class="r3-mode__title">
              {{ m.title }}<span
                v-if="m.recommended"
                class="r3-mode__rec"
              >推荐</span>
            </span>
            <span class="r3-mode__sig">{{ m.signature }}</span>
          </button>
        </div>
        <div class="r3-desc">{{ currentMode.desc }}</div>
        <div
          v-if="commandState === 'none'"
          class="r3-empty"
        >
          当前智能体未配置快捷指令，可在页面顶部切回 Mock 体验。
        </div>
        <div class="demo-actions">
          <bk-button
            :disabled="commandState === 'none'"
            theme="primary"
            @click="handleRun"
          >
            让小鲸诊断这条报错
          </bk-button>
          <DemoFeedback
            :feedback="feedback"
            :recipe-id="RECIPE_ID"
          />
        </div>
      </div>
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';

  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import { resultFeedback } from '../../demo-kit/feedback';
  import type { FeedbackState } from '../../demo-kit/types';
  import { FLOATING_INSTANCE, useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { scoped } from './snippets/scoped-request-options';
  import { openEmptyForm, openPrefilledForm, sendDirectly } from './snippets/sql-diagnosis';
  import source from './snippets/sql-diagnosis.ts?raw';

  type ModeStep = '①' | '②' | '③';

  interface ModeOption {
    step: ModeStep;
    title: string;
    signature: string;
    desc: string;
    recommended?: boolean;
    done: FeedbackState;
  }

  const RECIPE_ID = 'sql';
  const SQL = 'SELECT id, level, create_time FROM alarm_event\nWHERE biz_id = 2 ORDER BY create_time DESC LIMIT 20;';
  const ERROR = `(1054, "Unknown column 'create_time' in 'field list'")`;
  const MODES: ModeOption[] = [
    {
      step: '①',
      title: '空表单',
      signature: 'selectShortcut(cmd)',
      desc: '打开面板并弹出快捷指令表单，字段为空，由用户自己填写后提交。',
      done: { kind: 'ok', text: '已打开空表单，请在右侧填写并发送。' },
    },
    {
      step: '②',
      title: '预填表单',
      signature: 'selectShortcut(prefilled)',
      desc: '把页面上的 SQL 和报错预填进表单，用户确认或修改后再提交。适合「智能填充」。',
      done: { kind: 'ok', text: '已预填表单，请在右侧确认后发送。' },
    },
    {
      step: '③',
      title: '直接发送',
      signature: 'sendShortcut + 单次注入',
      desc: '预填后跳过表单直接发送，并且只给这一次请求注入额外 Header，等价于旧版 handleShortcutClick(_, true)。',
      recommended: true,
      done: {
        kind: 'ok',
        text: '已直接发送，只有这次发送过程中的请求带了 set_ai_message。',
        goto: 'requests',
        gotoLabel: '打开「请求」对比',
      },
    },
  ];

  const runtime = useDemoRuntime();
  runtime.useRequestScope(scoped);

  const mode = ref<ModeStep>('③');
  const feedback = ref<FeedbackState | null>(null);
  const currentMode = computed(() => MODES.find(m => m.step === mode.value) ?? MODES[2]);
  runtime.selectStep(RECIPE_ID, mode.value);

  /** 真实智能体可能没有配置快捷指令 */
  const commandState = computed<'unknown' | 'ok' | 'none'>(() => {
    const info = runtime.getInstance(FLOATING_INSTANCE)?.getChatHelper()?.agent.info.value;
    if (!info) return 'unknown';
    return info.conversationSettings?.commands?.length ? 'ok' : 'none';
  });

  const selectMode = (step: ModeStep) => {
    mode.value = step;
    feedback.value = null;
    runtime.selectStep(RECIPE_ID, step);
  };

  const handleRun = async () => {
    const current = currentMode.value;
    const result = await runtime.run(RECIPE_ID, current.step, ai => {
      if (current.step === '①') return openEmptyForm(ai);
      if (current.step === '②') return openPrefilledForm(ai, SQL, ERROR);
      return sendDirectly(ai, SQL, ERROR);
    });
    feedback.value = resultFeedback(result, () => current.done);
  };
</script>

<style scoped>
  .r3-sql {
    padding: 10px 12px;
    margin: 0;
    font-family: var(--vp-font-family-mono);
    font-size: 12px;
    line-height: 1.6;
    white-space: pre-wrap;
    background: #f5f7fa;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .r3-error {
    padding: 8px 12px;
    margin-top: 10px;
    font-family: var(--vp-font-family-mono);
    font-size: 12px;
    color: #ea3636;
    background: #ffeded;
    border: 1px solid #fdd;
    border-radius: 2px;
  }

  .r3-modes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
  }

  .r3-mode {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 10px 12px;
    text-align: left;
    cursor: pointer;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .r3-mode:hover {
    border-color: #a3c5fd;
  }

  .r3-mode.is-on {
    border-color: #3a84ff;
    box-shadow: inset 0 0 0 1px #3a84ff;
  }

  .r3-mode__title {
    display: flex;
    gap: 6px;
    align-items: center;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .r3-mode__rec {
    padding: 0 6px;
    margin-left: auto;
    font-size: 11px;
    font-weight: 400;
    color: #1a9f45;
    background: #e5f6ea;
    border-radius: 2px;
  }

  .r3-mode__sig {
    font-family: var(--vp-font-family-mono);
    font-size: 11px;
    color: #979ba5;
  }

  .r3-desc {
    margin-top: 10px;
    font-size: 12px;
    line-height: 1.6;
    color: #63656e;
  }

  .r3-empty {
    padding: 8px 12px;
    margin-top: 10px;
    font-size: 12px;
    color: #b45309;
    background: #fff3e1;
    border-radius: 2px;
  }

  @media (max-width: 720px) {
    .r3-modes {
      grid-template-columns: 1fr;
    }
  }
</style>
