import { API_BASE_URL } from '@/config';
import { Form, Input, Modal, message } from 'antd';
import React, { useEffect, useState } from 'react';

interface User {
  username: string;
  email: string;
}

interface UserProfileProps {
  onClose: () => void;
}

interface UpdateData {
  email?: string;
  current_password?: string;
  new_password?: string;
}

const UserProfile: React.FC<UserProfileProps> = ({ onClose }) => {
  const [form] = Form.useForm();
  const [user, setUser] = useState<User | null>(null);

  const fetchUserInfo = async (): Promise<void> => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data.data);
        form.setFieldsValue({
          username: data.data.username,
          email: data.data.email,
        });
      }
    } catch (error) {
      message.error('获取用户信息失败');
    }
  };

  useEffect(() => {
    fetchUserInfo();
  }, []);

  const handleSubmit = async (values: any): Promise<void> => {
    if (!user) return;

    const updateData: UpdateData = {};
    if (values.email !== user.email) updateData.email = values.email;
    if (values.current_password && values.new_password) {
      updateData.current_password = values.current_password;
      updateData.new_password = values.new_password;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
        method: 'PUT',
        headers: {
          Authorization: `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      });

      if (response.ok) {
        message.success('更新成功');
        form.resetFields(['current_password', 'new_password']);
        fetchUserInfo();
        onClose();
      } else {
        const error = await response.json();
        message.error(error.detail || '更新失败');
      }
    } catch (error) {
      message.error('更新失败，请稍后重试');
    }
  };

  return (
    <Modal
      title="个人信息"
      open={true}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText="保存"
      cancelText="取消"
      destroyOnClose
    >
      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{ username: user?.username, email: user?.email }}
      >
        <Form.Item label="用户名" name="username">
          <Input size="large" disabled />
        </Form.Item>

        <Form.Item
          label="邮箱"
          name="email"
          rules={[
            { required: true, message: '请输入邮箱' },
            { type: 'email', message: '请输入有效的邮箱地址' },
          ]}
        >
          <Input size="large" />
        </Form.Item>

        <Form.Item
          label="当前密码"
          name="current_password"
          rules={[
            {
              validator: (_, value) => {
                if (form.getFieldValue('new_password') && !value) {
                  return Promise.reject('修改密码时需要输入当前密码');
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Input.Password size="large" />
        </Form.Item>

        <Form.Item
          label="新密码"
          name="new_password"
          rules={[
            {
              validator: (_, value) => {
                if (form.getFieldValue('current_password') && !value) {
                  return Promise.reject('请输入新密码');
                }
                return Promise.resolve();
              },
            },
          ]}
        >
          <Input.Password size="large" />
        </Form.Item>
      </Form>
    </Modal>
  );
};

export default UserProfile;
