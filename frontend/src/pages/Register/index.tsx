import { fetchWithAuthNew } from '@/utils/fetch';
import { history } from '@umijs/max';
import { Button, Form, Input } from 'antd';
import React from 'react';
import { API_BASE_URL } from '../../config';
import './index.less';

interface RegisterFormValues {
  username: string;
  email: string;
  password: string;
}

const RegisterPage: React.FC = () => {
  const [form] = Form.useForm();

  const handleSubmit = async (values: RegisterFormValues): Promise<void> => {
    try {
      const response = await fetchWithAuthNew(
        `${API_BASE_URL}/api/v1/register`,
        {
          method: 'POST',
          data: values,
        },
      );

      if (response) {
        localStorage.setItem('token', response.access_token);
        localStorage.setItem('username', values.username);
        history.push('/');
        localStorage.removeItem('current_chat_session_id');
        localStorage.removeItem('current_document_id');
      }
    } catch (error) {
      // fetchWithAuthNew 已经处理了错误提示，这里不需要额外处理
      console.error('注册失败:', error);
    }
  };

  return (
    <div className="register-container-forUni">
      <div className="auth-container">
        <div className="auth-box">
          <h2>注册</h2>
          <Form
            form={form}
            onFinish={handleSubmit}
            layout="vertical"
            requiredMark={false}
          >
            <Form.Item
              label="用户名"
              name="username"
              rules={[{ required: true, message: '请输入用户名' }]}
            >
              <Input placeholder="请输入用户名" size="large" />
            </Form.Item>

            <Form.Item
              label="邮箱"
              name="email"
              rules={[
                { required: true, message: '请输入邮箱' },
                { type: 'email', message: '请输入有效的邮箱地址' },
              ]}
            >
              <Input placeholder="请输入邮箱" size="large" />
            </Form.Item>

            <Form.Item
              label="密码"
              name="password"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password placeholder="请输入密码" size="large" />
            </Form.Item>

            <Form.Item>
              <Button type="primary" htmlType="submit" block size="large">
                注册
              </Button>
            </Form.Item>
          </Form>
          <div className="auth-switch">
            已有账号？{' '}
            <Button
              type="link"
              onClick={() => history.push('/Login')}
              style={{ padding: 0 }}
            >
              去登录
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
