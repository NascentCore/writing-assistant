import { API_BASE_URL } from '@/config';
import React, { useState } from 'react';
import './index.less';

const RegisterPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (
    e: React.FormEvent<HTMLFormElement>,
  ): Promise<void> => {
    e.preventDefault();
    setError('');

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username,
          email,
          password,
        }),
      });

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem('token', data.access_token);
        // 注册成功后跳转到编辑器主页
        window.location.href = '/';
      } else {
        const errorData = await response.json();
        setError(errorData.detail || '注册失败');
      }
    } catch (error) {
      setError('注册失败，请稍后重试');
    }
  };

  return (
    <div className="register-container-forUni">
      <div className="auth-container">
        <div className="auth-box">
          <h2>注册</h2>
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
              <label>邮箱</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
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
            <button type="submit">注册</button>
          </form>
          <div className="auth-switch">
            已有账号？{' '}
            <button
              type="button"
              onClick={() => (window.location.href = '/login')}
            >
              去登录
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RegisterPage;
