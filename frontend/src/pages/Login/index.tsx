import { fetchWithAuthNew } from '@/utils/fetch';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { history } from '@umijs/max';
import { Button, Form, Input, message } from 'antd';
import React from 'react';
import './index.less';

interface LoginResponse {
  access_token: string;
}

const LoginPage: React.FC = () => {
  const [form] = Form.useForm();
  const [messageApi, contextHolder] = message.useMessage();

  const handleSubmit = async (values: {
    username: string;
    password: string;
  }): Promise<void> => {
    try {
      const formData = new FormData();
      formData.append('username', values.username);
      formData.append('password', values.password);

      const response = await fetchWithAuthNew<LoginResponse>('/api/v1/token', {
        method: 'POST',
        data: formData,
      });

      if (response && 'access_token' in response) {
        localStorage.setItem('token', response.access_token);
        localStorage.setItem('username', values.username);
        window.location.href = '/';
      }
    } catch (error) {
      messageApi.error('登录失败，请稍后重试');
    }
  };

  return (
    <div className="login-container-forUni">
      {contextHolder}
      <div className="auth-container">
        <div className="auth-box">
          <h2>登录</h2>
          <Form
            form={form}
            name="login"
            onFinish={handleSubmit}
            autoComplete="off"
          >
            <Form.Item
              name="username"
              rules={[{ required: true, message: '请输入用户名！' }]}
            >
              <Input
                prefix={<UserOutlined />}
                placeholder="用户名"
                size="large"
              />
            </Form.Item>

            <Form.Item
              name="password"
              rules={[{ required: true, message: '请输入密码！' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="密码"
                size="large"
              />
            </Form.Item>

            <Form.Item>
              <Button type="primary" htmlType="submit" block size="large">
                登录
              </Button>
            </Form.Item>
          </Form>
          <div className="auth-switch">
            没有账号？
            <Button type="link" onClick={() => history.push('/Register')}>
              去注册
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
