import { API_BASE_URL } from '@/config';
import { fetchWithAuthNew } from '@/utils/fetch';
import { InboxOutlined } from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd';
import { message, Upload } from 'antd';
import styles from './index.module.less';

const { Dragger } = Upload;

interface FileUploadProps extends Omit<UploadProps, 'value' | 'onChange'> {
  url?: string;
  category?: string;
  value?: UploadFile[];
  onChange?: (fileList: UploadFile[]) => void;
}

const FileUpload: React.FC<FileUploadProps> = ({
  url = '/api/v1/rag/files',
  category,
  value,
  onChange,
  ...restProps
}) => {
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    fileList: value,
    onRemove: async (file: UploadFile) => {
      try {
        const fileId = file.response?.data[0]?.file_id;
        if (!fileId) {
          message.error('文件ID不存在');
          return false;
        }
        const result = await fetchWithAuthNew('/api/v1/rag/files', {
          method: 'DELETE',
          data: {
            file_ids: [fileId],
          },
        });
        if (result !== undefined) {
          message.success('删除成功');
          return true;
        }
        return false;
      } catch (error) {
        message.error('删除失败');
        return false;
      }
    },
    customRequest: ({ file, onSuccess, onError }) => {
      const formData = new FormData();
      formData.append('files', file);
      const xhr = new XMLHttpRequest();
      xhr.open(
        'POST',
        `${API_BASE_URL}${url}${category ? `?category=${category}` : ''}`,
      );
      xhr.setRequestHeader(
        'authorization',
        `Bearer ${localStorage.getItem('token')}`,
      );
      xhr.onload = () => {
        if (xhr.status === 200) {
          try {
            const response = JSON.parse(xhr.responseText);
            if (response.code !== 200) {
              onError?.(new Error('上传失败'));
              return;
            }
            onSuccess?.(response);
          } catch (e) {
            onError?.(new Error('解析响应失败'));
          }
        } else {
          onError?.(new Error('上传失败'));
        }
      };
      xhr.onerror = () => {
        onError?.(new Error('网络错误'));
      };
      xhr.send(formData);
    },
    onChange(info) {
      const { status } = info.file;
      onChange?.(info.fileList);

      if (status === 'done') {
        message.success(`${info.file.name} 文件上传成功`);
      } else if (status === 'error') {
        message.error(`${info.file.name} 文件上传失败`);
      }
    },
    ...restProps,
  };

  return (
    <div className={styles.uploadContainer}>
      <Dragger accept=".docx,.doc,.pdf" {...uploadProps}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">支持单个或批量上传</p>
      </Dragger>
    </div>
  );
};

export default FileUpload;
