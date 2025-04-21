import logoImg from '@/assets/11691741759860_.pic.jpg';
import { fetchWithAuthNew } from '@/utils/fetch';
import { LockOutlined, UserOutlined } from '@ant-design/icons';
import { Button, Form, Input, message } from 'antd';
import React from 'react';
import './index.less';

interface LoginResponse {
  access_token: string;
  admin: number;
  user_id: string;
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
      console.log('response', response);
      if (response && 'access_token' in response) {
        localStorage.setItem('user_id', response.user_id);
        localStorage.setItem('token', response.access_token);
        localStorage.setItem('username', values.username);
        localStorage.setItem('admin', response.admin.toString());
        localStorage.removeItem('current_chat_session_id');
        localStorage.removeItem('current_document_id');
        localStorage.removeItem('ai_chat_model');
        window.location.href = '/WritingAssistant';
      }
    } catch (error) {
      messageApi.error('登录失败，请稍后重试');
    }
  };

  return (
    <div className="login-container-forUni">
      {contextHolder}
      <div className="auth-container">
        {/* 左侧背景区域 */}
        <div className="left-side">
          <div className="logo-container">
            <img src={logoImg} alt="Logo" className="logo" />
          </div>
        </div>

        {/* 右侧登录区域 */}
        <div className="auth-box">
          <div className="login-form-container">
            <div className="system-title">
              <div className="main-title">北京中咨路捷工程咨询有限公司</div>
              <div className="main-title">知识管理系统</div>
              {/* <div className="sub-title">资产管理系统</div> */}
            </div>

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
                <Button
                  type="primary"
                  htmlType="submit"
                  block
                  size="large"
                  className="login-button"
                >
                  登录
                </Button>
              </Form.Item>
            </Form>
          </div>

          <div className="footer">Copyright © 2025 中咨路捷</div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
