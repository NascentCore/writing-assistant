import { API_BASE_URL } from '@/config';
import { InboxOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { message, Upload } from 'antd';
import styles from './index.module.less';

const { Dragger } = Upload;

const FileUpload: React.FC = () => {
  const props: UploadProps = {
    name: 'file',
    multiple: true,
    action: `${API_BASE_URL}/api/v1/files`,
    customRequest: ({ file, onSuccess, onError }) => {
      const formData = new FormData();
      formData.append('files', file);
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `${API_BASE_URL}/api/v1/files`);
      // 添加额外的请求头
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
              message.error(`${response.message}`);
              return;
            }

            // 将服务器返回的响应传给 onSuccess
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

      if (status === 'done') {
        message.success(`${info.file.name} 文件上传成功`);
      } else if (status === 'error') {
        console.log('🚀 ~ info:', info);
        // message.error(`${info.file.name} 文件上传失败`);
      }
    },
  };

  return (
    <div className={styles.uploadContainer}>
      <Dragger {...props}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">
          点击或拖拽文件到此区域上传，支持 pdf，docx，doc
        </p>
        <p className="ant-upload-hint">支持单个或批量上传</p>
      </Dragger>
    </div>
  );
};

export default FileUpload;
