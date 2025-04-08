export interface FilePreviewProps {
  open: boolean;
  onCancel: () => void;
  fetchFile: () => Promise<string>;
  fileName: string;
}

export type SupportedFileType = 'pdf' | 'docx' | 'doc' | 'other';
