import React, { useState, useEffect } from 'react';
import { API_BASE_URL } from '../config';
import '../styles/user-profile.css';


const UserProfile = ({ onClose }) => {
  const [user, setUser] = useState(null);
  const [email, setEmail] = useState('');
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchUserInfo();
  }, []);

  const fetchUserInfo = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });
      if (response.ok) {
        const data = await response.json();
        setUser(data);
        setEmail(data.email);
      }
    } catch (error) {
      setError('获取用户信息失败');
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setMessage('');

    const updateData = {};
    if (email !== user.email) updateData.email = email;
    if (currentPassword && newPassword) {
      updateData.current_password = currentPassword;
      updateData.new_password = newPassword;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/users/me`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(updateData),
      });

      if (response.ok) {
        setMessage('更新成功');
        setCurrentPassword('');
        setNewPassword('');
        fetchUserInfo();
      } else {
        const error = await response.json();
        setError(error.detail || '更新失败');
      }
    } catch (error) {
      setError('更新失败，请稍后重试');
    }
  };

  const fetchUserProfile = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/user/profile`, {
        // ... 其他配置
      });
      // ... 其他代码
    } catch (error) {
      // ... 错误处理
    }
  };

  const updateProfile = async (data) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/user/profile`, {
        // ... 其他配置
      });
      // ... 其他代码
    } catch (error) {
      // ... 错误处理
    }
  };

  return (
    <div className="profile-overlay">
      <div className="profile-box">
        <h2>个人信息</h2>
        {error && <div className="error-message">{error}</div>}
        {message && <div className="success-message">{message}</div>}
        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>用户名</label>
            <input type="text" value={user?.username || ''} disabled />
          </div>
          <div className="form-group">
            <label>邮箱</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>当前密码</label>
            <input
              type="password"
              value={currentPassword}
              onChange={(e) => setCurrentPassword(e.target.value)}
            />
          </div>
          <div className="form-group">
            <label>新密码</label>
            <input
              type="password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </div>
          <div className="button-group">
            <button type="submit">保存</button>
            <button type="button" onClick={onClose}>取消</button>
          </div>
        </form>
      </div>
    </div>
  );
};

export default UserProfile; 