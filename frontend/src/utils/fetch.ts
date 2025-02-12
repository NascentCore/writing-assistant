import { API_BASE_URL } from '@/config';
import { message } from 'antd';

// 老的接口通用接口请求，不要再用了
export const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
  const token = localStorage.getItem('token');
  const headers = {
    ...(options.headers as Record<string, string>),
    Authorization: `Bearer ${token}`,
  };

  // 检查 URL 是否以 http:// 或 https:// 开头
  const fullUrl =
    url.startsWith('http://') || url.startsWith('https://')
      ? url
      : `${API_BASE_URL}${url.startsWith('/') ? '' : '/'}${url}`;

  const response = await fetch(fullUrl, { ...options, headers });
  if (response.status === 401) {
    // 如果认证失败，清除 token
    localStorage.removeItem('token');
    // 重新加载页面以重定向到登录页
    window.location.href = '/login';
    return null;
  }
  return response;
};

// 创建带认证的 fetch 函数
export const fetchWithAuthNew = async (
  url: string,
  options: RequestInit = {},
) => {
  const token = localStorage.getItem('token');
  const headers = {
    ...(options.headers as Record<string, string>),
    Authorization: `Bearer ${token}`,
  };

  // 检查 URL 是否以 http:// 或 https:// 开头
  const fullUrl =
    url.startsWith('http://') || url.startsWith('https://')
      ? url
      : `${API_BASE_URL}${url.startsWith('/') ? '' : '/'}${url}`;

  const response = await fetch(fullUrl, { ...options, headers });
  if (response.status === 401) {
    // 如果认证失败，清除 token
    localStorage.removeItem('token');
    // 重新加载页面以重定向到登录页
    window.location.href = '/login';
    return null;
  }
  if (response.ok) {
    const result = await response.json();
    return result?.data;
  } else {
    message.error('请求失败');
    return;
  }
};
