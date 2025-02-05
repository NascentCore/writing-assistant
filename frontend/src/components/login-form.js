import React, { useState, useEffect, useRef } from 'react';
import { API_BASE_URL } from '../config';
import '../styles/auth.css';

const LoginForm = ({ onLogin, onSwitchToRegister }) => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const loginButtonRef = useRef(null);
  const mounted = useRef(true);

  useEffect(() => {
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (mounted.current && loginButtonRef.current) {
        handleLogin();
      }
    }, 100);

    return () => {
      clearTimeout(timer);
    };
  }, []);

  const handleLogin = async () => {
    if (!mounted.current) return;
    
    try {
      // 创建 FormData 对象
      const formData = new URLSearchParams();
      formData.append('username', 'admin');
      formData.append('password', '123456');
      formData.append('grant_type', 'password');

      const response = await fetch(`${API_BASE_URL}/api/v1/token`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData
      });

      if (!mounted.current) return;

      if (response.ok) {
        const data = await response.json();
        if (!mounted.current) return;
        
        localStorage.setItem('token', data.access_token);
        onLogin(data.access_token);
      } else {
        const error = await response.json();
        if (mounted.current) {
          setError(error.detail || '登录失败');
        }
      }
    } catch (error) {
      if (mounted.current) {
        setError('登录失败，请稍后重试');
      }
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-box" style={{ display: 'none' }}>
        {error && <div className="error-message">{error}</div>}
        <button 
          ref={loginButtonRef}
          onClick={handleLogin}
          style={{ display: 'none' }}
        >
          登录
        </button>
      </div>
    </div>
  );
};

export default LoginForm; 