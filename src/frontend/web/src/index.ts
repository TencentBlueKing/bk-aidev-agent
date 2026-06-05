export {
  createDocsAssetService,
  getDefaultStaticDir,
  resolveDocsBasePath,
  warmCache,
  DocsAssetService,
  DOCS_BASE_PLACEHOLDER,
} from './docs-asset-service';
export type {
  DocsAssetServiceOptions,
  DocsAssetResult,
} from './docs-asset-service';
export { createDocsMiddleware, warmCache as warmDocsCache } from './middleware';
export type { DocsMiddlewareOptions } from './middleware';
export { createMockAguiRouter } from './mock-routes';
export {
  dispatchMockAguiRequest,
  handleMockChatCompletion,
  mockSessionContent,
  mockSessionContentBatchDelete,
  mockSessionContentStop,
  mockSessionFeedback,
  mockSessionFeedbackReasons,
} from './mock-handlers';
export type { MockJsonResult } from './mock-handlers';
