// 运行时配置

// 定义消息接口
interface ChatMessage {
  content?: string;
  role?: string;
}

// 定义请求体接口
interface ChatRequestBody {
  messages?: ChatMessage[];
  action?: 'abridge' | 'rewrite' | 'extension' | 'chat';
  temperature?: number | null;
  model_name?: string;
  selected_contents?: string[];
  doc_id?: string;
}

// 保存原始的fetch方法
const originalFetch = window.fetch;

// 重写fetch方法
window.fetch = async function (...args) {
  let [resource, config = {} as RequestInit] = args;
  if (
    typeof resource === 'string' &&
    resource.includes('/api/v1/completions') &&
    config.method?.toLowerCase() === 'post' &&
    (typeof config.body === 'string'
      ? JSON.parse(config.body).temperature === null
      : config.body &&
        'temperature' in config.body &&
        config.body.temperature === null)
  ) {
    const modelName = localStorage.getItem('ai_chat_model');
    const token = localStorage.getItem('token');

    // 如果有token，添加到请求头
    if (token) {
      config.headers = {
        ...config.headers,
        Authorization: `Bearer ${token}`,
      };
    }

    if (modelName) {
      // 处理请求体
      let body: ChatRequestBody = {};
      try {
        if (typeof config.body === 'string') {
          body = JSON.parse(config.body) as ChatRequestBody;
        } else if (config.body instanceof FormData) {
          console.warn('FormData 不支持修改 model_name');
          return originalFetch(resource, config);
        } else {
          body = (config.body as ChatRequestBody) || {};
        }

        // 检查并处理 messages 中的 content
        if (body.messages && Array.isArray(body.messages)) {
          const needsAbridge = body.messages.some((msg: ChatMessage) =>
            msg.content?.includes(
              '</content>\n这句话的内容较长，帮我简化一下这个内容',
            ),
          );
          const needsRewrite = body.messages.some((msg: ChatMessage) =>
            msg.content?.includes(
              '</content>\n请帮我优化一下这段内容，并直接返回优化后的结果',
            ),
          );
          const needsExtension = body.messages.some((msg: ChatMessage) =>
            msg.content?.includes(
              '</content>\n这句话的内容较简短，帮我简单的优化和丰富一下内容',
            ),
          );
          const needsChat = body.messages.some((msg: ChatMessage) =>
            msg.content?.match(/^[^\n]*\n[^\n]*$/),
          );
          if (needsAbridge || needsRewrite || needsExtension || needsChat) {
            // 设置对应的 action
            if (needsAbridge) {
              body.action = 'abridge';
            } else if (needsRewrite) {
              body.action = 'rewrite';
            } else if (needsExtension) {
              body.action = 'extension';
            } else {
              body.action = 'chat';
            }

            // 处理 messages content
            const selectedContents: string[] = [];
            body.messages = body.messages.map((msg: ChatMessage) => {
              if (msg.content) {
                const contentMatch = msg.content.match(
                  /<content>(.*?)<\/content>/,
                );
                if (contentMatch) {
                  selectedContents.push(contentMatch[1]);
                  msg.content = '';
                }
                if (body.action === 'chat') {
                  let text = msg.content.split('\n');
                  msg.content = text[1];
                  selectedContents.push(text[0]);
                }
              }
              return msg;
            });
            body.selected_contents = selectedContents;
            body.doc_id = localStorage.getItem('current_document_id')!;
          }
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
    // if (
    //   typeof resource === 'string' &&
    //   resource.includes('/api/v1/completions') &&
    //   config.method?.toLowerCase() === 'post' &&
    //   (typeof config.body === 'string'
    //     ? JSON.parse(config.body).temperature === null
    //     : config.body &&
    //       'temperature' in config.body &&
    //       config.body.temperature === null) &&
    //   !response.headers.get('transfer-encoding')
    // ) {
    //   const clone = response.clone();
    //   const data = await clone.json();
    //   if (data.code !== 200) {
    //     message.error(data.message);
    //   }
    // }
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
