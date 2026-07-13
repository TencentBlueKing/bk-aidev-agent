<template>
  <span class="ai-md-image-wrapper">
    <!-- 加载中、URL 不完整、或 URL 不稳定时显示 Loading -->
    <span
      v-if="showLoading"
      class="md-image-loading"
    >
      <Loading
        mode="spin"
        size="mini"
        theme="primary"
      />
      <span class="md-image-loading-text">{{ t('图片加载中...') }}</span>
    </span>
    <!-- 仅在 URL 稳定后才显示错误信息 -->
    <span
      v-else-if="showError"
      class="md-image-error"
    >
      <span class="md-image-error-icon">⚠️</span>
      <span class="md-image-error-text">{{ alt || t('图片加载失败') }}</span>
    </span>
    <!-- 加载成功显示图片 -->
    <img
      v-else
      :alt="alt"
      class="md-image"
      loading="lazy"
      :src="src"
    />
  </span>
</template>

<script setup lang="ts">
  import { computed, shallowRef, watch } from 'vue';

  import { Loading } from 'bkui-vue';
  import debounce from 'lodash/debounce';
  import throttle from 'lodash/throttle';

  import { t } from '../../../lang/lang';

  // 全局缓存：记录已成功加载的图片 URL
  // 使用 Set 存储，避免组件重新创建时重复加载
  const loadedImageCache = new Set<string>();

  const props = defineProps<{
    alt?: string;
    src: string;
  }>();

  // 检查当前 URL 是否已在缓存中（已成功加载过）
  const isCached = computed(() => loadedImageCache.has(props.src));

  // 如果已缓存，初始状态就是已加载完成
  const isLoading = shallowRef(!isCached.value);
  const hasError = shallowRef(false);
  // URL 是否已稳定（一段时间没有变化）
  const isUrlStable = shallowRef(isCached.value);
  // 缓存上一次加载的 URL，避免重复加载
  let lastLoadedUrl = isCached.value ? props.src : '';

  // 计算是否显示 loading（URL 不稳定时，即使有错误也显示 loading）
  const showLoading = computed(() => {
    // 如果已缓存（之前成功加载过），直接显示图片
    if (isCached.value) return false;
    // URL 无效时显示 loading
    if (!isValidUrl.value) return true;
    // 正在加载时显示 loading
    if (isLoading.value) return true;
    // URL 不稳定且有错误时，继续显示 loading（可能 URL 还在变化）
    if (!isUrlStable.value && hasError.value) return true;
    return false;
  });

  // 计算是否显示错误（仅在 URL 稳定后才显示）
  const showError = computed(() => {
    return isUrlStable.value && hasError.value && !isLoading.value;
  });

  // 标记 URL 已稳定（debounce，500ms 没有变化则认为稳定）
  const markUrlStable = debounce(() => {
    isUrlStable.value = true;
  }, 500);

  // 检测 URL 是否可能是完整的
  // 不完整的 URL 特征：
  // 1. 以 # 结尾（语法补全使用的占位符）
  // 2. URL 太短或明显被截断
  // 3. 没有有效的协议或路径
  const isValidUrl = computed(() => {
    const url = props.src?.trim() || '';

    // 空 URL 或只有占位符
    if (!url || url === '#' || url === '#)') {
      return false;
    }

    // 以 # 结尾说明是补全的占位符
    if (url.endsWith('#') || url.endsWith('#)')) {
      return false;
    }

    // 检查是否有基本的 URL 结构
    // 支持：http://, https://, //, data:, blob:, 相对路径等
    const hasProtocol = /^(https?:\/\/|\/\/|data:|blob:)/i.test(url);
    const isRelativePath = /^[./]/.test(url) || /\.(png|jpg|jpeg|gif|webp|svg|bmp|ico)(\?.*)?$/i.test(url);

    if (!hasProtocol && !isRelativePath) {
      // 可能是正在输入的 URL 片段
      return false;
    }

    // 检查 http(s):// 开头的 URL 是否至少有域名部分
    if (/^https?:\/\//i.test(url)) {
      const afterProtocol = url.replace(/^https?:\/\//i, '');
      // 至少应该有一个点（域名）或者 localhost
      if (!afterProtocol.includes('.') && !afterProtocol.startsWith('localhost')) {
        return false;
      }
    }

    return true;
  });

  // 预加载图片（节流处理）
  const preloadImage = throttle(
    (url: string) => {
      if (!isValidUrl.value) {
        isLoading.value = true;
        hasError.value = false;
        return;
      }

      // 如果 URL 已在全局缓存中（之前成功加载过），直接返回
      if (loadedImageCache.has(url)) {
        lastLoadedUrl = url;
        isLoading.value = false;
        hasError.value = false;
        return;
      }

      // 如果 URL 没有变化，直接返回
      if (url === lastLoadedUrl) {
        return;
      }

      isLoading.value = true;
      hasError.value = false;

      const img = new Image();

      img.onload = () => {
        // 确保 URL 没有变化
        if (props.src === url) {
          // 加入全局缓存
          loadedImageCache.add(url);
          lastLoadedUrl = url;
          isLoading.value = false;
          hasError.value = false;
        }
      };

      img.onerror = () => {
        // 确保 URL 没有变化
        if (props.src === url) {
          isLoading.value = false;
          hasError.value = true;
        }
      };

      img.src = url;
    },
    100,
    {
      leading: true,
      trailing: true,
    },
  );

  // 监听 URL 变化
  watch(
    () => props.src,
    newSrc => {
      // 如果 URL 已在全局缓存中，直接使用缓存状态
      if (loadedImageCache.has(newSrc)) {
        lastLoadedUrl = newSrc;
        isLoading.value = false;
        hasError.value = false;
        isUrlStable.value = true;
        return;
      }

      // URL 变化时，重置稳定状态
      isUrlStable.value = false;
      // 触发 debounce 判断是否稳定
      markUrlStable();

      if (isValidUrl.value) {
        preloadImage(newSrc);
      } else {
        isLoading.value = true;
        hasError.value = false;
      }
    },
    { immediate: true },
  );

  // 监听 isValidUrl 变化，当 URL 从无效变为有效时触发加载
  watch(isValidUrl, valid => {
    if (valid && props.src) {
      preloadImage(props.src);
    }
  });
</script>

<style lang="scss">
  .ai-md-image-wrapper {
    display: inline-block;
    vertical-align: middle;

    .md-image {
      max-width: 100%;
      height: auto;
    }

    .md-image-loading,
    .md-image-error {
      display: inline-flex;
      gap: 6px;
      align-items: center;
      padding: 4px 8px;
      font-size: var(--ai-font-size, 12px);
      color: #979ba5;
      background-color: #f5f7fa;
      border-radius: 2px;
    }

    .md-image-error {
      color: #ea3636;
      background-color: #fee;
    }

    .md-image-error-icon {
      font-size: 14px;
    }
  }
</style>
