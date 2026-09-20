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
              <span v-if="item.type === 'text'">{{ item.text }}</span>
              <MentionTag
                v-else-if="item.type === 'tag'"
                :description="item.data.description"
                :icon="item.data.icon"
                :label="item.data.label"
                :type="item.data.type"
                :value="item.data.value"
              />
            </template>
          </template>
          <template v-else>
            <br />
          </template>
        </div>
      </template>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { customRef, onMounted, onUnmounted, useTemplateRef, watch } from 'vue';

  import { isEn } from '../../../common';
  import { useCommandSelection } from '../../../composables';
  import { type KeyboardPayload, createEditor, docToString, ReplaceAll, stringToDoc } from '../../../edix';
  import { MentionTag } from '../../mention';
  import { CHAR_TRIGGERS } from '../input-menu/constants';
  import { DeleteTag, InsertMenuTag, InsertText } from './command';
  import { tagSchema } from './constants';
  import { useMenuTrigger } from './use-menu-trigger';

  import type { TagSchema } from '../../../types/input';
  import type { IInputMenuItem, MenuTrigger } from '../../../types/input-menu';

  const editorRef = useTemplateRef<HTMLDivElement>('editorRef');
  const emit = defineEmits<{
    (e: 'update:modelValue', value: TagSchema): void;
    (e: 'keydown', event: KeyboardEvent & KeyboardPayload): void;
    (e: 'upload', files: File[]): void;
    (e: 'menuChange', payload: { keyword: string; trigger: MenuTrigger | null }): void;
  }>();

  const props = withDefaults(
    defineProps<{
      modelValue: string | TagSchema;
      placeholder?: string;
    }>(),
    {
      placeholder: isEn ? `Please enter content` : `请输入内容`,
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
        emit('update:modelValue', value);
        trigger();
      },
    };
  });

  const { commandSelection, GetCursorPosition, GetDocSnapshot, docSnapshot } = useCommandSelection();
  const menuTrigger = useMenuTrigger();

  let editor: ReturnType<typeof createEditor>;
  /* 清理编辑器 */
  let cleanup: () => void;
  // 卸载前需清理延迟任务，避免 setTimeout 回调在 window 已销毁后仍执行
  let syncTimer: null | ReturnType<typeof setTimeout> = null;
  let focusTimer: null | ReturnType<typeof setTimeout> = null;
  const clearPendingTimers = () => {
    if (syncTimer !== null) {
      clearTimeout(syncTimer);
      syncTimer = null;
    }
    if (focusTimer !== null) {
      clearTimeout(focusTimer);
      focusTimer = null;
    }
  };

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

  watch([menuTrigger.trigger, menuTrigger.keyword], () => {
    emit('menuChange', { trigger: menuTrigger.trigger.value, keyword: menuTrigger.keyword.value });
  });

  /** 编辑器内容/光标变动后重算触发态；下一帧再读取，确保 DOM 已应用本次输入 */
  const scheduleSync = () => {
    if (syncTimer !== null) {
      clearTimeout(syncTimer);
    }
    syncTimer = setTimeout(() => {
      syncTimer = null;
      menuTrigger.sync();
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
    if ((CHAR_TRIGGERS as readonly string[]).includes(event.key)) {
      menuTrigger.activateChar(event.key as Exclude<MenuTrigger, 'plus'>);
    }
    scheduleSync();
    return undefined;
  };

  /** 聚焦编辑器并把光标放到末尾；只设选区不 focus 的话元素拿不到焦点，敲键盘不会有反应 */
  const setCaretToEnd = () => {
    if (typeof window === 'undefined' || !editorRef.value) return;
    editorRef.value.focus();
    const selection = window.getSelection();
    const range = document.createRange();
    if (selection) {
      range.selectNodeContents(editorRef.value);
      range.collapse(false);
      selection.removeAllRanges();
      selection.addRange(range);
    }
  };
  const focusToEnd = () => {
    if (focusTimer !== null) {
      clearTimeout(focusTimer);
    }
    focusTimer = setTimeout(() => {
      focusTimer = null;
      setCaretToEnd();
    }, 100);
  };

  /** 删除「触发符 + 过滤词」，返回删除后的起始位置 */
  const consumeTriggerText = (): [number, number] => {
    editor.command(GetCursorPosition);
    const { column, line } = commandSelection.value;
    const start = Math.max(column - menuTrigger.getConsumeLength(), 0);
    if (start < column) {
      editor.command(DeleteTag, [line, start], [line, column]);
    }
    return [line, start];
  };

  /** 插入菜单选项：先吃掉「触发符 + 过滤词」，再插入标签并补一个空格 */
  const insertMenuItem = (item: IInputMenuItem) => {
    const [line, start] = consumeTriggerText();
    editor.command(InsertMenuTag, [line, start], item);
    // 标签在文档中占一列，空格补在它之后
    editor.command(InsertText, [line, start + 1], ' ');
    menuTrigger.close();
    focusToEnd();
  };

  const replaceAll = (value: string) => {
    editor.command(ReplaceAll, value);
    menuTrigger.close();
    focusToEnd();
  };

  /**
   * 由外部（如文件产物面板）追加标签。
   *
   * 位置直接由文档末尾算出，不读光标：外部调用时编辑器通常没有焦点，
   * 而 DOM 选区与编辑器内部选区是异步同步的，依赖光标会插到错误的位置。
   */
  const appendMention = (item: IInputMenuItem) => {
    const doc = text.value ?? [];
    const line = Math.max(doc.length - 1, 0);
    // 文本节点按字符数计长，标签节点固定占一列（与 edix 的节点尺寸规则一致）
    const column = (doc[line] ?? []).reduce((acc, node) => acc + (node.type === 'text' ? node.text.length : 1), 0);
    editor.command(InsertMenuTag, [line, column], item);
    editor.command(InsertText, [line, column + 1], ' ');
    focusToEnd();
  };

  /**
   * + 号唤起聚合菜单。
   * 光标已在编辑器内时一律保持原位：contenteditable 上的 focus() 在未聚焦时会把光标顶到最前面，
   * 因此必须先判断再决定要不要接管光标；只有编辑器从未获得过光标时才落到末尾。
   */
  const openPlusMenu = () => {
    if (!editorRef.value) return;
    const anchorNode = window.getSelection()?.anchorNode ?? null;
    if (!anchorNode || !editorRef.value.contains(anchorNode)) {
      setCaretToEnd();
    }
    menuTrigger.activatePlus();
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
        scheduleSync();
      },
      onKeyDown: keyboard => {
        return handleKeyDown(keyboard as KeyboardEvent & KeyboardPayload);
      },
    });
    cleanup = editor.input(editorRef.value!);
  };
  onMounted(() => {
    initEditor();
    editorRef.value?.addEventListener('paste', handlePaste);
  });
  onUnmounted(() => {
    clearPendingTimers();
    editor.command(ReplaceAll, '');
    cleanup?.();
    editorRef.value?.removeEventListener('paste', handlePaste);
  });
  defineExpose({
    appendMention,
    cleanup: () => {
      editor.command(ReplaceAll, '');
      menuTrigger.close();
    },
    closeMenu: menuTrigger.close,
    consumeTriggerText,
    focus: focusToEnd,
    insertMenuItem,
    openPlusMenu,
    replaceAll,
  });
</script>
<style lang="scss">
  @use '../../../styles/variables.scss' as variables;

  .ai-slash-input-wrapper {
    display: flex;
    flex: 1;
    flex-direction: column;
    width: 100%;
    height: fit-content;
    min-height: 0; // 父级触达 max-height 后允许收缩并内部滚动
    overflow: auto;

    .ai-slash-input {
      box-sizing: border-box;
      width: 100%;

      // 默认保持 4 行高度，避免输入内容后 placeholder 消失导致高度抖动
      min-height: calc(var(--ai-line-height-compact, 20px) * 4 + var(--ai-spacing-comfortable, 8px) * 2);
      padding: var(--ai-spacing-comfortable, 8px);
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: variables.$color-text;
      outline: none;
      border: none;
      border-radius: 8px;
    }

    [contenteditable='true']:empty::before {
      color: #c4c6cc;
      pointer-events: none;
      content: attr(aria-placeholder) / '';
    }
  }
</style>
