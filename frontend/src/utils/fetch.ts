import { API_BASE_URL } from '@/config';
import type { RequestOptions } from '@umijs/max';
import { request } from '@umijs/max';
import { message } from 'antd';

interface ApiResponse<T = any> {
  code: number;
  data: T;
  message: string;
}

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

// 创建带认证的 request 函数
export const fetchWithAuthNew = async <T = any>(
  url: string,
  options: RequestOptions = {},
  originData?: boolean,
) => {
  const token = localStorage.getItem('token');
  const fullUrl =
    url.startsWith('http://') || url.startsWith('https://')
      ? url
      : `${API_BASE_URL}${url.startsWith('/') ? '' : '/'}${url}`;

  try {
    if (originData) {
      return await request<ApiResponse<T>>(fullUrl, {
        ...options,
        headers: {
          ...(options.headers || {}),
          Authorization: `Bearer ${token}`,
        },
        getResponse: true,
        responseType: 'stream', // 添加 responseType 为 stream
      });
    }

    const response = await request<ApiResponse<T>>(fullUrl, {
      ...options,
      headers: {
        ...(options.headers || {}),
        Authorization: `Bearer ${token}`,
      },
    });

    // 处理返回值，保持原有逻辑
    if (response.code !== 200) {
      message.error(response.message);
    }
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
      return null;
    }
    message.error(error.message || '请求失败');
    return;
  }
};

// 创建带认证的 fetch 函数
export const fetchWithAuthStream = async (
  url: string,
  options: RequestInit = {},
  originData?: boolean,
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
    if (originData) {
      return response;
    }
    const result = await response.json();
    if (result.code !== 200) {
      message.error(result.message);
    }
    return result?.data;
  } else {
    message.error('请求失败');
    return;
  }
};
