import { useState } from 'react';

interface Document {
  id: string;
  doc_id: string;
  title: string;
  content: string;
  updated_at: string;
}

export default () => {
  const [document, setDocument] = useState<Document>({} as Document);

  return {
    document,
    setDocument,
    // 根据 id 获取文档标题
  };
};
