<template>
  <div class="ai-slash-input-wrapper">
    <div
      ref="editorRef"
      :aria-placeholder="placeholder"
      class="ai-slash-input"
      spellcheck="false"
    >
      <template v-if="text?.length && text.some(line => line.length)">
        <div
          v-for="(line, index) in text"
          :key="index"
        >
          <template v-if="line.length">
            <template
              v-for="(item, columnIndex) in line"
              :key="columnIndex"
            >
              <span
                v-if="item.type === 'text'"
                :class="{ 'ai-slash-input-spacer': !item.text?.trim() }"
              >{{ item.text }}</span>
              <span
                v-else-if="item.type === 'tag'"
                :class="`mention-tag-${item.data.type}`"
                contenteditable="false"
                :data-tag-type="item.data.type"
                :data-tag-value="item.data.value"
                :data-tag-label="item.data.label"
                :data-tag-icon="item.data.icon || ''"
              >
                <img
                  v-if="item.data.icon && !failedTagIcons.has(`${item.data.type}:${item.data.value}`)"
                  :src="item.data.icon"
                  alt=""
                  class="mention-tag-icon"
                  @error="failedTagIcons.add(`${item.data.type}:${item.data.value}`)"
                />
                <span
                  v-else
                  class="mention-tag-icon mention-tag-icon--fallback"
                >
                  {{ item.data.label?.[0]?.toUpperCase() }}
                </span>
                <span class="mention-tag-label">{{ item.data.label }}</span>
                <RemoveIcon
                  class="mention-tag-remove-icon"
                  @click="handleRemoveTag(line, item, columnIndex, index)"
                />
              </span>
            </template>
          </template>
          <template v-else>
            <br />
          </template>
        </div>
      </template>
    </div>
    <Tippy
      ref="tippyRef"
      :append-to="getBody"
      :arrow="false"
      :hide-on-click="true"
      :interactive="true"
      :max-width="'none'"
      :offset="[0, 8]"
      :popper-options="menuPopperOptions"
      placement="top-start"
      theme="light ai-slash-editor-theme"
      trigger="manual"
      :trigger-target="editorRef!"
      :z-index="EDITOR_MENU_Z_INDEX"
      @hidden="handleTippyHidden"
      @show="handleTippyShow"
    >
      <template #content>
        <AiSlashMenu
          v-if="menuType === 'slash'"
          :on-select="insertTagAtCursor"
          :resource-list="filteredResourceList"
        />
        <AiSkillList
          v-else-if="menuType === 'skill'"
          :on-select="insertSkillAtCursor"
          :skills="filteredSkills"
        />
        <AiPromptList
          v-else-if="menuType === 'prompt'"
          :on-select="insertPromptAtCursor"
          :prompts="filteredPrompts"
        />
      </template>
    </Tippy>
  </div>
</template>
<script setup lang="ts">
  import { customRef, nextTick, onMounted, onUnmounted, reactive, shallowRef, useTemplateRef, watch, watchEffect } from 'vue';

  import { Tippy, useTippy } from 'vue-tippy';

  import { EDITOR_MENU_Z_INDEX, isEn } from '../../../common';
  import { useCommandSelection } from '../../../composables';
  import { type KeyboardPayload, createEditor, docToString, ReplaceAll, stringToDoc } from '../../../edix';
  import { RemoveIcon } from '../../../icons';
  import AiPromptList from './ai-prompt-list/ai-prompt-list.vue';
  import AiSkillList from './ai-skill-list/ai-skill-list.vue';
  import AiSlashMenu from './ai-slash-menu/ai-slash-menu.vue';
  import { DeleteTag, InsertSkillTag, InsertTag, InsertText, SetCaret } from './command';
  import { tagSchema } from './constants';

  import type { IAiSlashMenuItem, ISkillListItem } from '../../../types/editor';
  import type { MentionMenuType, MentionState, TagSchema } from '../../../types/input';

  import 'tippy.js/dist/tippy.css';

  const editorRef = useTemplateRef<HTMLDivElement>('editorRef');
  const tippyRef = useTemplateRef<InstanceType<typeof Tippy> & ReturnType<typeof useTippy>>('tippyRef');
  const emit = defineEmits<{
    (e: 'update:modelValue', value: TagSchema, selectedResourceList: IAiSlashMenuItem[]): void;
    (e: 'keydown', event: KeyboardEvent & KeyboardPayload): void;
    (e: 'upload', files: File[]): void;
  }>();

  const props = withDefaults(
    defineProps<{
      modelValue: string | TagSchema;
      placeholder?: string;
      prompts?: string[];
      resources?: IAiSlashMenuItem[];
      skills?: ISkillListItem[];
    }>(),
    {
      placeholder: isEn ? `Please enter content` : `请输入内容`,
      prompts: () => [],
      resources: () => [],
      skills: () => [],
    },
  );

  const text = customRef((track, trigger) => {
    return {
      get(): TagSchema {
        track();
        if (typeof props.modelValue === 'string') {
          return stringToDoc(props.modelValue) as TagSchema;
        }
        return props.modelValue;
      },
      set(value: TagSchema) {
        const selectedResourceList =
          value
            ?.flat()
            ?.filter(item => item.type === 'tag')
            ?.map(item => {
              return (
                props.resources?.find(
                  resource =>
                    (resource.id === item.data.value || resource.name === item.data.value) &&
                    resource.type === item.data.type,
                ) || null
              );
            })
            ?.filter((item): item is IAiSlashMenuItem => Boolean(item)) || [];
        emit('update:modelValue', value, selectedResourceList);
        trigger();
      },
    };
  });

  /** 禁止 flip，避免面板翻转到输入框上挡住文字 */
  const menuPopperOptions = {
    modifiers: [
      { name: 'flip', enabled: false },
      { name: 'preventOverflow', options: { altAxis: false, padding: 8 } },
    ],
  };

  const menuType = shallowRef<'' | MentionMenuType>('slash');
  const keyword = shallowRef<string>('');
  const filteredResourceList = shallowRef<IAiSlashMenuItem[]>([]);
  const filteredSkills = shallowRef<ISkillListItem[]>([]);
  const filteredPrompts = shallowRef<string[]>([]);
  const failedTagIcons = reactive(new Set<string>());

  const TRIGGER_MENU_MAP = {
    '@': 'slash',
    '/': 'skill',
    '\\': 'prompt',
  } as const satisfies Record<string, MentionMenuType>;

  let editor: ReturnType<typeof createEditor>;
  /* 清理编辑器 */
  let cleanup: () => void;
  // 卸载前需清理延迟任务，避免 setTimeout 回调在 window 已销毁后仍执行
  let suggestionTimer: null | ReturnType<typeof setTimeout> = null;
  let focusTimer: null | ReturnType<typeof setTimeout> = null;
  /** 菜单关闭后再聚焦，避免 tippy 抢走焦点 */
  type PendingFocus =
    | { kind: 'end' }
    | { caretOffset: number; kind: 'tag'; line: number; tagType: string; tagValue: string };
  let pendingFocus: null | PendingFocus = null;
  const clearPendingTimers = () => {
    if (suggestionTimer !== null) {
      clearTimeout(suggestionTimer);
      suggestionTimer = null;
    }
    if (focusTimer !== null) {
      clearTimeout(focusTimer);
      focusTimer = null;
    }
    pendingFocus = null;
  };
  const getBody = () => document.body;

  /** 菜单锚定整个聊天输入框，宽度与输入框一致 */
  const getInputMenuRect = (): DOMRect => {
    const el =
      editorRef.value?.closest('.chat-input') ||
      editorRef.value?.closest('.ai-slash-input-wrapper') ||
      editorRef.value;
    return el?.getBoundingClientRect() ?? new DOMRect();
  };

  const syncMenuWidthToInput = (instance?: { popper?: HTMLElement }) => {
    const width = getInputMenuRect().width;
    if (!width) return;
    const box =
      (instance?.popper?.querySelector?.('.tippy-box') as HTMLElement | null | undefined) ||
      (document.querySelector('.tippy-box[data-theme~="ai-slash-editor-theme"]') as HTMLElement | null);
    if (box) {
      box.style.width = `${width}px`;
      box.style.maxWidth = `${width}px`;
    }
  };

  const { commandSelection, GetCursorPosition, GetDocSnapshot, docSnapshot } = useCommandSelection();

  watch(
    () => props.modelValue,
    () => {
      // 处理上层 modelValue 变化时，编辑器内容与 modelValue 不一致的情况，同步编辑器内容
      editor.command(GetDocSnapshot);
      if (docToString(docSnapshot.value || []) !== docToString(text.value || [])) {
        editor.command(ReplaceAll, docToString(text.value || []) as unknown as string);
      }
    },
    {
      deep: false,
    },
  );
  /** 同步解析触发符后的检索词，供输入过程实时过滤 */
  const refreshMentionQuery = (): MentionState => {
    const mentionState = getMentionState();
    if (mentionState.menuType) {
      menuType.value = mentionState.menuType;
    }
    keyword.value = mentionState.query || '';
    return mentionState;
  };
  /* 显示提示 */
  const handleShowSuggestions = () => {
    // 先同步更新 keyword，保证列表即时过滤（含中文 IME 组合过程）
    refreshMentionQuery();
    if (suggestionTimer !== null) {
      clearTimeout(suggestionTimer);
    }
    suggestionTimer = setTimeout(() => {
      suggestionTimer = null;
      const mentionState = refreshMentionQuery();
      // 锚定输入框上方，宽度与输入框一致
      if (mentionState.isActive) {
        tippyRef.value?.setProps({
          placement: 'top-start',
          maxWidth: 'none',
          getReferenceClientRect: getInputMenuRect,
        });
        tippyRef.value?.show();
      } else {
        tippyRef.value?.hide();
      }
    }, 16);
  };
  const handleKeyDown = (event: KeyboardEvent & KeyboardPayload) => {
    emit('keydown', event);
    if (event.key === 'Enter' || event.key === 'NumpadEnter') {
      if (event.shiftKey) {
        return undefined;
      }
      event.preventDefault?.();
      return false;
    }
    if (event.key === '@' || event.key === '/' || event.key === '\\') {
      if (event.key === '@') menuType.value = 'slash';
      if (event.key === '/') menuType.value = 'skill';
      if (event.key === '\\') menuType.value = 'prompt';
      handleShowSuggestions();
    }
  };
  /** 输入 / IME 组合过程中持续刷新过滤（edix 组合阶段不会触发 onChange） */
  const handleEditorQueryRefresh = () => {
    handleShowSuggestions();
  };
  const escapeSelectorValue = (value: string) => {
    if (typeof CSS !== 'undefined' && typeof CSS.escape === 'function') {
      return CSS.escape(value);
    }
    return value.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
  };

  /** 光标落到 tag 后 spacer 文本起点；与 tag 的 4px 间距由 mention-tag margin-right 保证 */
  const placeCaretAfterTagElement = (tagEl: HTMLElement): boolean => {
    const selection = window.getSelection();
    if (!selection) return false;
    const range = document.createRange();
    const next = tagEl.nextSibling;
    if (next) {
      const textNode =
        next.nodeType === Node.TEXT_NODE
          ? (next as Text)
          : next.firstChild?.nodeType === Node.TEXT_NODE
            ? (next.firstChild as Text)
            : null;
      if (textNode) {
        range.setStart(textNode, 0);
      } else {
        range.setStartAfter(next);
      }
    } else {
      range.setStartAfter(tagEl);
    }
    range.collapse(true);
    selection.removeAllRanges();
    selection.addRange(range);
    return true;
  };

  const placeCaretAtEnd = (el: HTMLElement) => {
    const selection = window.getSelection();
    if (!selection) return;
    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
  };

  /** 等 Vue 渲染出 tag 后聚焦；focus 会 syncSelection 覆盖 SetCaret，需在 commit 后再写回 DOM */
  const scheduleFocusAfterTag = (options: {
    caretOffset: number;
    line: number;
    tagType: string;
    tagValue: string;
  }) => {
    if (focusTimer !== null) {
      clearTimeout(focusTimer);
      focusTimer = null;
    }

    const tryFocus = (retriesLeft: number) => {
      focusTimer = null;
      const el = editorRef.value;
      if (!el || typeof window === 'undefined') return;

      const selector = `span.mention-tag-${escapeSelectorValue(options.tagType)}[data-tag-value="${escapeSelectorValue(String(options.tagValue))}"]`;
      const tags = el.querySelectorAll(selector);
      const tagEl = tags[tags.length - 1] as HTMLElement | undefined;

      if (!tagEl) {
        if (retriesLeft > 0) {
          focusTimer = setTimeout(() => tryFocus(retriesLeft - 1), 16);
          return;
        }
        el.focus({ preventScroll: true });
        placeCaretAtEnd(el);
        return;
      }

      el.focus({ preventScroll: true });
      // 纠正 onFocus → syncSelection 覆盖的编辑器选区
      editor.command(SetCaret, [options.line, options.caretOffset]);
      // 等 SetCaret commit 后再落到 DOM，避免 mutationObserver 用脏选区把光标拉走
      queueMicrotask(() => {
        placeCaretAfterTagElement(tagEl);
      });
    };

    void nextTick(() => {
      tryFocus(30);
    });
  };

  const scheduleFocusToEnd = () => {
    if (focusTimer !== null) {
      clearTimeout(focusTimer);
      focusTimer = null;
    }
    void nextTick(() => {
      const el = editorRef.value;
      if (!el || typeof window === 'undefined') return;
      el.focus({ preventScroll: true });
      queueMicrotask(() => {
        placeCaretAtEnd(el);
      });
    });
  };

  const flushPendingFocus = () => {
    if (!pendingFocus) return;
    const pending = pendingFocus;
    pendingFocus = null;
    if (pending.kind === 'tag') {
      scheduleFocusAfterTag(pending);
    } else {
      scheduleFocusToEnd();
    }
  };

  const requestFocusAfterInsert = (pending: PendingFocus) => {
    pendingFocus = pending;
    tippyRef.value?.hide();
    // tippy @hidden 优先；未展示或 hidden 未触发时用短延迟兜底
    if (focusTimer !== null) {
      clearTimeout(focusTimer);
    }
    focusTimer = setTimeout(() => {
      focusTimer = null;
      flushPendingFocus();
    }, 80);
  };

  const handleTippyHidden = () => {
    keyword.value = '';
    flushPendingFocus();
  };
  const getMentionState = (): MentionState => {
    const defaultState: MentionState = {
      isActive: false,
      query: '',
      rect: null,
      coordinates: null,
    };

    if (typeof window === 'undefined') return defaultState;

    const editorEl = editorRef.value;
    const selection = window.getSelection();
    if (!editorEl || !selection || selection.rangeCount === 0) return defaultState;
    if (!selection.anchorNode || !editorEl.contains(selection.anchorNode)) return defaultState;

    // 取编辑器内光标前的全部文本（跨 text/span 节点，兼容 Vue 重渲染与 IME）
    let textBeforeCursor = '';
    try {
      const preRange = selection.getRangeAt(0).cloneRange();
      preRange.selectNodeContents(editorEl);
      preRange.setEnd(selection.anchorNode, selection.anchorOffset);
      textBeforeCursor = preRange.toString();
    } catch {
      return defaultState;
    }

    // 光标前最后一个触发符及其后的检索词（遇空白则中断）
    const match = textBeforeCursor.match(/([@/\\])([^\s]*)$/);
    if (!match) return defaultState;

    const triggerChar = match[1] as keyof typeof TRIGGER_MENU_MAP;
    const query = match[2] || '';
    const detectedType = TRIGGER_MENU_MAP[triggerChar];
    if (!detectedType) return defaultState;

    const inputRect = getInputMenuRect();
    return {
      isActive: true,
      menuType: detectedType,
      query,
      rect: inputRect,
      coordinates: {
        top: inputRect.bottom,
        left: inputRect.left,
        height: inputRect.height,
      },
    };
  };
  const getStartPosition = (line: TagSchema[number], columnIndex: number) => {
    const startIndex = line.reduce((acc, item, index) => {
      if (index >= columnIndex) {
        return acc;
      }
      if (item.type === 'text') {
        acc += item.text?.length || 0;
      }
      if (item.type === 'tag') {
        acc += 1;
      }
      return acc;
    }, 0);
    return startIndex;
  };
  const insertTagAtCursor = (tag: IAiSlashMenuItem) => {
    editor.command(GetCursorPosition);
    const { column, line } = commandSelection.value;
    // 删除触发符 + 检索词后，在原起始位插入 tag，并在其后补一个空格
    const startColumn = Math.max(column - keyword.value.length - 1, 0);
    editor.command(DeleteTag, [line, startColumn], [line, column]);
    editor.command(InsertTag, [line, startColumn], tag);
    editor.command(InsertText, [line, startColumn + 1], ' ');
    // 光标在 tag 后空格起点；与 tag 的 4px 间距由 mention-tag margin-right 提供
    const caretOffset = startColumn + 1;
    editor.command(SetCaret, [line, caretOffset]);
    requestFocusAfterInsert({
      kind: 'tag',
      tagType: tag.type,
      tagValue: String(tag.id ?? tag.name),
      line,
      caretOffset,
    });
  };
  const focusToEnd = () => {
    requestFocusAfterInsert({ kind: 'end' });
  };
  const insertPromptAtCursor = (prompt: string) => {
    editor.command(ReplaceAll, prompt);
    requestFocusAfterInsert({ kind: 'end' });
  };
  const insertSkillAtCursor = (skill: ISkillListItem) => {
    editor.command(GetCursorPosition);
    const { column, line } = commandSelection.value;
    // 删除触发符 + 检索词后，在原起始位插入 tag，并在其后补一个空格，保证 tag 间距一致
    const startColumn = Math.max(column - keyword.value.length - 1, 0);
    editor.command(DeleteTag, [line, startColumn], [line, column]);
    editor.command(InsertSkillTag, [line, startColumn], skill);
    editor.command(InsertText, [line, startColumn + 1], ' ');
    const caretOffset = startColumn + 1;
    editor.command(SetCaret, [line, caretOffset]);
    requestFocusAfterInsert({
      kind: 'tag',
      tagType: 'skill',
      tagValue: skill.skill_code,
      line,
      caretOffset,
    });
  };
  watchEffect(() => {
    const resourceList = props.resources?.filter(
      item =>
        !text.value?.some(line =>
          line.some(
            lineItem => lineItem.type === 'tag' && lineItem.data.value === item.id && lineItem.data.type === item.type,
          ),
        ),
    );
    const skillList = props.skills?.filter(
      skill =>
        !text.value?.some(line =>
          line.some(
            lineItem =>
              lineItem.type === 'tag' && lineItem.data.value === skill.skill_code && lineItem.data.type === 'skill',
          ),
        ),
    );
    const query = keyword.value.trim().toLowerCase();
    if (!query) {
      filteredResourceList.value = resourceList;
      filteredSkills.value = skillList;
      filteredPrompts.value = props.prompts;
    } else {
      filteredResourceList.value = resourceList.filter(item => {
        const name = item.name?.toLowerCase() || '';
        const code = String(item.code ?? item.id ?? '').toLowerCase();
        return name.includes(query) || code.includes(query);
      });
      filteredSkills.value = skillList.filter(
        skill =>
          skill.skill_name.toLowerCase().includes(query) || skill.skill_code.toLowerCase().includes(query),
      );
      filteredPrompts.value = props.prompts.filter(prompt => prompt.toLowerCase().includes(query));
    }
    // 仅根据当前菜单类型判断是否隐藏，避免其它列表干扰
    const currentEmpty =
      (menuType.value === 'slash' && !filteredResourceList.value.length) ||
      (menuType.value === 'skill' && !filteredSkills.value.length) ||
      (menuType.value === 'prompt' && !filteredPrompts.value.length);
    if (currentEmpty) {
      tippyRef.value?.hide();
    }
  });
  const handleRemoveTag = (
    line: TagSchema[number],
    item: TagSchema[number][number],
    columnIndex: number,
    lineIndex: number,
  ) => {
    if (item.type === 'tag') {
      const startIndex = getStartPosition(line, columnIndex);
      editor.command(DeleteTag, [lineIndex, startIndex], [lineIndex, startIndex + 1]);
    }
  };
  const handlePaste = (event: ClipboardEvent) => {
    const items = event.clipboardData?.items;
    if (!items) return;

    const files: File[] = [];
    for (const item of items) {
      if (item.kind === 'file') {
        const file = item.getAsFile();
        if (file) {
          files.push(file);
        }
      }
    }

    if (files.length > 0) {
      event.preventDefault();
      emit('upload', files);
    }
  };

  const initEditor = () => {
    cleanup?.();
    editor = createEditor({
      doc: text.value,
      schema: tagSchema,
      onChange: async doc => {
        text.value = doc;
        handleShowSuggestions();
      },
      onKeyDown: keyboard => {
        return handleKeyDown(keyboard as KeyboardEvent & KeyboardPayload);
      },
    });
    cleanup = editor.input(editorRef.value!);
  };
  const handleTippyShow = (instance?: { popper?: HTMLElement }): false | void => {
    if (menuType.value === 'slash') {
      if (filteredResourceList.value.length < 1) return false;
    } else if (menuType.value === 'skill') {
      if (filteredSkills.value.length < 1) return false;
    } else if (filteredPrompts.value.length < 1) {
      return false;
    }
    syncMenuWidthToInput(instance);
    requestAnimationFrame(() => syncMenuWidthToInput(instance));
    return undefined;
  };
  onMounted(() => {
    initEditor();
    editorRef.value?.addEventListener('paste', handlePaste);
    // keyup / composition*：覆盖连续输入与中文 IME，保证检索词实时更新
    editorRef.value?.addEventListener('keyup', handleEditorQueryRefresh);
    editorRef.value?.addEventListener('compositionupdate', handleEditorQueryRefresh);
    editorRef.value?.addEventListener('compositionend', handleEditorQueryRefresh);
  });
  onUnmounted(() => {
    clearPendingTimers();
    editor.command(ReplaceAll, '');
    cleanup?.();
    editorRef.value?.removeEventListener('paste', handlePaste);
    editorRef.value?.removeEventListener('keyup', handleEditorQueryRefresh);
    editorRef.value?.removeEventListener('compositionupdate', handleEditorQueryRefresh);
    editorRef.value?.removeEventListener('compositionend', handleEditorQueryRefresh);
  });
  defineExpose({
    cleanup: () => {
      editor.command(ReplaceAll, '');
    },
    focus: focusToEnd,
  });
</script>
<style lang="scss">
  @use 'sass:list';
  @use '../../../styles/variables.scss' as variables;

  .ai-slash-input-wrapper {
    display: flex;
    flex: 1;
    flex-direction: column;
    width: 100%;
    height: fit-content;
    max-height: 400px;
    overflow: auto;

    @each $type, $color in variables.$resourceTypeMap {
      .mention-tag-#{$type} {
        position: relative;
        display: inline-flex;
        gap: 4px;
        align-items: center;
        box-sizing: border-box;
        // 高度跟随主题行高：small=20px / normal=24px；左右 8px / 图标 16px
        height: var(--ai-line-height, 20px);
        padding: 0 8px;
        // 与左右文字均保持 4px；后继 spacer 不再额外加 padding，避免叠成 8px
        margin: 0 4px;
        font-size: var(--ai-font-size, 12px);
        line-height: var(--ai-line-height, 20px);
        color: list.nth($color, 2);
        background: list.nth($color, 1);
        border-radius: 2px;
        vertical-align: middle;

        .mention-tag-icon {
          flex-shrink: 0;
          width: 16px;
          height: 16px;
          object-fit: contain;
          border-radius: 2px;

          &--fallback {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            font-weight: 700;
            line-height: 16px;
            color: #fff;
            background: #3a84ff;
          }
        }

        .mention-tag-label {
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .mention-tag-remove-icon {
          position: absolute;
          top: -7px;
          right: -7px; // 所有类型 tag 删除按钮统一落在右上角
          z-index: 1;
          display: none;
          align-items: center;
          justify-content: center;
          width: 14px;
          height: 14px;
          font-size: 14px;
          color: #4d4f56;
          cursor: pointer;
        }

        &:hover {
          color: list.nth($color, 5);
          background: list.nth($color, 4);

          .mention-tag-remove-icon {
            display: flex;
          }
        }
      }
    }

    .ai-slash-input {
      box-sizing: border-box;
      width: 100%;

      // 固定 4 行底高（与主题 line-height 一致），内容未超出时高度不变，超出后再撑开
      min-height: calc(var(--ai-line-height, 20px) * 4 + var(--ai-spacing-comfortable, 8px) * 2);
      padding: var(--ai-spacing-comfortable, 8px);
      font-size: var(--ai-font-size, 12px);
      // 跟随主题：small=20px / normal=24px；与 mention tag 高度一致
      line-height: var(--ai-line-height, 20px);
      color: #4d4f56;
      outline: none;
      border: none;
      border-radius: 8px;

      // 行内文字与 tag 共用 middle 对齐，避免基线导致上下错位
      > div > span {
        vertical-align: middle;
      }
    }

    .ai-slash-input-spacer {
      // 插入 tag 后的空格节点：裁掉空格字形，避免额外占宽；
      // 与 tag / 光标的 4px 间距由 mention-tag 的 margin: 0 4px 承担
      display: inline-block;
      width: 0;
      overflow: hidden;
      vertical-align: middle;
    }

    [contenteditable='true']:empty::before {
      color: #c4c6cc;
      pointer-events: none;
      content: attr(aria-placeholder) / '';
    }
  }

  .tippy-box[data-theme~='ai-slash-editor-theme'] {
    width: 100%;
    max-width: none !important;
    overflow: hidden !important;
    background-color: #fff !important;
    border: 1px solid #dcdee5 !important;
    border-radius: 8px !important; // 与聊天输入框一致
    outline: none !important;
    // 外阴影放在 tippy-box，避免被 overflow:hidden 裁切
    box-shadow: 0 2px 16px 0 #00000029 !important;

    &[data-theme~='light'] {
      background-color: #fff !important;
    }

    .tippy-content {
      width: 100%;
      padding: 0 !important;
      box-sizing: border-box;

      > span {
        display: block;
        width: 100%;
      }
    }
  }
</style>
