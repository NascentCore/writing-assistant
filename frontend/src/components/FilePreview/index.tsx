import { Modal, Spin } from 'antd';
import React, { useEffect, useMemo, useState } from 'react';
import FileViewer from 'react-file-viewer';

interface FilePreviewProps {
  open: boolean;
  onCancel: () => void;
  fetchFile: () => Promise<string>;
  fileName: string;
}

const FilePreview: React.FC<FilePreviewProps> = ({
  open,
  onCancel,
  fetchFile,
  fileName,
}) => {
  const [fileData, setFileData] = useState<string>();

  useEffect(() => {
    if (open) {
      fetchFile().then(setFileData);
    } else if (fileData) {
      URL.revokeObjectURL(fileData);
      setFileData(undefined);
    }
  }, [open, fetchFile]);

  useEffect(() => {
    // 组件卸载时清理
    return () => {
      if (fileData) {
        URL.revokeObjectURL(fileData);
      }
    };
  }, [fileData]);

  const fileType = useMemo(() => {
    if (!fileName) return '';
    return fileName.split('.').pop()?.toLowerCase() || '';
  }, [fileName]);

  const onError = (e: Error) => {
    console.error('文件预览错误:', e);
  };

  return (
    <Modal
      title="文件预览"
      open={open}
      onCancel={onCancel}
      footer={null}
      width={1000}
      destroyOnClose
    >
      {fileData ? (
        <FileViewer
          fileType={fileType}
          filePath={fileData}
          onError={onError}
          errorComponent={() => <div>无法预览该文件</div>}
        />
      ) : (
        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <Spin tip="加载中..." />
        </div>
      )}
    </Modal>
  );
};

export default FilePreview;
