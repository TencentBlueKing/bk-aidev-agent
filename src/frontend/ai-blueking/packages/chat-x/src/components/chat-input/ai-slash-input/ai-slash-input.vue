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
              <span
                v-else-if="item.type === 'tag'"
                :class="`mention-tag-${item.data.type}`"
                contenteditable="false"
                :data-tag-type="item.data.type"
              >
                {{ item.data.label }}
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
      :offset="[0, 0]"
      placement="right-start"
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
  import { customRef, onMounted, onUnmounted, shallowRef, useTemplateRef, watch, watchEffect } from 'vue';

  import { Tippy, useTippy } from 'vue-tippy';

  import { EDITOR_MENU_Z_INDEX, isEn } from '../../../common';
  import { useCommandSelection } from '../../../composables';
  import { type KeyboardPayload, createEditor, docToString, ReplaceAll, stringToDoc } from '../../../edix';
  import { RemoveIcon } from '../../../icons';
  import AiPromptList from './ai-prompt-list/ai-prompt-list.vue';
  import AiSkillList from './ai-skill-list/ai-skill-list.vue';
  import AiSlashMenu from './ai-slash-menu/ai-slash-menu.vue';
  import { DeleteTag, InsertTag, InsertText } from './command';
  import { tagSchema } from './constants';

  import type { IAiSlashMenuItem, ISkillListItem } from '../../../types/editor';
  import type { MentionState, TagSchema } from '../../../types/input';

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

  const menuType = shallowRef<'' | 'prompt' | 'skill' | 'slash'>('slash');
  const keyword = shallowRef<string>('');
  const filteredResourceList = shallowRef<IAiSlashMenuItem[]>([]);
  const filteredSkills = shallowRef<ISkillListItem[]>([]);
  const filteredPrompts = shallowRef<string[]>([]);

  let editor: ReturnType<typeof createEditor>;
  /* 清理编辑器 */
  let cleanup: () => void;
  const getBody = () => document.body;

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
  /* 显示提示 */
  const handleShowSuggestions = () => {
    setTimeout(() => {
      const mentionState = getMentionState();
      keyword.value = mentionState.query || '';
      // 设置 tippy 位置（仅在 keyword 为空时，即刚输入 '/' 或 '@' 时）
      if (mentionState.isActive) {
        tippyRef.value?.setProps({
          getReferenceClientRect: () => {
            return {
              left: mentionState.coordinates?.left || 0,
              top: mentionState.coordinates?.top || 0,
              width: 0,
              height: 0,
            };
          },
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
    if (event.key === '@') {
      menuType.value = 'slash';
      handleShowSuggestions();
    }
    if (event.key === '/') {
      menuType.value = 'skill';
      handleShowSuggestions();
    }
    if (event.key === '\\') {
      menuType.value = 'prompt';
      handleShowSuggestions();
    }
  };
  const handleTippyHidden = () => {
    keyword.value = '';
  };
  const getMentionState = (): MentionState => {
    const defaultState: MentionState = {
      isActive: false,
      query: '',
      rect: null,
      coordinates: null,
    };

    const selection = window.getSelection();
    if (!selection || selection.rangeCount === 0) return defaultState;

    const range = selection.getRangeAt(0);
    const node = range.startContainer;
    const offset = range.startOffset;
    if (node.nodeType !== Node.TEXT_NODE) return defaultState;
    const text = node.textContent || '';
    const textBeforeCursor = text.slice(0, offset);

    // 2. 正则匹配：查找光标前的最后一个触发字符
    const triggerChar = menuType.value === 'slash' ? '@' : menuType.value === 'skill' ? '/' : '\\';
    const escapedChar = triggerChar === '\\' ? '\\\\' : triggerChar;
    const regex = new RegExp(`(${escapedChar}[^\\s]*)$`);
    const match = textBeforeCursor.match(regex);

    if (!match) return defaultState;

    // match[1] 是捕获到的 "@xxx"
    const matchText = match[1];
    const query = matchText?.slice(1); // 去掉 @，得到搜索词

    // 3. 计算 "@" 符号在文本节点中的精确索引
    // match.index 是匹配开始的位置（可能包含前导空格），我们需要调整到 @ 的位置
    const matchIndex = match.index! + match[0].indexOf(triggerChar);

    try {
      const rangeOfAt = document.createRange();
      rangeOfAt.setStart(node, matchIndex);
      rangeOfAt.setEnd(node, matchIndex + 1);

      // 5. 获取 "@" 的物理坐标
      const rect = rangeOfAt.getBoundingClientRect();

      return {
        isActive: true,
        query: query,
        rect: rect,
        coordinates: {
          top: rect.bottom,
          left: rect.left,
          height: rect.height,
        },
      };
    } catch {
      return defaultState;
    }
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
    editor.command(DeleteTag, [line, column - keyword.value.length - 1], [line, column]);
    editor.command(InsertTag, [line, column], tag);
    editor.command(InsertText, [line, column + keyword.value.length + 1 + 1], ' ');
    tippyRef.value?.hide();
    focusToEnd();
  };
  const focusToEnd = () => {
    setTimeout(() => {
      const selection = window.getSelection();
      const range = document.createRange();
      if (editorRef.value && selection) {
        range.selectNodeContents(editorRef.value);
        range.collapse(false);
        selection.removeAllRanges();
        selection.addRange(range);
      }
    }, 100);
  };
  const insertPromptAtCursor = (prompt: string) => {
    editor.command(ReplaceAll, prompt);
    focusToEnd();
  };
  const insertSkillAtCursor = (skill: ISkillListItem) => {
    editor.command(ReplaceAll, `/${skill.skill_code} `);
    tippyRef.value?.hide();
    focusToEnd();
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
    if (!keyword.value) {
      filteredResourceList.value = resourceList;
      filteredSkills.value = props.skills;
      filteredPrompts.value = props.prompts;
    } else {
      filteredResourceList.value = resourceList.filter(item =>
        item.name.toLowerCase().includes(keyword.value.toLowerCase()),
      );
      filteredSkills.value = props.skills.filter(
        skill =>
          skill.skill_name.toLowerCase().includes(keyword.value.toLowerCase()) ||
          skill.skill_code.toLowerCase().includes(keyword.value.toLowerCase()),
      );
      filteredPrompts.value = props.prompts.filter(prompt =>
        prompt.toLowerCase().includes(keyword.value.toLowerCase()),
      );
    }
    if (!filteredResourceList.value.length && !filteredSkills.value.length && !filteredPrompts.value.length) {
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
  const handleTippyShow = (): false | void => {
    if (menuType.value === 'slash') {
      return filteredResourceList.value.length < 1 ? false : undefined;
    }
    if (menuType.value === 'skill') {
      return filteredSkills.value.length < 1 ? false : undefined;
    }
    return filteredPrompts.value.length < 1 ? false : undefined;
  };
  onMounted(() => {
    initEditor();
    editorRef.value?.addEventListener('paste', handlePaste);
  });
  onUnmounted(() => {
    editor.command(ReplaceAll, '');
    cleanup?.();
    editorRef.value?.removeEventListener('paste', handlePaste);
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
      $iconColor: list.nth($color, 3);
      .mention-tag-#{$type} {
        position: relative;
        display: inline-flex;
        align-items: center;
        height: 18px;
        padding: 0 2px 0 6px;
        font-size: var(--ai-font-size, 12px);
        color: list.nth($color, 2);
        background: list.nth($color, 1);
        border-radius: 2px;

        .mention-tag-remove-icon {
          position: absolute;
          top: -7px;
          right: -7px;
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
      width: 100%;
      min-height: 100%;
      padding: var(--ai-spacing-comfortable, 8px);
      font-size: var(--ai-font-size, 12px);
      line-height: var(--ai-line-height-compact, 20px);
      color: #4d4f56;
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

  .tippy-box[data-theme~='ai-slash-editor-theme'] {
    box-shadow: none !important;

    &[data-theme~='light'] {
      background-color: white;
    }

    .tippy-content {
      padding: 0 !important;
    }
  }
</style>
