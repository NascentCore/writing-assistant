import { API_BASE_URL } from '@/config';
import React, { useState } from 'react';
import './index.less';

const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (
    e: React.FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    e.preventDefault();
    setError('');

    try {
      const formData = new FormData();
      formData.append('username', username);
      formData.append('password', password);

      const response = await fetch(`${API_BASE_URL}/api/v1/token`, {
        method: 'POST',
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('token', data.data.access_token);
        // 登录成功后跳转到编辑器主页
        window.location.href = '/';
      } else {
        const errorData = await response.json();
        setError(errorData.detail || '登录失败');
      }
    } catch (error) {
      setError('登录失败，请稍后重试');
    }
  };

  return (
    <div className="login-container-forUni">
      <div className="auth-container">
        <div className="auth-box">
          <h2>登录</h2>
          {error && <div className="error-message">{error}</div>}
          <form onSubmit={handleSubmit}>
            <div className="form-group">
              <label>用户名</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label>密码</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <button type="submit">登录</button>
          </form>
          <div className="auth-switch">
            没有账号？
            <button
              type="button"
              onClick={() => (window.location.href = '/register')}
            >
              去注册
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
