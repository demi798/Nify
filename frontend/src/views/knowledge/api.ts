/** knowledge 模块 API 出口（经 shared/api-client）。 */
export {
  KnowledgeApiPrefix,
  getKnowledgeBaseList,
  getKnowledgeBase,
  createKnowledgeBase,
  updateKnowledgeBase,
  deleteKnowledgeBase,
  getKnowledgeBaseReferences,
  getKnowledgeBaseOptions,
  getDocumentList,
  getDocument,
  getDocumentChunks,
  uploadDocument,
  deleteDocument,
  retryDocument,
} from "@/api/knowledge";

export type {
  KnowledgeBase,
  KnowledgeBaseCreateBody,
  KnowledgeBaseUpdateBody,
  KnowledgeBaseReferences,
  KnowledgeBaseRefItem,
  KnowledgeDocument,
  KnowledgeChunk,
  KnowledgeCursorPage,
} from "@/api/knowledge";
