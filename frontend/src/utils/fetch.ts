// 创建带认证的 fetch 函数
export const fetchWithAuth = async (url: string, options: RequestInit = {}) => {
  const token = localStorage.getItem('token');
  const headers = {
    ...(options.headers as Record<string, string>),
    Authorization: `Bearer ${token}`,
  };

  const response = await fetch(url, { ...options, headers });
  if (response.status === 401) {
    // 如果认证失败，清除 token
    localStorage.removeItem('token');
    // 重新加载页面以重定向到登录页
    window.location.href = '/login';
    return null;
  }
  return response;
};
