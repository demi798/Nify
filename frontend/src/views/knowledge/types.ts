/** knowledge 模块展示类型。 */

export type KnowledgeBaseRow = {
  id: string;
  name: string;
  description: string;
  documentCount: number;
  isEnabled: boolean;
  createdAt: string;
  updatedAt: string;
};

export type KnowledgeBaseFormValues = {
  id?: string;
  name: string;
  description?: string;
  isEnabled?: boolean;
};

export type KnowledgeDocumentRow = {
  id: string;
  name: string;
  /** 展示用扩展名 / MIME 简化 */
  fileType: string;
  contentType: string;
  byteSize: number;
  chunkCount: number;
  status: string;
  errorMessage: string;
  createdAt: string;
};

export type KnowledgeChunkRow = {
  id: string;
  seq: number;
  content: string;
  tokenCount: number;
};
