/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import type { Component, h, VNode } from 'vue';

import { type Checkbox, type Form, type Input, type Radio, type Select, type Switcher } from 'bkui-vue';

export type BaseShortcutComponent<T extends keyof ShortcutComponentProps> = OldShortcut & {
  formItemProps?: InstanceType<typeof Form.FormItem>['$props'];
  key: string;
  props?: ShortcutComponentProps[T];
  type: T;
};

export interface CheckboxGroupShortcutComponent extends BaseShortcutComponent<'checkboxGroup'> {
  props: InstanceType<typeof Checkbox.Group>['$props'] & {
    options: InstanceType<typeof Checkbox>['$props'][];
  };
}

export type InputShortcutComponent = BaseShortcutComponent<'input'>;

export type NumberShortcutComponent = BaseShortcutComponent<'number'>;

export interface OldShortcut {
  default?: string;
  fillBack?: boolean;
  fillRegx?: RegExp;
  key?: string;
  max?: 100;
  min?: 1;
  name?: string;
  options?: { label: string; value: string }[];
  placeholder?: string;
  required?: boolean;
  rows?: number;
}

export interface RadioGroupShortcutComponent extends BaseShortcutComponent<'radioGroup'> {
  props: InstanceType<typeof Radio.Group>['$props'] & {
    options: InstanceType<typeof Radio>['$props'][];
  };
}

export interface SelectShortcutComponent extends BaseShortcutComponent<'select'> {
  props?: InstanceType<typeof Select>['$props'] & {
    options: InstanceType<typeof Select.Option>['$props'][];
  };
}

export interface Shortcut {
  alias?: string;
  components?: ShortcutComponent[];
  description?: string;
  formModel?: Record<string, unknown>;
  icon?: ((c: typeof h) => Component | VNode) | string | VNode;
  id: string;
  key?: string;
  name: string;
}

export type ShortcutComponent =
  | CheckboxGroupShortcutComponent
  | InputShortcutComponent
  | NumberShortcutComponent
  | RadioGroupShortcutComponent
  | SelectShortcutComponent
  | SwitcherShortcutComponent
  | TextareaShortcutComponent
  | TextShortcutComponent;

export type ShortcutComponentProps = {
  checkboxGroup: InstanceType<typeof Checkbox.Group>['$props'];
  input: InstanceType<typeof Input>['$props'];
  number: InstanceType<typeof Input>['$props'];
  radioGroup: InstanceType<typeof Radio.Group>['$props'];
  select: InstanceType<typeof Select>['$props'];
  switcher: InstanceType<typeof Switcher>['$props'];
  text: InstanceType<typeof Input>['$props'];
  textarea: InstanceType<typeof Input>['$props'];
};

export type SwitcherShortcutComponent = BaseShortcutComponent<'switcher'>;

export type TextareaShortcutComponent = BaseShortcutComponent<'textarea'>;

export type TextShortcutComponent = BaseShortcutComponent<'text'>;
