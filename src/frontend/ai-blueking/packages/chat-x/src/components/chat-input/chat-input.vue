<template>
  <div
    ref="containerRef"
    class="ai-chat-input-container"
    :style="{ '--chat-z-index': CHAT_Z_INDEX, '--chat-menu-z-index': EDITOR_MENU_Z_INDEX }"
  >
    <slot name="top" />
    <slot name="interrupt" />
    <div class="chat-input-wrapper">
      <InputMenuPanel
        v-if="isMenuVisible"
        class="chat-input-menu"
        :flat-items="flatItems"
        :groups="menuGroups"
        @close="handleCloseMenu"
        @select="handleSelectMenuItem"
        @toggle-group="handleToggleGroup"
      />
      <div
        class="chat-input"
        :class="{ 'is-dragover': isDragOver }"
        :style="{ maxHeight: maxHeight + 'px' }"
        @dragenter="handleDragEnter"
        @dragleave="handleDragLeave"
        @dragover="handleDragOver"
        @drop="handleDrop"
      >
        <slot name="input-header">
          <CiteContent
            v-if="citeModel"
            class="chat-input-cite"
            :content="citeModel"
            @close="handleCloseCite"
          />
        </slot>
        <slot
          name="files"
          v-bind="{ files: uploadFiles }"
        >
          <div
            v-if="uploadFiles.length"
            ref="filesRef"
            class="chat-input-files"
          >
            <FileContent
              :files="uploadFiles"
              @delete-file="handleDeleteFile"
            />
          </div>
        </slot>
        <AiSlashInput
          ref="aiSlashInputRef"
          :model-value="modelValue"
          :placeholder="resolvedPlaceholder"
          @keydown="handleKeyDown"
          @menu-change="handleMenuChange"
          @update:model-value="handleUpdateModelValue"
          @upload="handleUpload"
        />
        <InputAttachment
          :message-state="messageState"
          :send-disabled-tip="effectiveSendDisabledTip"
          :tippy-options="tippyOptions"
          @send-message="handleSendMessage"
          @stop-sending="handleStopSending"
        >
          <template #default>
            <input
              ref="fileInputRef"
              class="chat-input-file-input"
              multiple
              type="file"
              @change="handleFileInputChange"
            />
            <AddMenuBtn
              v-if="hasAddMenu"
              :active="menuTrigger === 'plus'"
              :tippy-options="tippyOptions"
              @toggle="handleToggleAddMenu"
            />
            <span
              v-if="hasAddMenu && (shortcuts?.length || selectedShortcut)"
              class="ai-divider"
            />
            <slot name="attachment">
              <ShortcutBtns
                v-if="shortcuts && !selectedShortcut"
                :shortcuts="shortcuts"
                @select-shortcut="handleSelectShortcut"
              />
              <ShortcutBtn
                v-if="selectedShortcut"
                class="selected-shortcut-btn"
                :shortcut="selectedShortcut"
              >
                <template #append>
                  <CloseIcon @click="handleDeleteShortcut" />
                </template>
              </ShortcutBtn>
            </slot>
          </template>
          <template #before-send>
            <slot
              name="model-selector"
              v-bind="{ models, selectedModel }"
            >
              <ModelSelector
                v-if="models?.length"
                v-model="selectedModel"
                class="chat-input-model-selector"
                :models="models"
                :tippy-options="tippyOptions"
                @change="handleModelChange"
              />
            </slot>
          </template>
          <template #send-icon>
            <slot name="send-icon" />
          </template>
        </InputAttachment>
      </div>
    </div>
  </div>
</template>
<script setup lang="ts">
  import { computed, onUnmounted, reactive, ref as deepRef, shallowRef, useTemplateRef, watch, watchPostEffect } from 'vue';

  import { Message } from 'bkui-vue';

  import {
    type Interrupt,
    type InterruptResume,
    type UserMessage,
    MessageContentType,
    MessageStatus,
  } from '../../ag-ui/types';
  import { CHAT_Z_INDEX, EDITOR_MENU_Z_INDEX, isEn, MAX_UPLOAD_FILE_SIZE, MAX_UPLOAD_FILES } from '../../common';
  import { type KeyboardPayload } from '../../edix';
  import { CloseIcon } from '../../icons';
  import { t } from '../../lang/lang';
  import {
    type AITippyProps,
    type IInputMenuItem,
    type MenuTrigger,
    type Shortcut,
    type TagSchema,
    type UploadFile,
    UploadStatus,
  } from '../../types';
  import { formatUploadNotAddedMessage, getFileIdentity, getUploadFileName, getUploadFileSize } from '../../utils';
  import AddMenuBtn from '../ai-buttons/add-menu-btn/add-menu-btn.vue';
  import ShortcutBtn from '../ai-shortcut/shortcut-btn/shortcut-btn.vue';
  import ShortcutBtns from '../ai-shortcut/shortcut-btns/shortcut-btns.vue';
  import CiteContent from '../chat-content/cite-content/cite-content.vue';
  import FileContent from '../chat-content/file-content/file-content.vue';
  import AiSlashInput from './ai-slash-input/ai-slash-input.vue';
  import { tagSchemaToMessageString } from './ai-slash-input/constants';
  import { buildDefaultPlaceholder } from './build-default-placeholder';
  import InputAttachment from './input-attachment/input-attachment.vue';
  import { DEFAULT_GROUP_ITEM_LIMIT, InputMenuPanel, useInputMenu } from './input-menu';
  import { ModelSelector } from './model-selector';

  import type { MenuGroupKey } from './input-menu';
  import type { IModelOption } from './model-selector';

  const aiSlashInputRef = useTemplateRef<InstanceType<typeof AiSlashInput>>('aiSlashInputRef');
  const containerRef = useTemplateRef<HTMLDivElement>('containerRef');
  const filesRef = useTemplateRef<HTMLDivElement>('filesRef');
  const fileInputRef = useTemplateRef<HTMLInputElement>('fileInputRef');
  const citeModel = defineModel<string>('cite', {
    required: false,
    default: '',
  });
  // 当前选中的模型（值为 llm_name，v-model:selectedModel）
  const selectedModel = defineModel<string>('selectedModel', {
    required: false,
  });
  const maxHeight = shallowRef(280);
  export type ChatInputUploadResult = {
    download_url?: string;
    error?: string;
    id?: string;
    status?: 'failed' | 'success';
  };
  export type ChatInputEmits = {
    (e: 'selectShortcut', shortcut: Shortcut): void;
    (e: 'deleteShortcut'): void;
    (e: 'update:modelValue', value: string | TagSchema, selectedResourceList: IInputMenuItem[]): void;
    (e: 'modelChange', model: IModelOption): void;
  };
  export type ChatInputProps = {
    defaultUploadFiles?: UploadFile[];
    inputMaxHeight?: number;
    /** 菜单每个分组默认展示的条数，超出折叠为「更多 +N」 */
    menuGroupItemLimit?: number;
    /** 统一的菜单数据源：`@` `/` `\` 与左下角 + 号共用，按 type 分发到不同触发方式 */
    menuSources?: IInputMenuItem[];
    messageStatus?: MessageStatus;
    models?: IModelOption[]; // 可选模型列表，传入后在发送按钮左侧展示模型选择器
    modelValue: string | TagSchema;
    onSendMessage?: (
      message: UserMessage['content'],
      docSchema: TagSchema,
      options?: { interrupt?: Interrupt; payload?: InterruptResume },
    ) => Promise<void>;
    onStopSending?: () => Promise<void>;
    onUpload?: (files: File[]) => Promise<ChatInputUploadResult | ChatInputUploadResult[]>;
    placeholder?: string;
    sendDisabledTip?: string;
    shortcutId?: string;
    shortcuts?: Shortcut[];
    supportUpload?: boolean; // 是否支持上传文件 默认是true
    tippyOptions?: AITippyProps; // tips配置
  };
  const props = withDefaults(defineProps<ChatInputProps>(), {
    menuSources: () => [],
    menuGroupItemLimit: DEFAULT_GROUP_ITEM_LIMIT,
    inputMaxHeight: 280,
    supportUpload: true,
  });
  const emit = defineEmits<ChatInputEmits>();
  /** 数据源里存在的菜单类型，用于决定 placeholder 展示哪几行提示 */
  const sourceTypes = computed(() => new Set(props.menuSources.map(item => item.type)));
  const resolvedPlaceholder = computed(() => {
    if (props.placeholder !== undefined) {
      return props.placeholder;
    }
    return buildDefaultPlaceholder({
      isEn,
      hasSlashMenu: ['skill', 'mcp', 'tool'].some(type => sourceTypes.value.has(type as IInputMenuItem['type'])),
      hasAtMenu: ['knowledgebase', 'doc', 'artifact'].some(type =>
        sourceTypes.value.has(type as IInputMenuItem['type']),
      ),
      hasPromptMenu: sourceTypes.value.has('prompt'),
    });
  });
  const uploadFiles = deepRef<Partial<UploadFile>[]>(props.defaultUploadFiles || []);
  const selectedShortcut = computed(() => {
    return props.shortcuts?.find(shortcut => shortcut.id === props.shortcutId);
  });

  // ---------------- 输入框菜单（@ / \ 与左下角 + 号共用同一个面板） ----------------
  const menuTrigger = shallowRef<MenuTrigger | null>(null);
  const menuKeyword = shallowRef('');
  /** 已插入编辑器的标签，避免在菜单里重复出现 */
  const insertedTagKeys = computed(() => {
    if (typeof props.modelValue === 'string') {
      return new Set<string>();
    }
    return new Set(
      props.modelValue
        .flat()
        .filter(node => node.type === 'tag')
        .map(node => `${node.data.type}:${node.data.value}`),
    );
  });
  const availableSources = computed<IInputMenuItem[]>(() => {
    const list = props.menuSources.filter(item => !insertedTagKeys.value.has(`${item.type}:${item.id}`));
    // 「文件」是组件内置的上传入口，只在 + 号聚合菜单的「添加」分组里出现
    return props.supportUpload ? [{ id: '__built_in_file__', type: 'file', name: t('文件') }, ...list] : list;
  });
  const {
    groups: menuGroups,
    flatItems,
    hasContent,
    toggleGroup,
  } = useInputMenu({
    sources: availableSources,
    keyword: menuKeyword,
    trigger: menuTrigger,
    groupItemLimit: computed(() => props.menuGroupItemLimit),
  });
  const isMenuVisible = computed(() => Boolean(menuTrigger.value) && hasContent.value);
  /** 既不能上传也没有任何可选项时不展示 + 号 */
  const hasAddMenu = computed(() => props.supportUpload || props.menuSources.length > 0);

  const handleMenuChange = (payload: { keyword: string; trigger: MenuTrigger | null }) => {
    menuTrigger.value = payload.trigger;
    menuKeyword.value = payload.keyword;
  };
  const handleCloseMenu = () => {
    aiSlashInputRef.value?.closeMenu?.();
  };
  const handleToggleAddMenu = () => {
    if (menuTrigger.value === 'plus') {
      handleCloseMenu();
      return;
    }
    aiSlashInputRef.value?.openPlusMenu?.();
  };
  const handleToggleGroup = (key: string) => {
    toggleGroup(key as MenuGroupKey);
  };
  const handleSelectMenuItem = (item: IInputMenuItem) => {
    if (item.type === 'file') {
      // 与插入标签保持一致：先吃掉用于过滤的输入文本，再唤起系统文件选择器
      aiSlashInputRef.value?.consumeTriggerText?.();
      handleCloseMenu();
      fileInputRef.value?.click();
      return;
    }
    if (item.type === 'prompt') {
      // Prompt 选中后整体替换输入框内容
      aiSlashInputRef.value?.replaceAll?.(item.content ?? item.name);
      return;
    }
    aiSlashInputRef.value?.insertMenuItem?.(item);
  };
  // 输入框文本：modelValue 可能是普通字符串（如编辑态回填）或编辑器 TagSchema
  const inputText = computed(() =>
    typeof props.modelValue === 'string' ? props.modelValue : tagSchemaToMessageString(props.modelValue),
  );
  const messageState = computed(() => {
    if (
      props.messageStatus &&
      [MessageStatus.Pending, MessageStatus.Streaming, MessageStatus.Fetching].includes(props.messageStatus)
    ) {
      return props.messageStatus;
    }
    // 已有附件即可发送，纯附件消息无需再输入文字
    if (uploadFiles.value.length > 0) {
      return props.messageStatus;
    }
    if (!inputText.value.trim()) {
      return MessageStatus.Disabled;
    }
    return props.messageStatus;
  });
  const isUploading = computed(() => uploadFiles.value.some(file => file.status === UploadStatus.Pending));
  const hasUploadError = computed(() => uploadFiles.value.some(file => file.status === UploadStatus.Error));
  const effectiveSendDisabledTip = computed(() => {
    if (props.sendDisabledTip) {
      return props.sendDisabledTip;
    }
    if (isUploading.value) {
      return t('文件上传中，请稍候');
    }
    if (hasUploadError.value) {
      return t('存在上传失败的文件，请删除后重试');
    }
    return undefined;
  });

  watchPostEffect(() => {
    const defaultHeight = props.inputMaxHeight || 280;
    if (uploadFiles.value.length < 1 || !filesRef.value) {
      maxHeight.value = defaultHeight;
      return;
    }
    const filesHeight = filesRef.value?.clientHeight || 0;
    maxHeight.value = defaultHeight + filesHeight;
  });
  const handleSendMessage = async () => {
    try {
      if (effectiveSendDisabledTip.value) {
        return;
      }
      aiSlashInputRef.value?.cleanup?.();
      let content: undefined | UserMessage['content'] = undefined;

      // 如果没有上传文件，则使用输入框的值
      if (!uploadFiles.value?.length) {
        content = inputText.value;
      } else {
        // 如果上传了文件，则使用上传的文件
        // 取值统一走 helper：编辑态回填的附件只有 BinaryInputContent（无 File），不能只读 file.*
        content = uploadFiles.value?.slice().map(file => ({
          type: MessageContentType.Binary,
          id: file.id,
          url: file.url,
          mimeType: file.mimeType || file.file?.type || '',
          filename: getUploadFileName(file),
          size: getUploadFileSize(file),
        }));
        // 输入框有实际文字时才追加文本内容，纯附件消息不带空文本段
        if (inputText.value.trim()) {
          content.push({
            type: MessageContentType.Text,
            text: inputText.value,
          });
        }
      }
      props.onSendMessage?.(content, props.modelValue as TagSchema);
      uploadFiles.value = [];
    } catch (error) {
      console.error(error);
    }
  };
  const handleKeyDown = (event: KeyboardEvent & KeyboardPayload) => {
    if (event.key === 'Enter' || event.key === 'NumpadEnter') {
      if (event.shiftKey) {
        return;
      }
      // 菜单展开时 Enter 用于选中条目，不触发发送
      if (isMenuVisible.value) {
        return;
      }
      if (messageState.value === MessageStatus.Disabled) {
        return;
      }
      if (effectiveSendDisabledTip.value) {
        return;
      }
      if (
        messageState.value === MessageStatus.Fetching ||
        messageState.value === MessageStatus.Streaming ||
        messageState.value === MessageStatus.Pending
      ) {
        return;
      }
      handleSendMessage();
    }
  };
  const handleStopSending = async () => {
    try {
      props.onStopSending?.();
    } catch (error) {
      console.error(error);
    }
  };
  const handleCloseCite = () => {
    citeModel.value = '';
  };
  const handleSelectShortcut = (shortcut: Shortcut) => {
    emit('selectShortcut', shortcut);
  };
  const handleDeleteShortcut = () => {
    emit('deleteShortcut');
  };
  const handleModelChange = (model: IModelOption) => {
    emit('modelChange', model);
  };
  const maxUploadMb = (MAX_UPLOAD_FILE_SIZE / (1024 * 1024)).toFixed(1);
  const applyUploadResult = (fileItem: Partial<UploadFile>, res?: ChatInputUploadResult) => {
    const failed = res?.status === 'failed';
    const succeeded = !failed && (!!res?.id || !!res?.download_url || res?.status === 'success');
    if (succeeded) {
      fileItem.id = res.id;
      fileItem.url = res.download_url;
      fileItem.status = UploadStatus.Success;
      return;
    }
    fileItem.status = UploadStatus.Error;
  };
  const handleUpload = async (files: File[]) => {
    if (!props.supportUpload) {
      return;
    }
    const existingKeys = new Set(uploadFiles.value.map(item => (item.file ? getFileIdentity(item.file) : '')));
    const acceptedItems: Partial<UploadFile>[] = [];
    let rejectedCount = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      const key = getFileIdentity(file);
      if (existingKeys.has(key)) {
        continue;
      }
      if (uploadFiles.value.length >= MAX_UPLOAD_FILES) {
        rejectedCount += files.length - i;
        break;
      }
      if (file.size <= 0 || file.size >= MAX_UPLOAD_FILE_SIZE) {
        rejectedCount += 1;
        continue;
      }
      existingKeys.add(key);
      const fileItem = reactive<Partial<UploadFile>>({
        file,
        mimeType: file.type,
        status: UploadStatus.Pending,
      });
      uploadFiles.value.push(fileItem);
      acceptedItems.push(fileItem);
    }
    if (rejectedCount > 0) {
      Message({
        message: formatUploadNotAddedMessage(rejectedCount, maxUploadMb, isEn),
        theme: 'error',
      });
    }
    // 设计稿标注：文件加入列表后光标自动回到输入区，便于继续输入
    if (acceptedItems.length > 0) {
      focus();
      const acceptedFiles = acceptedItems.map(item => item.file).filter((file): file is File => !!file);
      const request = props.onUpload?.(acceptedFiles);
      if (!request) {
        return;
      }
      request
        .then(res => {
          const results = Array.isArray(res) ? res : [res];
          acceptedItems.forEach((fileItem, index) => {
            applyUploadResult(fileItem, results[index]);
          });
        })
        .catch(() => {
          acceptedItems.forEach(fileItem => {
            fileItem.status = UploadStatus.Error;
          });
        });
    }
  };

  // 拖拽上传：仅响应从系统拖入的文件，避免编辑器内部 tag 拖拽误触发
  const isDragOver = shallowRef(false);
  // 子元素间移动会连续触发 enter/leave，用计数抵消，避免高亮闪烁
  let dragDepth = 0;
  const isFileDragEvent = (event: DragEvent) => !!event.dataTransfer?.types?.includes('Files');
  const canAcceptDrag = (event: DragEvent) => props.supportUpload && isFileDragEvent(event);
  const handleDragEnter = (event: DragEvent) => {
    if (!canAcceptDrag(event)) return;
    dragDepth += 1;
    isDragOver.value = true;
  };
  const handleDragOver = (event: DragEvent) => {
    if (!canAcceptDrag(event)) return;
    // 不阻止默认行为浏览器会直接打开被拖入的文件
    event.preventDefault();
    if (event.dataTransfer) {
      event.dataTransfer.dropEffect = 'copy';
    }
  };
  const handleDragLeave = (event: DragEvent) => {
    if (!canAcceptDrag(event)) return;
    dragDepth = Math.max(dragDepth - 1, 0);
    if (dragDepth === 0) {
      isDragOver.value = false;
    }
  };
  const handleDrop = (event: DragEvent) => {
    if (!canAcceptDrag(event)) return;
    event.preventDefault();
    dragDepth = 0;
    isDragOver.value = false;
    const files = Array.from(event.dataTransfer?.files ?? []);
    if (files.length) {
      handleUpload(files);
    }
  };
  const handleDeleteFile = (file: Partial<UploadFile>) => {
    uploadFiles.value = uploadFiles.value.filter(item => {
      if (item.file) {
        return item.file !== file.file;
      }
      if (item.url) {
        return item.url !== file.url;
      }
      if (item.filename) {
        return item.filename !== file.filename;
      }
      return true;
    });
  };
  /** 把文档里的标签还原成菜单选项，作为 update:modelValue 的第二个参数交给业务方 */
  const handleUpdateModelValue = (value: TagSchema) => {
    const selectedResourceList = value
      .flat()
      .filter(node => node.type === 'tag')
      .map(node => props.menuSources.find(item => item.id === node.data.value && item.type === node.data.type))
      .filter((item): item is IInputMenuItem => Boolean(item));
    emit('update:modelValue', value, selectedResourceList);
  };
  const handleFileInputChange = (event: Event) => {
    const target = event.target as HTMLInputElement;
    const files = Array.from(target.files ?? []);
    if (files.length) {
      // 大小与数量校验统一在 handleUpload 中处理
      handleUpload(files);
    }
    target.value = '';
  };
  // 点击输入区之外时收起菜单；用 mousedown 以便在编辑器失焦之前处理
  const handleDocumentMouseDown = (event: MouseEvent) => {
    if (!containerRef.value?.contains(event.target as Node)) {
      handleCloseMenu();
    }
  };
  watch(isMenuVisible, visible => {
    if (visible) {
      document.addEventListener('mousedown', handleDocumentMouseDown, true);
      return;
    }
    document.removeEventListener('mousedown', handleDocumentMouseDown, true);
  });
  onUnmounted(() => {
    document.removeEventListener('mousedown', handleDocumentMouseDown, true);
  });
  /**
   * 聚焦输入框
   */
  const focus = () => {
    aiSlashInputRef.value?.focus?.();
  };
  /** 供外部（文件产物面板等）把资源以标签形式追加进输入框 */
  const insertMention = (item: IInputMenuItem) => {
    aiSlashInputRef.value?.appendMention?.(item);
  };
  defineExpose({
    focus,
    insertMention,
    triggerSendMessage: handleSendMessage,
  });
</script>
<style lang="scss">
  @use '../../styles/variables.scss' as variables;
  @use '../../styles/border.scss' as border;

  .ai-chat-input-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    padding: 0 16px 16px;

    // 菜单需要溢出输入框展示，而 .chat-input 自身要 overflow: hidden，因此额外包一层定位容器
    .chat-input-wrapper {
      position: relative;
      display: flex;
      flex-direction: column;
      width: 100%;
      min-width: variables.$chat-input-min-width;
      max-width: variables.$chat-input-max-width;
    }

    // 设计稿：菜单固定在输入框正上方并与输入框等宽，不跟随光标
    .chat-input-menu {
      position: absolute;
      bottom: calc(100% + 8px);
      left: 0;
      z-index: var(--chat-menu-z-index);
    }

    .chat-input-file-input {
      display: none;
    }

    .chat-input {
      position: relative;
      display: flex;
      flex-direction: column;
      width: 100%;
      min-height: 110px;
      max-height: 280px; // 与 inputMaxHeight 默认一致；有文件时由 inline style 叠加预览区高度
      padding-bottom: var(--ai-spacing-comfortable, 8px);
      overflow: hidden; // 触顶后由内部 ai-slash-input 滚动
      background: #fff;
      border: 1px solid #dcdee5; // 未激活：灰色描边
      border-radius: 16px;

      &::before {
        z-index: var(--chat-z-index);
        opacity: 0;
        transition: opacity 0.15s ease;

        @include border.linear-gradient-border(180deg, #6cbaff, #3a84ff);
      }

      // 激活（编辑区 / 内部控件聚焦）与拖拽悬停时切换为蓝色渐变描边
      &:focus-within,
      &.is-dragover {
        border-color: transparent;

        &::before {
          opacity: 1;
        }
      }

      // 拖拽悬停额外叠加浅蓝底提示可释放（设计稿未给拖拽态，取背景蓝 #e1ecff 的更浅一档）
      &.is-dragover {
        background: #f0f5ff;
      }

      .chat-input-cite {
        margin: 8px 8px 0;
        background: #f0f1f5;

        .ai-cite-content-text {
          color: #4d4f56;
        }
      }

      .chat-input-files {
        display: flex;
        width: 100%;
        padding: 8px 8px 0;
      }

      // 模型选择器靠右与发送按钮成组：吸收左侧剩余空间，把自身与发送按钮一起推到右端
      .chat-input-model-selector {
        margin-left: auto;
      }

      // 已选快捷指令 tag：默认态与 bkui Tag 一致，hover 使用 shortcut 语义色
      .selected-shortcut-btn {
        height: 32px;
        padding: 0 10px;
        color: #3a84ff;
        background: #e1ecff;
        transition:
          background-color 0.2s,
          color 0.2s;

        .ai-common-icon {
          color: #3a84ff;
        }

        &:hover {
          color: #1768ef;
          background: #cddffe;

          .ai-common-icon {
            color: #3a84ff;
          }
        }
      }

      .ai-shortcut-btns-item {
        height: 32px;
        padding: 0 8px;
        border-radius: 8px;
      }
    }
  }
</style>
