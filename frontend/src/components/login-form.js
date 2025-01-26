import React, { useState } from 'react';
import { API_BASE_URL } from '../config';
import '../styles/auth.css';

const LoginForm = ({ onLogin, onSwitchToRegister }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
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
        localStorage.setItem('token', data.access_token);
        onLogin(data.access_token);
      } else {
        const error = await response.json();
        setError(error.detail || '登录失败');
      }
    } catch (error) {
      setError('登录失败，请稍后重试');
    }
  };

  return (
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
          没有账号？ <button onClick={onSwitchToRegister}>去注册</button>
        </div>
      </div>
    </div>
  );
};

export default LoginForm; 