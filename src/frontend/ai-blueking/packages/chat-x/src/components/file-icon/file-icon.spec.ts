import { mount } from '@vue/test-utils';
import { describe, expect, it } from 'vitest';

import { getFileIconSvg } from '../../icons/file-icons';
import FileIcon from './file-icon.vue';

/** 将原始 svg 走一遍 DOM 序列化，与 v-html 渲染结果对齐后再断言 */
const serializeSvg = (svg: string) => {
  const el = document.createElement('div');
  el.innerHTML = svg;
  return el.innerHTML;
};

describe('FileIcon', () => {
  it('应按 fileType 内联对应的 svg', () => {
    const wrapper = mount(FileIcon, { props: { fileType: 'pdf' } });

    expect(wrapper.find('.ai-file-icon svg').exists()).toBe(true);
    expect(wrapper.find('.ai-file-icon').element.innerHTML).toBe(serializeSvg(getFileIconSvg('pdf')));
  });

  it('fileType 缺省时应回退 fileName 推断', () => {
    const wrapper = mount(FileIcon, { props: { fileName: 'train.py' } });

    expect(wrapper.find('.ai-file-icon').element.innerHTML).toBe(serializeSvg(getFileIconSvg('py')));
  });

  it('类型变更时应切换图标', async () => {
    const wrapper = mount(FileIcon, { props: { fileType: 'pdf' } });

    await wrapper.setProps({ fileType: 'docx' });

    expect(wrapper.find('.ai-file-icon').element.innerHTML).toBe(serializeSvg(getFileIconSvg('docx')));
  });
});
