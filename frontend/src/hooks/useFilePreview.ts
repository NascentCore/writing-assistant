import { fetchWithAuthStream } from '@/utils/fetch';
import { useCallback, useState } from 'react';

export interface FilePreviewState {
  visible: boolean;
  fileName: string;
  fileId: string;
}

export default function useFilePreview() {
  const [previewState, setPreviewState] = useState<FilePreviewState>({
    visible: false,
    fileName: '',
    fileId: '',
  });

  const showPreview = useCallback((fileName: string, fileId: string) => {
    setPreviewState({
      visible: true,
      fileName,
      fileId,
    });
  }, []);

  const hidePreview = useCallback(() => {
    setPreviewState((prev) => ({
      ...prev,
      visible: false,
    }));
  }, []);

  const fetchPreviewFile = useCallback(async () => {
    if (!previewState.fileId) return '';

    try {
      const response = await fetchWithAuthStream(
        `/api/v1/rag/files/${previewState.fileId}/download`,
        { method: 'GET' },
        true,
      );
      if (!response) {
        throw new Error('获取文件失败');
      }
      const blob = await response.blob();
      return URL.createObjectURL(blob);
    } catch (error) {
      console.error('文件预览获取失败:', error);
      throw error;
    }
  }, [previewState.fileId]);

  return {
    previewState,
    showPreview,
    hidePreview,
    fetchPreviewFile,
  };
}
