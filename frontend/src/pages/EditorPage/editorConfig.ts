import { API_BASE_URL } from '@/config';

// 添加文件类型和大小限制的接口
export interface FileTypeConfig {
  maxSize: number;
  ext: string | string[];
}

export interface FileTypes {
  [key: string]: FileTypeConfig;
}

// 添加文件类型和大小限制常量
export const ALLOWED_FILE_TYPES: FileTypes = {
  // 文档类型
  'text/markdown': { maxSize: 30 * 1024 * 1024, ext: 'md' },
  'text/plain': { maxSize: 30 * 1024 * 1024, ext: 'txt' },
  'application/pdf': { maxSize: 30 * 1024 * 1024, ext: 'pdf' },
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': {
    maxSize: 30 * 1024 * 1024,
    ext: 'docx',
  },
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': {
    maxSize: 30 * 1024 * 1024,
    ext: 'xlsx',
  },
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': {
    maxSize: 30 * 1024 * 1024,
    ext: 'pptx',
  },
  'message/rfc822': { maxSize: 30 * 1024 * 1024, ext: 'eml' },
  'text/csv': { maxSize: 30 * 1024 * 1024, ext: 'csv' },
  // 图片类型
  'image/jpeg': { maxSize: 5 * 1024 * 1024, ext: ['jpg', 'jpeg'] },
  'image/png': { maxSize: 5 * 1024 * 1024, ext: 'png' },
};

export const MAX_TOTAL_SIZE = 125 * 1024 * 1024; // 125MB

export const toolbarKeys = [
  'undo',
  'redo',
  'brush',
  'eraser',
  '|',
  'heading',
  'font-family',
  'font-size',
  '|',
  'bold',
  'strike',
  'link',
  '|',
  'highlight',
  'font-color',
  '|',
  'align',
  'line-height',
  '|',
  'image',
  'video',
  'attachment',
  'table',
  '|',
  'source-code',
  'printer',
  'fullscreen',
  'ai',
];

export const aiConfig = {
  bubblePanelMenus: [
    {
      prompt: `<content>{content}</content>\n请帮我优化一下这段内容，并直接返回优化后的结果。\n注意：你应该先判断一下这句话是中文还是英文，如果是中文，请给我返回中文的内容，如果是英文，请给我返回英文内容，只需要返回内容即可，不需要告知我是中文还是英文。`,
      icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M15.1986 9.94447C14.7649 9.5337 14.4859 8.98613 14.4085 8.39384L14.0056 5.31138L11.275 6.79724C10.7503 7.08274 10.1433 7.17888 9.55608 7.06948L6.49998 6.50015L7.06931 9.55625C7.17871 10.1435 7.08257 10.7505 6.79707 11.2751L5.31121 14.0057L8.39367 14.4086C8.98596 14.4861 9.53353 14.7651 9.94431 15.1987L12.0821 17.4557L13.4178 14.6486C13.6745 14.1092 14.109 13.6747 14.6484 13.418L17.4555 12.0823L15.1986 9.94447ZM15.2238 15.5079L13.0111 20.1581C12.8687 20.4573 12.5107 20.5844 12.2115 20.442C12.1448 20.4103 12.0845 20.3665 12.0337 20.3129L8.49229 16.5741C8.39749 16.474 8.27113 16.4096 8.13445 16.3918L3.02816 15.7243C2.69958 15.6814 2.46804 15.3802 2.51099 15.0516C2.52056 14.9784 2.54359 14.9075 2.5789 14.8426L5.04031 10.3192C5.1062 10.1981 5.12839 10.058 5.10314 9.92253L4.16 4.85991C4.09931 4.53414 4.3142 4.22086 4.63997 4.16017C4.7126 4.14664 4.78711 4.14664 4.85974 4.16017L9.92237 5.10331C10.0579 5.12855 10.198 5.10637 10.319 5.04048L14.8424 2.57907C15.1335 2.42068 15.4979 2.52825 15.6562 2.81931C15.6916 2.88421 15.7146 2.95507 15.7241 3.02833L16.3916 8.13462C16.4095 8.2713 16.4739 8.39766 16.5739 8.49245L20.3127 12.0338C20.5533 12.2617 20.5636 12.6415 20.3357 12.8821C20.2849 12.9357 20.2246 12.9795 20.1579 13.0112L15.5078 15.224C15.3833 15.2832 15.283 15.3835 15.2238 15.5079ZM16.0206 17.435L17.4348 16.0208L21.6775 20.2634L20.2633 21.6776L16.0206 17.435Z"></path></svg>`,
      title: '改进',
    },
    {
      prompt: `<content>{content}</content>\n这句话的内容较简短，帮我简单的优化和丰富一下内容，并直接返回优化后的结果。注意：优化的内容不能超过原来内容的 2 倍。\n注意：你应该先判断一下这句话是中文还是英文，如果是中文，请给我返回中文的内容，如果是英文，请给我返回英文内容，只需要返回内容即可，不需要告知我是中文还是英文。`,
      icon: ` <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2C20.5523 2 21 2.44772 21 3V6.757L19 8.757V4H5V20H19V17.242L21 15.242V21C21 21.5523 20.5523 22 20 22H4C3.44772 22 3 21.5523 3 21V3C3 2.44772 3.44772 2 4 2H20ZM21.7782 8.80761L23.1924 10.2218L15.4142 18L13.9979 17.9979L14 16.5858L21.7782 8.80761ZM13 12V14H8V12H13ZM16 8V10H8V8H16Z"></path></svg>`,
      title: '扩写',
    },
    {
      prompt: `<content>{content}</content>\n这句话的内容较长，帮我简化一下这个内容，并直接返回简化后的内容结果。\n注意：你应该先判断一下这句话是中文还是英文，如果是中文，请给我返回中文的内容，如果是英文，请给我返回英文内容，只需要返回内容即可，不需要告知我是中文还是英文。`,
      icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M21 6.75736L19 8.75736V4H10V9H5V20H19V17.242L21 15.242V21.0082C21 21.556 20.5551 22 20.0066 22H3.9934C3.44476 22 3 21.5501 3 20.9932V8L9.00319 2H19.9978C20.5513 2 21 2.45531 21 2.9918V6.75736ZM21.7782 8.80761L23.1924 10.2218L15.4142 18L13.9979 17.9979L14 16.5858L21.7782 8.80761Z"></path></svg>`,
      title: '缩写',
    },
    {
      icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" d="M0 0h24v24H0z"></path><path d="M15 5.25C16.7949 5.25 18.25 3.79493 18.25 2H19.75C19.75 3.79493 21.2051 5.25 23 5.25V6.75C21.2051 6.75 19.75 8.20507 19.75 10H18.25C18.25 8.20507 16.7949 6.75 15 6.75V5.25ZM4 7C4 5.89543 4.89543 5 6 5H13V3H6C3.79086 3 2 4.79086 2 7V17C2 19.2091 3.79086 21 6 21H18C20.2091 21 22 19.2091 22 17V12H20V17C20 18.1046 19.1046 19 18 19H6C4.89543 19 4 18.1046 4 17V7Z"></path></svg>`,
      title: '整体编写方案',
      prompt: `请根据以下大纲编写一份完整的解决方案。要求：
1. 各部分内容要有逻辑关联
2. 突出方案的价值和创新点
3. 使用专业、准确的技术术语
4. 内容要具体、可落地
5. 保持整体结构的一致性
6. 各部分内容要详实且有深度

{content}

请按照大纲结构，生成完整的方案内容。要确保内容的专业性和可行性。并直接返回生成的内容结果。`,
    },
  ],
  models: {
    openai: {
      customUrl: `${API_BASE_URL}/api/v1/completions`,
      model: '',
      apiKey: '',
    },
  } as any,
};

export interface EditorConfig {
  element: HTMLElement;
  placeholder: string;
  content: string;
  toolbarKeys: string[];
  toolbarSize: 'medium' | 'small' | 'large';
  ai: typeof aiConfig;
}

export function getEditorConfig(element: HTMLElement): EditorConfig {
  return {
    element,
    placeholder: '开始写作...',
    content: '',
    toolbarKeys,
    toolbarSize: 'medium' as const,
    ai: aiConfig,
  };
}
