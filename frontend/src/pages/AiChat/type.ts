import type { FileItem } from '@/types/common';

// 引用文件类型
export interface ReferenceFile {
  file_id: string;
  file_name: string;
  file_path: string;
  file_ext: string;
  file_size: number;
  content: string;
}

// 文件全文内容类型
export interface FileFullContent {
  file_id: string;
  file_name: string;
  content: string;
}

// 引用标记组件的Props类型
export interface ReferenceMarkerProps {
  index: number;
  referenceFile: ReferenceFile;
}

// 内联引用组件的Props类型
export interface InlineReferencesContentProps {
  content: string;
  referenceFiles?: ReferenceFile[];
}

// 聊天消息类型（与ChatSessionList中定义的类型扩展）
export interface ChatMessage {
  key: string;
  placement: 'start' | 'end';
  content: string;
  avatarType: 'user' | 'assistant';
  files?: FileItem[];
  atfiles?: FileItem[];
  loading?: boolean;
  reference_files?: ReferenceFile[];
}

// 模型类型
export interface Model {
  id: string;
  name: string;
  description: string;
}

// AiChat组件的Props
export interface AIChatProps {
  setShowAIChat: (show: boolean) => void;
}

// AiChat组件的Ref
export interface AIChatRef {
  addSelectedFile: (file: FileItem) => void;
}
