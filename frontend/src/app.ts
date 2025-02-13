// 运行时配置

// 保存原始的fetch方法
const originalFetch = window.fetch;

// 重写fetch方法
window.fetch = async function (...args) {
  let [resource, config = {}] = args;
  console.log('🚀 ~ args:', args);
  if (
    typeof resource === 'string' &&
    resource.includes('/api/v1/completions') &&
    config.method?.toLowerCase() === 'post'
  ) {
    const modelName = localStorage.getItem('ai_chat_model');
    if (modelName) {
      // 处理请求体
      let body = {};
      try {
        if (typeof config.body === 'string') {
          body = JSON.parse(config.body);
        } else if (config.body instanceof FormData) {
          console.warn('FormData 不支持修改 model_name');
          return originalFetch(resource, config);
        } else {
          body = config.body || {};
        }

        config.body = JSON.stringify({
          ...body,
          model_name: modelName,
        });
      } catch (error) {
        console.error('处理请求体失败:', error);
      }
    }
  }

  // 发起请求
  try {
    const response = await originalFetch(resource, config);
    return response;
  } catch (error) {
    console.error('请求错误:', error);
    throw error;
  }
};

// 全局初始化数据配置，用于 Layout 用户信息和权限初始化
// 更多信息见文档：https://umijs.org/docs/api/runtime-config#getinitialstate
export async function getInitialState(): Promise<{ name: string }> {
  return { name: '@umijs/max' };
}

// 配置路由跳转逻辑
export function onRouteChange({
  location,
}: {
  location: { pathname: string };
}) {
  if (location.pathname === '/') {
    window.location.href = '/EditorPage';
  }
}

// 需要现在 umi 开启布局
// export const layout = () => {
//   return {
//     logo: 'https://img.alicdn.com/tfs/TB1YHEpwUT1gK0jSZFhXXaAtVXa-28-27.svg',
//     menu: {
//       locale: false,
//     },
//   };
// };
