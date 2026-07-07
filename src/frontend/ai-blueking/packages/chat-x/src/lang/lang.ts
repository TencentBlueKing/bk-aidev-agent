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

import { isEn } from '../common/lang';

export const lang = {
  发送: 'Send',
  停止: 'Stop',
  问问小鲸: 'Ask AI',
  复制: 'Copy',
  分享: 'Share',
  点赞: 'Like',
  不满意: 'Unsatisfied',
  删除: 'Delete',
  引用: 'Quote',
  重新生成: 'Regenerate',
  重新生成将清空下文内容: 'Regenerating will clear the content below',
  提交: 'Submit',
  取消: 'Cancel',
  预览内容: 'Preview Content',
  跳转详情: 'Jump to Detail',
  '调用工具：': 'Call Tool:',
  调用中: 'Calling...',
  调用成功: 'Call Success',
  调用失败: 'Call Failed',
  说出您的想法: 'Tell us your thoughts',
  '什么原因让你满意？': 'What makes you satisfied?',
  '什么原因让你不满意？': 'What makes you dissatisfied?',
  返回内容: 'Return Content',
  编辑: 'Edit',
  深度思考: 'Deep Thinking',
  '图片加载中...': 'Loading image...',
  图片加载失败: 'Failed to load image',
  思考中: 'Thinking...',
  已思考完成: 'Thinking Completed',
  思考失败: 'Thinking Failed',
  复制成功: 'Copy Success',
  复制失败: 'Copy Failed',
  返回底部: 'Return to bottom',
  停止生成: 'Stop generating',
  正在停止: 'Stopping',
  耗时: 'Duration',
  参数: 'Parameters',
  描述: 'Description',
  // Flow Agent
  执行情况: 'Execution Status',
  执行中: 'Running',
  成功: 'Success',
  失败: 'Failed',
  挂起: 'Pending',
  待执行: 'To Be Executed',
  详情: 'Details',
  重试: 'Retry',
  重试中: 'Retrying',
  跳过中: 'Skipping',
  '任务正在重试中，不可跳过': 'The task is retrying and cannot be skipped',
  '任务正在跳过中，不可重试': 'The task is skipping and cannot be retried',
  节点: 'Node',
  节点配置: 'Node Config',
  节点输出: 'Node Output',
  基础信息: 'Basic Info',
  流程模板: 'Flow Template',
  节点名称: 'Node Name',
  步骤名称: 'Step Name',
  执行方案: 'Execution Plan',
  是否可选: 'Optional',
  失败处理: 'Failure Handler',
  超时控制: 'Timeout Control',
  是: 'Yes',
  否: 'No',
  输入参数: 'Input Params',
  输出参数: 'Output Params',
  参数名: 'Param Name',
  参数值: 'Param Value',
  名称: 'Name',
  变量说明: 'Description',
  结构化输出: 'Structured Output',
  手动跳过: 'Manual Skip',
  暂无数据: 'No Data',
  '调用 MCP：': 'Call MCP:',
  更多: 'More',
  算法方案评审单: 'Algorithm Plan Review Ticket',
  评审中: 'Reviewing',
  已废弃: 'Abandoned',
  已批准: 'Approved',
  已通过: 'Approved',
  已取消: 'Cancelled',
  已过期: 'Expired',
  已拒绝: 'Rejected',
  已撤销: 'Revoked',
  单据编号: 'Ticket No.',
  提交时间: 'Submitted At',
  当前处理人: 'Current Handler',
  无: 'None',
  查看单据详情: 'View Ticket Detail',
  复制单据: 'Copy Ticket',
  复制单据链接: 'Copy Ticket Link',
  取消审批: 'Cancel Approval',
  已取消审批: 'Approval Cancelled',
  刷新单据状态: 'Refresh Ticket Status',
  '该单据已被拒绝，无法取消': 'This ticket has been rejected and cannot be cancelled',
  '该单据已通过，无法取消': 'This ticket has been approved and cannot be cancelled',
  '单据已取消，无需重复点击': 'This ticket has been cancelled, no need to click again',
  当前状态无法取消审批: 'Approval cannot be cancelled in the current status',
  '当前会话有 {count} 个待审批单，如需继续，请先取消审批':
    'There are {count} pending approval tickets in the current conversation. To continue, cancel approval first.',
  暂不支持的中断消息: 'Unsupported interrupt message',
  检索中: 'Searching',
  检索完成: 'Search Completed',
  上传文件: 'Upload File',
  '请求中...': 'Requesting...',
  取消满意: 'Cancel satisfied',
  取消不满意: 'Cancel dissatisfied',
  '确认删除该回答？': 'Confirm delete this answer?',
  '删除操作无法撤回，请谨慎操作！': 'This operation cannot be undone. Please proceed with caution!',
  预览: 'Preview',
  缩小: 'Zoom Out',
  放大: 'Zoom In',
  旋转: 'Rotate',
  下载: 'Download',
  '抱歉，图片加载失败，可尝试重新加载': 'Sorry, image loading failed. Please try reloading.',
  重置: 'Reset',
  重新加载: 'Reload',
  宽: 'W',
  高: 'H',
  上传图片: 'Upload Image',
  '搜索 关键字': 'Search keyword',
  选择日期: 'Select date',
  在对话中定位: 'Locate in Chat',
  全选: 'Select All',
  确定: 'Confirm',
  '上传图片, 最多支持上传 3 个, 最大支持 2.4MB': 'Upload Image, up to 3 images supported, max 2.4MB each',
  '你好，我是小鲸': 'Hello, I am BlueKing AI Bot',
  清空搜索: 'Clear Search',
  搜索结果为空: 'Search Result is Empty',
  有效证据: 'Valid Evidence',
  全屏: 'Full Screen',
  退出全屏: 'Exit Full Screen',
  请选择以继续: 'Please choose to continue',
  继续: 'Continue',
  '收到信息：': 'Received: ',
  待审批: 'Pending',
  已审批: 'Approved',
  // 用户回答问题中断（human-in-the-loop）
  完成: 'Done',
  跳过: 'Skip',
  单选: 'Single',
  多选: 'Multiple',
  其他: 'Others',
  回答内容: 'Answers',
  已回复: 'Replied',
  '请输入...': 'Please enter...',
} as const;

export const t = (key: keyof typeof lang) => {
  if (isEn) {
    return lang[key];
  }
  return key;
};
