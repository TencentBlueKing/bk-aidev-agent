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
import { defineConfig, loadEnv } from "vite"

import { createCommonConfig } from "./vite.utils"

const host = "0.0.0.0"
const port = 8001

// 从环境变量读取允许的主机列表，支持逗号分隔的多个域名
// 例如：VITE_ALLOWED_HOSTS=example.com,other.example.com
// 如果未设置，则默认允许所有主机 ["*"]
const getAllowedHosts = (): string[] => {
  const env = loadEnv(process.env.NODE_ENV || "development", process.cwd(), "")
  const allowedHostsEnv = env.VITE_ALLOWED_HOSTS
  if (allowedHostsEnv) {
    return allowedHostsEnv
      .split(",")
      .map((host) => host.trim())
      .filter(Boolean)
  }
  return ["*"]
}

export default defineConfig(() => ({
  ...createCommonConfig(),
  server: {
    host,
    port,
    allowedHosts: getAllowedHosts(),
  },
}))
