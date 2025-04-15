import { API_BASE_URL } from '@/config';
import { fetchWithAuthNew } from '@/utils/fetch';
import { InboxOutlined } from '@ant-design/icons';
import type { UploadFile, UploadProps } from 'antd';
import { message, Select, Space, Upload } from 'antd';
import { useEffect, useState } from 'react';
import styles from './index.module.less';
import { Department, FileUploadProps } from './type';

const { Dragger } = Upload;

const FileUpload: React.FC<FileUploadProps> = ({
  url = '/api/v1/rag/files',
  category,
  value,
  onChange,
  selectedDepartment,
  onDepartmentChange,
  ...restProps
}) => {
  const [departments, setDepartments] = useState<Department[]>([]);
  const [loading, setLoading] = useState(false);
  const [currentDepartment, setCurrentDepartment] = useState<
    string | undefined
  >(selectedDepartment);

  // 获取部门列表
  useEffect(() => {
    const fetchDepartments = async () => {
      setLoading(true);
      try {
        let my_own = localStorage.getItem('admin') !== '2';
        const result = await fetchWithAuthNew(
          `/api/v1/users/departments?my_own=${my_own}`,
          {
            method: 'GET',
          },
        );

        if (result.length > 0) {
          setDepartments(result);

          // 如果只有一个部门，自动选中
          if (result.length === 1 && !currentDepartment) {
            setCurrentDepartment(result[0].department_id);
            onDepartmentChange?.(result[0].department_id);
          }
        }
      } catch (error) {
        message.error('获取部门列表失败');
      } finally {
        setLoading(false);
      }
    };

    fetchDepartments();
  }, []);

  // 处理部门变更
  const handleDepartmentChange = (value: string) => {
    setCurrentDepartment(value);
    onDepartmentChange?.(value);
  };

  const uploadProps: UploadProps = {
    name: 'file',
    multiple: true,
    fileList: value,
    onRemove: async (file: UploadFile) => {
      try {
        const fileId = file.response?.data[0]?.file_id;
        if (!fileId) {
          // message.error('文件ID不存在');
          return true;
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
      // 检查是否选择了部门
      if (!currentDepartment) {
        message.error('请先选择部门');
        onError?.(new Error('请先选择部门'));
        return;
      }

      const formData = new FormData();
      formData.append('files', file);

      const xhr = new XMLHttpRequest();
      xhr.open(
        'POST',
        `${API_BASE_URL}${url}${category ? `?category=${category}` : ''}${
          currentDepartment ? `&department_id=${currentDepartment}` : ''
        }`,
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
              message.error(`${response.message}`);
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
        console.error(`${info.file.name} 文件上传失败`);
        // onError?.(new Error('上传失败'));
      }
    },
    ...restProps,
  };

  return (
    <div className={styles.uploadContainer}>
      <Space direction="vertical" style={{ width: '100%' }}>
        <Select
          placeholder="请选择部门"
          value={currentDepartment}
          onChange={handleDepartmentChange}
          loading={loading}
          style={{ width: '100%' }}
          showSearch
          optionFilterProp="children"
          allowClear={false}
          options={departments.map((dept) => ({
            value: dept.department_id,
            label: dept.name,
          }))}
        />
        <Dragger
          disabled={!currentDepartment}
          accept=".docx,.doc,.pdf"
          {...uploadProps}
        >
          <p className="ant-upload-drag-icon">
            <InboxOutlined />
          </p>
          <p className="ant-upload-text">
            点击或拖拽文件到此区域上传，支持 pdf，docx，doc
          </p>
          <p className="ant-upload-hint">支持单个或批量上传</p>
        </Dragger>
      </Space>
    </div>
  );
};

export default FileUpload;
