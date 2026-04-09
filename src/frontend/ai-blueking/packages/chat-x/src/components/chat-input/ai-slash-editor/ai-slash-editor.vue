<template>
  <div
    class="ai-slash-editor-wrapper"
    :class="{ 'ai-slash-editor-wrapper_disabled': disabled }"
  >
    <div
      ref="editorRef"
      class="ai-slash-editor"
    />
    <Tippy
      ref="tippyRef"
      :append-to="body"
      :arrow="false"
      :hide-on-click="true"
      :interactive="true"
      :offset="[0, 0]"
      placement="right-start"
      theme="light ai-slash-editor-theme"
      trigger="manual"
      :trigger-target="editorRef!"
      :z-index="EDITOR_MENU_Z_INDEX"
      @hidden="handleTippyHidden"
    >
      <template #content>
        <AiSlashMenu
          v-if="menuType === 'slash'"
          :on-select="insertTagAtCursor"
          :resource-list="filteredResourceList"
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
  import {
    computed,
    ref as deepRef,
    onMounted,
    onUnmounted,
    shallowRef,
    useTemplateRef,
    watch,
    watchEffect,
  } from 'vue';

  import { type IKeyboardEvent, KeyCode, editor as monacoEditor, Range } from 'monaco-editor';
  import { type useTippy, Tippy } from 'vue-tippy';

  import { EDITOR_MENU_Z_INDEX } from '../../../common';
  import AiPromptList from '../ai-slash-input/ai-prompt-list/ai-prompt-list.vue';
  import AiSlashMenu from '../ai-slash-input/ai-slash-menu/ai-slash-menu.vue';
  import { aiSlashEditorOptions } from './theme';

  import type { IAiSlashMenuItem } from '../../../types';

  import 'tippy.js/dist/tippy.css';

  const props = withDefaults(
    defineProps<{
      disabled?: boolean;
      modelValue?: string;
      placeholder?: string;
      prompts?: string[];
    }>(),
    {
      placeholder: aiSlashEditorOptions.placeholder,
      disabled: false,
      modelValue: '',
      prompts: () => [],
    },
  );

  const emit = defineEmits<{
    (e: 'update:modelValue', value: string): void;
    (e: 'focus'): void;
    (e: 'keydown', event: IKeyboardEvent): void;
    (e: 'layoutChange', layoutInfo: monacoEditor.EditorLayoutInfo): void;
  }>();

  const editorRef = useTemplateRef<HTMLDivElement>('editorRef');
  const tippyRef = useTemplateRef<InstanceType<typeof Tippy> & ReturnType<typeof useTippy>>('tippyRef');
  const body = document.body;

  let mentionDecorations: monacoEditor.IEditorDecorationsCollection | null = null;

  let editor: monacoEditor.IStandaloneCodeEditor;
  const selectedResourceList = shallowRef<IAiSlashMenuItem[]>([]);
  const keyword = deepRef<string>('');
  const resourceList = shallowRef<IAiSlashMenuItem[]>([
    {
      type: 'tool',
      name: '工具1撒旦法收到了客服',
      id: 'tool1',
      icon: 'icon-tool1',
    },
    {
      type: 'shortcut',
      name: '快捷1撒旦法收到',
      id: 'shortcut1',
      icon: 'icon-shortcut1',
    },
    {
      type: 'doc',
      name: '文档1',
      id: 'doc1',
      icon: 'icon-doc1',
    },
    {
      type: 'mcp',
      name: 'MCP1',
      id: 'mcp1',
      icon: 'icon-mcp1',
    },
    {
      type: 'tool',
      name: '工具2',
      id: 'tool2',
      icon: 'icon-tool2',
    },

    {
      type: 'shortcut',
      name: '快捷2',
      id: 'shortcut2',
      icon: 'icon-shortcut2',
    },

    {
      type: 'doc',
      name: '文档2',
      id: 'doc2',
      icon: 'icon-doc2',
    },
  ]);
  const filteredResourceList = shallowRef<IAiSlashMenuItem[]>([]);
  const filteredPrompts = shallowRef<string[]>([]);
  const menuType = shallowRef<'' | 'prompt' | 'slash'>('slash');
  const editorPreHeight = shallowRef(0);
  const suggestionChar = computed(() => {
    return menuType.value === 'prompt' ? '/' : '@';
  });
  watch(
    () => props.modelValue,
    newValue => {
      if (editor && editor.getValue() !== newValue) {
        editor.setValue(newValue);
        editor.setPosition({
          lineNumber: 1,
          column: newValue.length + 1,
        });
        const layoutInfo = editor.getLayoutInfo();
        editor.getModel()?.getLineCount();
        editor.layout(
          {
            width: layoutInfo.width,
            height: Math.max(88, aiSlashEditorOptions.lineHeight! * 3),
          },
          true,
        );
        editor.focus();
      }
    },
  );
  watch(
    () => props.disabled,
    newValue => {
      if (editor) {
        editor.updateOptions({
          readOnly: newValue,
          domReadOnly: newValue,
        });
      }
    },
    {
      immediate: true,
    },
  );
  const initEditor = () => {
    if (editorRef.value) {
      editor = monacoEditor.create(editorRef.value, {
        ...aiSlashEditorOptions,
        value: props.modelValue,
        placeholder: props.placeholder,
        readOnly: props.disabled,
        domReadOnly: props.disabled,
        padding: {
          top: 6,
          bottom: 0,
        },
      });
      editor.createDecorationsCollection([]);
      editor.onKeyDown(event => {
        emit('keydown', event);
        if (event.keyCode === KeyCode.LeftArrow || event.keyCode === KeyCode.RightArrow) {
          if (mentionDecorations?.length) {
            const position = editor?.getPosition();
            if (!position?.column) return;
            const positionColumn = event.keyCode === KeyCode.LeftArrow ? position.column - 1 : position.column + 1;
            for (const item of editor?.getModel()?.getAllDecorations() ?? []) {
              if (!mentionDecorations.has(item)) {
                continue;
              }
              const { range } = item;
              if (
                range.startLineNumber === position?.lineNumber &&
                range.startColumn <= positionColumn &&
                range.endColumn >= positionColumn
              ) {
                event.preventDefault();
                event.browserEvent.preventDefault();
                // 禁用不掉默认的 cursor 移动，导致出发了两次 cursor移动 需要保证这里是最终的位置
                setTimeout(() => {
                  editor.setPosition({
                    lineNumber: range.startLineNumber,
                    column: event.keyCode === KeyCode.LeftArrow ? range.startColumn - 1 : range.endColumn + 1,
                  });
                }, 1);
                return;
              }
            }
          }
          return;
        }
        if (event.keyCode === KeyCode.Backspace) {
          const contentHeight = editor?.getContentHeight();
          if (mentionDecorations?.length) {
            const model = editor?.getModel();
            if (!model) return;
            const position = editor.getPosition()!;

            for (const item of model.getAllDecorations()) {
              if (
                mentionDecorations.has(item) &&
                item.range.startLineNumber === position.lineNumber &&
                position.column - 1 <= item.range.endColumn &&
                position.column - 1 >= item.range.startColumn
              ) {
                event.preventDefault();
                model.pushEditOperations(
                  [],
                  [
                    {
                      range: item.range,
                      text: '',
                    },
                  ],
                  () => [],
                );
              }
            }
          }
          editor?.layout({
            width: editorRef.value!.parentElement!.clientWidth,
            height: Math.min(Math.max(contentHeight ?? 0, aiSlashEditorOptions.lineHeight! * 3), 400),
          });
          return;
        }
        if (event.keyCode === KeyCode.Enter) {
          if (!event.shiftKey) {
            event.preventDefault();
            event.browserEvent.preventDefault();
            return;
          }
        }
      });
      editor.onKeyUp(event => {
        if (event.browserEvent.key === '@') {
          menuType.value = 'slash';
          handleShowSuggestions();
        }
        if (event.browserEvent.key === '/') {
          menuType.value = 'prompt';
          handleShowSuggestions();
        }
      });
      editor.onDidChangeCursorPosition((event: monacoEditor.ICursorPositionChangedEvent) => {
        const position = event.position;
        if (!position?.lineNumber || !position?.column) return;
        const searchKeyword = getSearchKeyword();
        const currentChar = editor
          ?.getModel()
          ?.getValueInRange(new Range(position.lineNumber, position.column - 1, position.lineNumber, position.column));
        if (searchKeyword || currentChar === '@' || currentChar === '/') {
          keyword.value = searchKeyword;
          handleShowSuggestions();
          return;
        }
        tippyRef.value?.hide();
      });
      editor.onDidFocusEditorWidget(() => {
        handleShowSuggestions();
      });
      editor.onDidChangeModelContent(() => {
        updateDecorations();
        const contentHeight = editor?.getContentHeight() ?? 0;
        const scrollHeight = editor?.getScrollHeight() ?? 0;
        if (contentHeight >= scrollHeight) {
          editor?.layout({
            width: editorRef.value!.parentElement!.clientWidth,
            height: Math.min(contentHeight! + aiSlashEditorOptions.lineHeight!, 400),
          });
        }
        const value = editor.getValue();
        if (value !== props.modelValue) {
          emit('update:modelValue', value);
        }
      });
      editor.onDidScrollChange(() => {
        tippyRef.value?.hide();
      });
      editor.onDidFocusEditorText(() => {
        emit('focus');
      });
      editor.onDidLayoutChange(() => {
        const layoutInfo = editor.getLayoutInfo();
        if (editorPreHeight.value !== layoutInfo.height) {
          editorPreHeight.value = layoutInfo.height;
          emit('layoutChange', layoutInfo);
        }
      });
      mentionDecorations = editor.createDecorationsCollection();
    }
  };
  onMounted(() => {
    initEditor();
    window.addEventListener('resize', handleDocumentResize);
  });
  onUnmounted(() => {
    window.removeEventListener('resize', handleDocumentResize);
  });
  const handleDocumentResize = () => {
    tippyRef.value?.hide();
  };

  watchEffect(() => {
    if (!keyword.value) {
      filteredResourceList.value = resourceList.value;
      filteredPrompts.value = props.prompts;
    } else {
      filteredResourceList.value = resourceList.value.filter(item =>
        item.name.toLowerCase().includes(keyword.value.toLowerCase()),
      );
      filteredPrompts.value = props.prompts.filter(prompt =>
        prompt.toLowerCase().includes(keyword.value.toLowerCase()),
      );
    }
    if (!filteredResourceList.value.length && !filteredPrompts.value.length) {
      tippyRef.value?.hide();
    }
  });

  const insertTagAtCursor = (tag: IAiSlashMenuItem) => {
    const position = editor.getPosition()!;
    // 插入的位置是 @ 符号的位置
    const startColumn = position.column - keyword.value.length;
    const model = editor?.getModel();
    if (model && position && editor) {
      const range = new Range(position.lineNumber, startColumn - 1, position.lineNumber, startColumn);
      const textRange = new Range(
        position.lineNumber,
        range.endColumn + 1,
        position.lineNumber,
        range.endColumn + tag.name.length + 2,
      );
      if (keyword.value) {
        // 清空 keyword 区域
        model.pushEditOperations(
          [],
          [
            {
              range: new Range(
                position.lineNumber,
                startColumn - 1,
                position.lineNumber,
                startColumn + keyword.value.length,
              ),
              text: '',
            },
          ],
          () => null,
        );
      }
      // 插入 tag
      model.pushEditOperations(
        [],
        [
          {
            range,
            text: ' ',
          },
          {
            range: textRange,
            text: `@${tag.name}`,
          },
          {
            range: new Range(position.lineNumber, textRange.endColumn, position.lineNumber, textRange.endColumn + 1),
            text: ' ',
          },
        ],
        () => null,
      );
      selectedResourceList.value.push(tag);
      updateDecorations();
      editor.focus();
    }
  };
  const insertPromptAtCursor = (prompt: string) => {
    emit('update:modelValue', prompt);
  };
  const updateDecorations = () => {
    if (!editor) return;
    const model = editor.getModel();
    if (!model) return;
    const text = model.getValue();
    const newDecorations: monacoEditor.IModelDeltaDecoration[] = [];
    let match;
    for (const resourceItem of selectedResourceList.value) {
      const regex = new RegExp(`@${resourceItem.name}`, 'g');
      while ((match = regex.exec(text)) !== null) {
        const startPos = model.getPositionAt(match.index);
        const endPos = model.getPositionAt(match.index + match[0].length);
        const range = new Range(startPos.lineNumber, startPos.column, endPos.lineNumber, endPos.column);
        newDecorations.push({
          range: range,
          options: {
            inlineClassName: `mention-tag mention-tag-${resourceItem.type} range-${range.startLineNumber}-${range.startColumn}-${range.endLineNumber}-${range.endColumn}`,
            // afterContentClassName: `mention-tag-after-content`,
            // beforeContentClassName: `mention-tag-before-content`,
            // before: {
            //   content: '',
            //   cursorStops: editor.InjectedTextCursorStops.Left,
            // },
            // after: {
            //   content: '',
            //   cursorStops: editor.InjectedTextCursorStops.Right,
            // },
            stickiness: monacoEditor.TrackedRangeStickiness.NeverGrowsWhenTypingAtEdges,
          },
        });
      }
    }
    mentionDecorations?.set(newDecorations ?? []);
    setTimeout(() => {
      const mentionTags: NodeListOf<HTMLElement> = editor
        ?.getDomNode()
        ?.querySelectorAll('.mention-tag') as NodeListOf<HTMLElement>;
      mentionTags.forEach(item => {
        let xDom = item.querySelector('.mention-tag-x');
        if (xDom) {
          item.removeChild(xDom);
        }
        xDom = document.createElement('span');
        xDom.className = 'mention-tag-x';
        item.appendChild(xDom);
        xDom.addEventListener('click', handleMentionTagXClick);
        item.removeEventListener('mousedown', handleMentionTagMouseDown);
        item.addEventListener('mousedown', handleMentionTagMouseDown);
        item.setAttribute('contenteditable', 'false');
      });
    }, 20);
  };
  const handleMentionTagXClick = (event: Event) => {
    event.preventDefault();
    event.stopPropagation();
    const classList = Array.from((event.target as HTMLElement)?.closest('.mention-tag')?.classList ?? []);
    const rangeClassName = classList.find(item => item.startsWith('range-'));
    if (rangeClassName) {
      const [, startLineNumber, startColumn, endLineNumber, endColumn] = rangeClassName.split('-');
      const range = new Range(
        parseInt(startLineNumber ?? '0'),
        parseInt(startColumn ?? '0'),
        parseInt(endLineNumber ?? '0'),
        parseInt(endColumn ?? '0'),
      );
      editor.getModel()?.pushEditOperations(
        [],
        [
          {
            range: range,
            text: '',
          },
        ],
        () => null,
      );
      editor.layout();
    }
  };
  const handleMentionTagMouseDown = (event: MouseEvent) => {
    event.preventDefault();
    event.stopPropagation();
  };
  // 获取从 @ 符号到当前光标位置的搜索关键词
  const getSearchKeyword = (): string => {
    if (!editor) return '';
    const position = editor.getPosition();
    if (!position) return '';
    const model = editor.getModel();
    if (!model) return '';

    const lineNumber = position.lineNumber;
    const column = position.column;
    const lineContent = model.getLineContent(lineNumber);

    // 从当前光标位置向前查找 @ 符号
    let atIndex = -1;
    for (let i = column - 2; i >= 0; i--) {
      if (lineContent[i] === suggestionChar.value) {
        atIndex = i;
        break;
      }
      // 如果遇到空格或换行，说明不在 @ 匹配范围内
      if (lineContent[i] === ' ' || lineContent[i] === '\n') {
        break;
      }
    }

    if (atIndex === -1) return '';

    // 提取 @ 后面的文本（不包括 @ 本身）
    const keyword = lineContent.substring(atIndex + 1, column - 1);
    return keyword;
  };
  const handleShowSuggestions = () => {
    if (!editor) return;
    const position = editor.getPosition()!;
    if (!position.lineNumber || !position.column) return;
    const currentChar = editor
      .getModel()
      ?.getValueInRange(new Range(position.lineNumber, position.column - 1, position.lineNumber, position.column));

    // 如果当前字符不是 '/' 或 '@'，且没有关键词，则不显示建议
    if (currentChar !== '/' && currentChar !== '@' && !keyword.value) {
      return;
    }

    // 设置 tippy 位置（仅在 keyword 为空时，即刚输入 '/' 或 '@' 时）
    if (!keyword.value) {
      const offset = editor.getOffsetForColumn(position.lineNumber, position.column);
      const rect = editor.getDomNode()!.getBoundingClientRect();
      tippyRef.value?.setProps({
        getReferenceClientRect: () => {
          const scrollTop = editor.getScrollTop();
          return {
            left: rect.left + offset + 10 - editor.getScrollLeft(),
            top: rect.top + position.lineNumber * aiSlashEditorOptions.lineHeight! - scrollTop + 6,
            width: 0,
            height: 0,
          };
        },
      });
    }
    tippyRef.value?.show();
  };
  const handleTippyHidden = () => {
    keyword.value = '';
  };
  defineExpose({
    get editor(): monacoEditor.IStandaloneCodeEditor {
      return editor;
    },
  });
</script>
<style lang="scss">
  @use 'sass:list';
  @use '../../../styles/variables.scss' as variables;

  .ai-slash-editor-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: fit-content;
    min-height: 88px;

    .ai-slash-editor {
      flex: 1;
      height: fit-content;
      max-height: 400px;
      overflow: hidden;
      border-radius: 8px;

      @each $type, $color in variables.$resourceTypeMap {
        $iconColor: list.nth($color, 3);
        .mention-tag-#{$type} {
          position: relative;
          display: inline-flex;
          align-items: center;
          height: 18px;
          padding: 0 2px 0 6px;
          font-size: 12px;
          color: list.nth($color, 2);
          background: list.nth($color, 1);
          border-radius: 2px;

          &::after {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 18px;
            height: 18px;
            cursor: pointer;
            content: ' ';
            background-color: $iconColor;
            mask-image: url('data:image/svg+xml;charset=utf-8,%3Csvg%20viewBox%3D%220%200%201024%201024%22%20version%3D%221.1%22%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20xmlns%3Axlink%3D%22http%3A%2F%2Fwww.w3.org%2F1999%2Fxlink%22%20width%3D%22200%22%20height%3D%22200%22%3E%3Cpath%20d%3D%22M678.4%20297.6L512%20467.2l-166.4-169.6-48%2048%20169.6%20166.4-169.6%20166.4%2048%2048%20166.4-169.6%20166.4%20169.6%2048-48-169.6-166.4%20169.6-166.4z%22%3E%3C%2Fpath%3E%3C%2Fsvg%3E');
            mask-repeat: no-repeat;
            mask-position: center;
            mask-size: contain;
          }

          .mention-tag-x {
            position: absolute;
            top: 0;
            right: 0;
            z-index: 1;
            width: 18px;
            height: 18px;
            cursor: pointer;
          }

          &:hover {
            color: list.nth($color, 5);
            background: list.nth($color, 4);

            &::after {
              background-color: list.nth($color, 6);
            }
          }
        }
      }
    }

    &_disabled {
      cursor: not-allowed;

      .ai-slash-editor {
        margin: 6px;
        pointer-events: none;
        background: #fff;
        border-radius: 2px;

        .cursor {
          display: none !important;
        }
      }
    }
  }

  .ai-slash-suggestions {
    position: fixed;
    z-index: v-bind(EDITOR_MENU_Z_INDEX);
    display: flex;
    flex-direction: column;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    box-shadow: 0 0 8px 0 #0000001a;

    .ai-slash-suggestion-item {
      padding: 4px 8px;
      border-radius: 4px;
    }
  }

  .tippy-box[data-theme~='ai-slash-editor-theme'] {
    box-shadow: none !important;

    .tippy-content {
      padding: 0 !important;
    }
  }
</style>
