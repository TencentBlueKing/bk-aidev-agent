<template>
  <div class="image-demo">
    <h2>Image / ImagePreview 组件示例</h2>

    <section class="demo-section">
      <h3>1. 单图预览 - 基础用法</h3>
      <p>鼠标变为放大镜，点击直接打开全屏预览</p>
      <div class="demo-row">
        <AiImage
          :height="100"
          :src="singleImage"
          :width="100"
        />
      </div>
    </section>

    <section class="demo-section">
      <h3>2. 高清预览 - previewProps.src</h3>
      <p>缩略图和预览图使用不同 URL，点击预览加载高清大图</p>
      <div class="demo-row">
        <AiImage
          :height="100"
          :preview-props="{ src: hdImage }"
          :src="singleImage"
          :width="100"
        />
      </div>
    </section>

    <section class="demo-section">
      <h3>3. 多图预览 - ImagePreviewGroup</h3>
      <p>点击任意图片打开预览，支持左右切换</p>
      <ImagePreviewGroup>
        <div class="demo-row">
          <AiImage
            v-for="(img, idx) in multiImages"
            :key="idx"
            :height="100"
            :src="img"
            :width="100"
          />
        </div>
      </ImagePreviewGroup>
    </section>

    <section class="demo-section">
      <h3>4. 多图预览 - 带图片信息</h3>
      <p>Group 设置 showInfo，工具栏显示图片尺寸和清晰度</p>
      <ImagePreviewGroup :show-info="true">
        <div class="demo-row">
          <AiImage
            v-for="(img, idx) in multiImagesWithInfo"
            :key="idx"
            :height="100"
            :preview-props="{ src: img.url }"
            :src="img.thumbnail"
            :width="100"
          />
        </div>
      </ImagePreviewGroup>
    </section>

    <section class="demo-section">
      <h3>5. 懒加载</h3>
      <p>设置 lazy，图片进入视口时才加载（滚动查看效果）</p>
      <div class="demo-scroll-area">
        <div class="demo-scroll-placeholder">↓ 往下滚动查看懒加载图片</div>
        <div class="demo-row">
          <AiImage
            v-for="(img, idx) in multiImages"
            :key="idx"
            :height="120"
            :lazy="true"
            :src="img"
            :width="160"
          />
        </div>
      </div>
    </section>

    <section class="demo-section">
      <h3>6. 图片加载失败</h3>
      <p>hover 出现"重新加载"按钮</p>
      <div class="demo-row">
        <AiImage
          :height="100"
          src="https://invalid-url.example.com/broken.jpg"
          :width="100"
        />
      </div>
    </section>

    <section class="demo-section">
      <h3>7. 不同尺寸</h3>
      <div class="demo-row">
        <AiImage
          :height="60"
          :src="singleImage"
          :width="60"
        />
        <AiImage
          :height="100"
          :src="singleImage"
          :width="100"
        />
        <AiImage
          :height="150"
          :src="singleImage"
          :width="150"
        />
      </div>
    </section>

    <section class="demo-section">
      <h3>8. 禁用预览</h3>
      <p>设置 :preview="false" 禁用预览功能，鼠标样式恢复默认</p>
      <div class="demo-row">
        <AiImage
          :height="100"
          :preview="false"
          :src="singleImage"
          :width="100"
        />
      </div>
    </section>

    <section class="demo-section">
      <h3>9. 自定义下载 - Group 模式</h3>
      <p>ImagePreviewGroup 设置 onDownload 回调</p>
      <ImagePreviewGroup :on-download="handleCustomDownload">
        <div class="demo-row">
          <AiImage
            v-for="(img, idx) in multiImages"
            :key="idx"
            :height="100"
            :src="img"
            :width="100"
          />
        </div>
      </ImagePreviewGroup>
    </section>

    <section class="demo-section">
      <h3>10. ImagePreview 独立使用</h3>
      <p>通过按钮手动控制打开预览</p>
      <div class="demo-row">
        <button
          class="demo-btn"
          @click="standaloneVisible = true"
        >
          打开多图预览
        </button>
        <ImagePreview
          v-model:visible="standaloneVisible"
          :images="standaloneImages"
          :show-info="true"
        >
          <template #extra>
            <div
              class="demo-extra-btn"
              title="自定义按钮"
              @click="handleExtraAction"
            >
              ⭐
            </div>
          </template>
        </ImagePreview>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import ImagePreviewGroup from '../../src/components/image-preview/image-preview-group.vue';
  import ImagePreview from '../../src/components/image-preview/image-preview.vue';
  import AiImage from '../../src/components/image-preview/image.vue';

  import type { ImageItem } from '../../src/types/image';

  const singleImage = 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=400&h=300&fit=crop';
  const hdImage = 'https://images.unsplash.com/photo-1506744038136-46273834b3fb?w=1920&h=1080&fit=crop';

  const multiImages = [
    'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=800&h=600&fit=crop',
    'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=900&h=600&fit=crop',
    'https://images.unsplash.com/photo-1433086966358-54859d0ed716?w=700&h=500&fit=crop',
  ];

  const multiImagesWithInfo = [
    {
      thumbnail: 'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=400&h=300&fit=crop',
      url: 'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=1920&h=1080&fit=crop',
    },
    {
      thumbnail: 'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=400&h=300&fit=crop',
      url: 'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=1600&h=900&fit=crop',
    },
    {
      thumbnail: 'https://images.unsplash.com/photo-1433086966358-54859d0ed716?w=400&h=300&fit=crop',
      url: 'https://images.unsplash.com/photo-1433086966358-54859d0ed716?w=1280&h=720&fit=crop',
    },
  ];

  const standaloneImages: ImageItem[] = [
    {
      url: 'https://images.unsplash.com/photo-1469474968028-56623f02e42e?w=1920&h=1080&fit=crop',
      name: '风景图1',
      width: 1920,
      resolution: '超清',
    },
    {
      url: 'https://images.unsplash.com/photo-1447752875215-b2761acb3c5d?w=1600&h=900&fit=crop',
      name: '风景图2',
      width: 1600,
      resolution: '高清',
    },
    {
      url: 'https://images.unsplash.com/photo-1433086966358-54859d0ed716?w=1280&h=720&fit=crop',
      name: '风景图3',
      width: 1280,
      resolution: '标清',
    },
  ];

  const standaloneVisible = ref(false);

  const handleCustomDownload = (url: string) => {
    alert(`自定义下载：${url}`);
  };

  const handleExtraAction = () => {
    alert('自定义操作被点击！');
  };
</script>

<style scoped>
  .image-demo {
    width: 800px;
    max-height: 100vh;
    padding: 24px;
    overflow-y: auto;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }

  .image-demo h2 {
    padding-bottom: 12px;
    margin-bottom: 24px;
    font-size: 22px;
    color: #313238;
    border-bottom: 1px solid #eaebf0;
  }

  .demo-section {
    margin-bottom: 32px;
  }

  .demo-section h3 {
    margin-bottom: 8px;
    font-size: 16px;
    color: #313238;
  }

  .demo-section p {
    margin-bottom: 12px;
    font-size: 13px;
    color: #979ba5;
  }

  .demo-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: flex-start;
  }

  .demo-scroll-area {
    height: 200px;
    overflow-y: auto;
    border: 1px dashed #dcdee5;
    border-radius: 4px;
  }

  .demo-scroll-placeholder {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 180px;
    font-size: 14px;
    color: #979ba5;
  }

  .demo-btn {
    padding: 8px 16px;
    font-size: 14px;
    color: #fff;
    cursor: pointer;
    background: #3a84ff;
    border: none;
    border-radius: 4px;
    transition: background 0.2s;
  }

  .demo-btn:hover {
    background: #699df4;
  }

  .demo-extra-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    font-size: 14px;
    cursor: pointer;
    border-radius: 4px;
    transition: background 0.2s;
  }

  .demo-extra-btn:hover {
    background: rgb(255 255 255 / 20%);
  }
</style>
