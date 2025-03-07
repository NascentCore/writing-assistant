import { useState } from 'react';

interface Document {
  id: string;
  doc_id: string;
  title: string;
  content: string;
  updated_at: string;
}

export default () => {
  const [documents, setDocuments] = useState<Document[]>([]);

  return {
    documents,
    setDocuments,
    // 根据 id 获取文档标题
    getDocumentTitle: (id: string) => {
      const doc = documents.find((doc) => doc.id === id || doc.doc_id === id);
      return doc?.title || '未命名文档';
    },
  };
};
