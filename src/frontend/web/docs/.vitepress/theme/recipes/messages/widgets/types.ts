/** 表单组件提交的结果，由 CustomMessageRenderer 向上抛出 */
export interface FormSubmit {
  title: string;
  action: string;
  values: Record<string, string>;
}
