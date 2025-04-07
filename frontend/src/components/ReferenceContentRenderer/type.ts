/**
 * 引用文件类型
 */
export interface ReferenceFile {
  file_id: string;
  file_name: string;
  file_path: string;
  file_ext: string;
  file_size: number;
  content: string;
}

/**
 * 文件全文内容类型
 */
export interface FileFullContent {
  file_id: string;
  file_name: string;
  content: string;
}

/**
 * 引用标记组件的Props类型
 */
export interface ReferenceMarkerProps {
  index: number;
  referenceFile: ReferenceFile;
}

/**
 * 内联引用组件的Props类型
 */
export interface InlineReferencesContentProps {
  content: string;
  referenceFiles?: ReferenceFile[];
}
