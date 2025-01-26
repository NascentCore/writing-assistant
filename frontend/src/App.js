import { useEffect, useRef, useState, useCallback } from "react";
import { AiEditor } from "aieditor";
import "aieditor/dist/style.css";
import "./custom.css";
import ExportBtnGroup from "./components/export-btn-group";
import { saveAsDocx, saveAsPdf } from "./utils";
import { debounce } from "lodash";
import { API_BASE_URL } from './config';
import LoginForm from './components/login-form';
import UserProfile from './components/user-profile';
import RegisterForm from './components/register-form';
import VersionHistory from './components/version-history';

// 添加常量
const CURRENT_DOC_KEY = 'current_document_id';


function App() {
  const divRef = useRef(null);
  const editorRef = useRef(null);
  const [headings, setHeadings] = useState([]);
  const [showOutline, setShowOutline] = useState(true); // 控制目录显示/隐藏
  const [outlineWidth, setOutlineWidth] = useState(280); // 目录区宽度
  const [isDragging, setIsDragging] = useState(false); // 是否正在拖动分隔线
  const [lastSavedTime, setLastSavedTime] = useState(null);
  const [showErrorDialog, setShowErrorDialog] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [pendingInput, setPendingInput] = useState(null);
  const [documents, setDocuments] = useState([]);
  const [currentDocId, setCurrentDocId] = useState(() => {
    return localStorage.getItem(CURRENT_DOC_KEY) || null;
  });
  const [showNewDocDialog, setShowNewDocDialog] = useState(false);
  const [newDocTitle, setNewDocTitle] = useState('');
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return !!localStorage.getItem('token');
  });
  const [showProfile, setShowProfile] = useState(false);
  const [showRegister, setShowRegister] = useState(false);
  const [showVersionHistory, setShowVersionHistory] = useState(false);

    // 添加文件类型和大小限制常量
    const ALLOWED_FILE_TYPES = {
        // 文档类型
        'text/markdown': { maxSize: 30 * 1024 * 1024, ext: 'md' },
        'text/plain': { maxSize: 30 * 1024 * 1024, ext: 'txt' },
        'application/pdf': { maxSize: 30 * 1024 * 1024, ext: 'pdf' },
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document': { maxSize: 30 * 1024 * 1024, ext: 'docx' },
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': { maxSize: 30 * 1024 * 1024, ext: 'xlsx' },
        'application/vnd.openxmlformats-officedocument.presentationml.presentation': { maxSize: 30 * 1024 * 1024, ext: 'pptx' },
        'message/rfc822': { maxSize: 30 * 1024 * 1024, ext: 'eml' },
        'text/csv': { maxSize: 30 * 1024 * 1024, ext: 'csv' },
        // 图片类型
        'image/jpeg': { maxSize: 5 * 1024 * 1024, ext: ['jpg', 'jpeg'] },
        'image/png': { maxSize: 5 * 1024 * 1024, ext: 'png' }
    };

    const MAX_TOTAL_SIZE = 125 * 1024 * 1024; // 125MB

    // 添加文件验证函数
    const validateFiles = (files) => {
        let totalSize = 0;
        const errors = [];
        const validFiles = [];

        for (const file of files) {
            // 检查文件类型
            const fileType = ALLOWED_FILE_TYPES[file.type];
            if (!fileType) {
                errors.push(`不支持的文件类型: ${file.name}`);
                continue;
            }

            // 检查文件大小
            if (file.size > fileType.maxSize) {
                const maxSizeMB = fileType.maxSize / (1024 * 1024);
                const isImage = file.type.startsWith('image/');
                errors.push(`${file.name} 超过${isImage ? '图片' : '文档'}大小限制 (${maxSizeMB}MB)`);
                continue;
            }

            totalSize += file.size;
            validFiles.push(file);
        }

        // 检查总大小
        if (totalSize > MAX_TOTAL_SIZE) {
            errors.push(`文件总大小超过限制 (125MB)`);
            return { valid: false, errors, files: [] };
        }

        return {
            valid: errors.length === 0,
            errors,
            files: validFiles
        };
    };

  // 修改拖动处理函数
  const handleMouseDown = (e) => {
    e.preventDefault(); // 防止文本选择
    e.stopPropagation();
    setIsDragging(true);
  };

  useEffect(() => {
    if (isDragging) {
      const handleMouseMove = (e) => {
        const newWidth = e.clientX;
        if (newWidth >= 200 && newWidth <= 500) {
          setOutlineWidth(newWidth);
        }
      };

      const handleMouseUp = () => {
        setIsDragging(false);
      };

      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);

      return () => {
        document.removeEventListener("mousemove", handleMouseMove);
        document.removeEventListener("mouseup", handleMouseUp);
      };
    }
  }, [isDragging]);

  // 添加标题解析函数
  const parseHeadings = (content) => {
    const tempDiv = document.createElement("div");
    tempDiv.innerHTML = content;

    // 获取所有标题元素
    const headingElements = tempDiv.querySelectorAll("h1, h2, h3, h4, h5, h6");

    // 转换为数组并提取信息
    const headingsArray = Array.from(headingElements).map((heading) => ({
      level: parseInt(heading.tagName[1]), // 获取标题级别
      text: heading.textContent,
      id: heading.id || Math.random().toString(36).substr(2, 9),
    }));

    // 处理缩进级别
    return headingsArray.map((heading, index) => {
      let indentLevel = 0;

      // 查找当前标题之前最近的标题级别
      for (let i = index - 1; i >= 0; i--) {
        if (headingsArray[i].level < heading.level) {
          // 找到上级标题，计算相对缩进
          indentLevel = heading.level - headingsArray[i].level;
          break;
        }
      }

      return {
        ...heading,
        indentLevel: indentLevel,
      };
    });
  };
  function updateOutLine(editor) {
    const outlineContainer = document.querySelector("#outline");
    while (outlineContainer?.firstChild) {
      outlineContainer.removeChild(outlineContainer.firstChild);
    }

    const outlines = editor.getOutline();
    for (let outline of outlines) {
      const child = document.createElement("div");
      child.classList.add(`aie-title${outline.level}`);
      child.style.marginLeft = `${14 * (outline.level - 1)}px`;
      child.innerHTML = `<a href="#${outline.id}">${outline.text}</a>`;
      child.addEventListener("click", (e) => {
        e.preventDefault();
        const el = editor.innerEditor.view.dom.querySelector(`#${outline.id}`);
        el.scrollIntoView({
          behavior: "smooth",
          block: "center",
          inline: "nearest",
        });
        setTimeout(() => {
          editor.focusPos(outline.pos + outline.size - 1);
        }, 1000);
      });
      outlineContainer?.appendChild(child);
    }
  }

  // 修改编辑器初始化代码
  useEffect(() => {
    // 只有在已认证状态下才初始化编辑器
    if (divRef.current && isAuthenticated) {
      const aiEditor = new AiEditor({
        element: divRef.current,
        placeholder: "点击输入内容...",
        content: "",
        toolbarKeys: [
          "undo",
          "redo",
          "brush",
          "eraser",
          "|",
          "heading",
          "font-family",
          "font-size",
          "|",
          "bold",
          "italic",
          "underline",
          "strike",
          "link",
          "code",
          "subscript",
          "superscript",
          "hr",
          "todo",
          "emoji",
          "|",
          "highlight",
          "font-color",
          "|",
          "align",
          "line-height",
          "|",
          "bullet-list",
          "ordered-list",
          "indent-decrease",
          "indent-increase",
          "break",
          "|",
          "image",
          "video",
          "attachment",
          "quote",
          "code-block",
          "table",
          "|",
          "source-code",
          "printer",
          "fullscreen",
          "ai",
        ],
        toolbarSize: "small",
        onCreated: async (editor) => {
          // 在编辑器创建完成后，如果有当前文档ID，就加载文档内容
          if (currentDocId) {
            try {
              const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents/` + currentDocId);
              if (response && response.ok) {
                const result = await response.json();
                const content = result.data.content || '';
                
                // 创建临时 div 来解析内容
                const tempDiv = document.createElement("div");
                tempDiv.innerHTML = content;

                // 查找所有段落和标题元素并处理样式
                const elements = tempDiv.querySelectorAll("p, h1, h2, h3, h4, h5, h6");
                elements.forEach((element) => {
                  const textAlign =
                    element.style.textAlign ||
                    element.getAttribute("data-text-align") ||
                    (element.classList.contains("is-style-text-align-center")
                      ? "center"
                      : "");

                  if (textAlign === "center") {
                    element.style.textAlign = "center";
                    element.setAttribute("data-text-align", "center");
                    element.classList.add("is-style-text-align-center");
                  }
                });

                // 设置内容并立即定位光标到开头
                editor.setContent(tempDiv.innerHTML);
                requestAnimationFrame(() => {
                  // 将所有可能的滚动容器都滚动到顶部
                  const editorElement = editor.innerEditor.view.dom;
                  const scrollContainers = [
                    editorElement.parentElement,
                    document.querySelector('.aie-container-panel'),
                    document.querySelector('.aie-container-main'),
                    document.querySelector('.aie-editor')
                  ];
                  
                  scrollContainers.forEach(container => {
                    if (container) {
                      container.scrollTop = 0;
                    }
                  });
                  
                  editor.focusStart();
                  updateOutLine(editor);
                });
              }
            } catch (error) {
              console.error('Fetch document error:', error);
            }
          } else {
            updateOutLine(editor);
          }
          
          // 添加快捷键监听
          const handleKeyDown = async (event) => {
            if (event.code === 'KeyU' && event.altKey) {
                event.preventDefault();
                event.stopPropagation();

                // 创建一个新的 input 元素
                const input = document.createElement('input');
                input.type = 'file';
                input.style.display = 'none';
                input.multiple = true;

                // 设置允许的文件类型
                const acceptedTypes = Object.entries(ALLOWED_FILE_TYPES)
                    .map(([mimeType, config]) => {
                        const exts = Array.isArray(config.ext) ? config.ext : [config.ext];
                        return [
                            mimeType,  // MIME 类型
                            ...exts.map(ext => `.${ext}`)  // 文件扩展名
                        ];
                    })
                    .flat()
                    .join(',');
                input.accept = acceptedTypes;

                // 处理文件选择
                input.onchange = async (e) => {
                    const files = Array.from(e.target.files || []);
                    
                    // 验证文件
                    const validation = validateFiles(files);
                    
                    // 如果有错误，显示错误信息并提供重试选项
                    if (validation.errors.length > 0) {
                        setErrorMessage(validation.errors.join('\n'));
                        setShowErrorDialog(true);
                        setPendingInput(input);  // 保存当前的 input 元素以供重用
                        return;
                    }

                    // 上传有效文件
                    for (const file of validation.files) {
                        try {
                            const formData = new FormData();
                            formData.append('files', file);

                            // 显示上传进度
                            const currentContent = editor.getHtml();
                            editor.setContent(currentContent + `<p>正在上传: ${file.name}...</p>`);

                            // 上传文件
                            const response = await fetch(`${API_BASE_URL}/api/v1/upload`, {
                                method: 'POST',
                                body: formData
                            });

                            if (!response.ok) {
                                throw new Error('Upload failed');
                            }

                            const data = await response.json();
                            
                            // 替换上传进度为文件链接
                            const content = editor.getHtml();
                            const newContent = content.replace(
                                `<p>正在上传: ${file.name}...</p>`,
                                `<p><a href="${data.url}" target="_blank">${file.name}</a></p>`
                            );
                            editor.setContent(newContent);
                        } catch (error) {
                            console.error('Upload error:', error);
                            const content = editor.getHtml();
                            const newContent = content.replace(
                                `<p>正在上传: ${file.name}...</p>`,
                                `<p style="color: red;">上传失败: ${file.name}</p>`
                            );
                            editor.setContent(newContent);
                        }
                    }

                    document.body.removeChild(input);
                };

                document.body.appendChild(input);
                input.click();
            }
          };

          // 将事件监听器添加到编辑器容器元素
          divRef.current.addEventListener('keydown', handleKeyDown);

          // 保存清理函数
          editor._cleanupKeyDown = () => {
            divRef.current?.removeEventListener('keydown', handleKeyDown);
          };
        },
        onChange: async (editor) => {
          // 更新大纲
          updateOutLine(editor);
          setHeadings(parseHeadings(editor.getHtml()));
          
          // 只有当内容是由用户编辑触发时才保存
          if (!editor._isSettingContent) {
            const content = editor.getHtml();
            debouncedSave(content);
          }
        },
        ai: {
          bubblePanelMenus:[
            {
                prompt: `<content>{content}</content>\n请帮我优化一下这段内容，并直接返回优化后的结果。\n注意：你应该先判断一下这句话是中文还是英文，如果是中文，请给我返回中文的内容，如果是英文，请给我返回英文内容，只需要返回内容即可，不需要告知我是中文还是英文。`,
                icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M15.1986 9.94447C14.7649 9.5337 14.4859 8.98613 14.4085 8.39384L14.0056 5.31138L11.275 6.79724C10.7503 7.08274 10.1433 7.17888 9.55608 7.06948L6.49998 6.50015L7.06931 9.55625C7.17871 10.1435 7.08257 10.7505 6.79707 11.2751L5.31121 14.0057L8.39367 14.4086C8.98596 14.4861 9.53353 14.7651 9.94431 15.1987L12.0821 17.4557L13.4178 14.6486C13.6745 14.1092 14.109 13.6747 14.6484 13.418L17.4555 12.0823L15.1986 9.94447ZM15.2238 15.5079L13.0111 20.1581C12.8687 20.4573 12.5107 20.5844 12.2115 20.442C12.1448 20.4103 12.0845 20.3665 12.0337 20.3129L8.49229 16.5741C8.39749 16.474 8.27113 16.4096 8.13445 16.3918L3.02816 15.7243C2.69958 15.6814 2.46804 15.3802 2.51099 15.0516C2.52056 14.9784 2.54359 14.9075 2.5789 14.8426L5.04031 10.3192C5.1062 10.1981 5.12839 10.058 5.10314 9.92253L4.16 4.85991C4.09931 4.53414 4.3142 4.22086 4.63997 4.16017C4.7126 4.14664 4.78711 4.14664 4.85974 4.16017L9.92237 5.10331C10.0579 5.12855 10.198 5.10637 10.319 5.04048L14.8424 2.57907C15.1335 2.42068 15.4979 2.52825 15.6562 2.81931C15.6916 2.88421 15.7146 2.95507 15.7241 3.02833L16.3916 8.13462C16.4095 8.2713 16.4739 8.39766 16.5739 8.49245L20.3127 12.0338C20.5533 12.2617 20.5636 12.6415 20.3357 12.8821C20.2849 12.9357 20.2246 12.9795 20.1579 13.0112L15.5078 15.224C15.3833 15.2832 15.283 15.3835 15.2238 15.5079ZM16.0206 17.435L17.4348 16.0208L21.6775 20.2634L20.2633 21.6776L16.0206 17.435Z"></path></svg>`,
                title: '改进写作',
            },
            {
                prompt: `<content>{content}</content>\n这句话的内容较简短，帮我简单的优化和丰富一下内容，并直接返回优化后的结果。注意：优化的内容不能超过原来内容的 2 倍。\n注意：你应该先判断一下这句话是中文还是英文，如果是中文，请给我返回中文的内容，如果是英文，请给我返回英文内容，只需要返回内容即可，不需要告知我是中文还是英文。`,
                icon: ` <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M20 2C20.5523 2 21 2.44772 21 3V6.757L19 8.757V4H5V20H19V17.242L21 15.242V21C21 21.5523 20.5523 22 20 22H4C3.44772 22 3 21.5523 3 21V3C3 2.44772 3.44772 2 4 2H20ZM21.7782 8.80761L23.1924 10.2218L15.4142 18L13.9979 17.9979L14 16.5858L21.7782 8.80761ZM13 12V14H8V12H13ZM16 8V10H8V8H16Z"></path></svg>`,
                title: '丰富内容',
            },
            {
                prompt: `<content>{content}</content>\n这句话的内容较长，帮我简化一下这个内容，并直接返回简化后的内容结果。\n注意：你应该先判断一下这句话是中文还是英文，如果是中文，请给我返回中文的内容，如果是英文，请给我返回英文内容，只需要返回内容即可，不需要告知我是中文还是英文。`,
                icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M21 6.75736L19 8.75736V4H10V9H5V20H19V17.242L21 15.242V21.0082C21 21.556 20.5551 22 20.0066 22H3.9934C3.44476 22 3 21.5501 3 20.9932V8L9.00319 2H19.9978C20.5513 2 21 2.45531 21 2.9918V6.75736ZM21.7782 8.80761L23.1924 10.2218L15.4142 18L13.9979 17.9979L14 16.5858L21.7782 8.80761Z"></path></svg>`,
                title: '简化内容',
            },
            {
                icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" d="M0 0h24v24H0z"></path><path d="M15 5.25C16.7949 5.25 18.25 3.79493 18.25 2H19.75C19.75 3.79493 21.2051 5.25 23 5.25V6.75C21.2051 6.75 19.75 8.20507 19.75 10H18.25C18.25 8.20507 16.7949 6.75 15 6.75V5.25ZM4 7C4 5.89543 4.89543 5 6 5H13V3H6C3.79086 3 2 4.79086 2 7V17C2 19.2091 3.79086 21 6 21H18C20.2091 21 22 19.2091 22 17V12H20V17C20 18.1046 19.1046 19 18 19H6C4.89543 19 4 18.1046 4 17V7Z"></path></svg>`,
                title: "整体编写方案",
                prompt: `请根据以下大纲编写一份完整的解决方案。要求：
1. 各部分内容要有逻辑关联
2. 突出方案的价值和创新点
3. 使用专业、准确的技术术语
4. 内容要具体、可落地
5. 保持整体结构的一致性
6. 各部分内容要详实且有深度

{content}

请按照大纲结构，生成完整的方案内容。要确保内容的专业性和可行性。并直接返回生成的内容结果。`,
            }
        ],
          models: {
            openai: {
              customUrl: "http://localhost:8000/api/v1/completions",
              model: "",
              apiKey: "",
            },
          },
        },
      });

      // 先保存对原始 setContent 方法的引用
      const originalSetContent = aiEditor.setContent.bind(aiEditor);
      
      // 然后再扩展 setContent 方法
      aiEditor.setContent = function(content) {
        this._isSettingContent = true;
        originalSetContent(content);
        requestAnimationFrame(() => {
          this._isSettingContent = false;
        });
      };

      editorRef.current = aiEditor;

      // 添加在线状态监听
      const handleOnline = () => {
        console.log("网络已连接");
      };

      const handleOffline = () => {
        console.log("网络已断开");
      };

      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);

      return () => {
        aiEditor.destroy();
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
      };
    }
  }, [currentDocId, isAuthenticated]);

  // 创建防抖的保存函数
  const debouncedSave = useCallback(
    debounce(async (content) => {
      if (!currentDocId) return;
      
      try {
        const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents/` + currentDocId, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ content }),
        });
        
        if (response && response.ok) {
          setLastSavedTime(new Date());
        }
      } catch (error) {
        console.error('Save error:', error);
      }
    }, 1000), // 1秒的延迟
    [currentDocId]
  );

  // 修改初始化用户文档的函数
  const initializeUserDocuments = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents`);
      if (response && response.ok) {
        const result = await response.json();
        setDocuments(result.data);
        
        if (result.data.length === 0) {
          // 如果没有文档，创建一个新文档
          const createResponse = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              title: '新建文档',
              content: ''
            }),
          });
          
          if (createResponse && createResponse.ok) {
            const createResult = await createResponse.json();
            setCurrentDocId(createResult.data.id);
            loadDocuments();
            
            setTimeout(() => {
              if (editorRef.current) {
                editorRef.current.setContent('');
                editorRef.current.focusStart();
              }
            }, 100);
          }
        } else {
          // 如果有文档，设置最近的文档为当前文档
          const mostRecentDoc = result.data[0]; // 因为文档列表已按更新时间降序排序
          setCurrentDocId(mostRecentDoc.id);
          
          // 等待编辑器初始化完成后加载文档内容
          setTimeout(() => {
            if (editorRef.current) {
              editorRef.current.focusStart();
            }
          }, 100);
        }
      }
    } catch (error) {
      console.error('Initialize documents error:', error);
    }
  };

  // 修改登录和注册处理函数
  const handleLogin = async (token) => {
    localStorage.setItem('token', token);
    setIsAuthenticated(true);
    await new Promise(resolve => setTimeout(resolve, 0));
    await initializeUserDocuments();
  };

  const handleRegister = async (token) => {
    localStorage.setItem('token', token);
    setIsAuthenticated(true);
    await new Promise(resolve => setTimeout(resolve, 0));
    await initializeUserDocuments();
  };

  // 添加登出处理函数
  const handleLogout = () => {
    localStorage.removeItem('token');
    setIsAuthenticated(false);
    setCurrentDocId(null);
  };

  // 修改 fetch 请求，添加认证头
  const fetchWithAuth = async (url, options = {}) => {
    const token = localStorage.getItem('token');
    const headers = {
      ...options.headers,
      'Authorization': `Bearer ${token}`,
    };

    const response = await fetch(url, { ...options, headers });
    if (response.status === 401) {
      // 如果认证失败，清除 token 并重定向到登录页
      localStorage.removeItem('token');
      setIsAuthenticated(false);
      return null;
    }
    return response;
  };

  // 修改 loadDocuments 函数
  const loadDocuments = async () => {
    try {
      const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents`);
      if (response && response.ok) {
        const result = await response.json();
        setDocuments(result.data);
        
        // 如果没有当前选中的文档，但有文档列表，则选择最近的文档
        if (!currentDocId && result.data.length > 0) {
          const mostRecentDoc = result.data[0];
          setCurrentDocId(mostRecentDoc.id);
        } else if (currentDocId) {
          // 验证当前文档是否存在于列表中
          const docExists = result.data.some(doc => doc.id === parseInt(currentDocId));
          if (!docExists && result.data.length > 0) {
            // 如果当前文档不存在，选择最近的文档
            setCurrentDocId(result.data[0].id);
          }
        }
      }
    } catch (error) {
      console.error('Load documents error:', error);
    }
  };

  // 修改组件加载时的 useEffect
  useEffect(() => {
    // 只在已认证状态下加载文档
    if (isAuthenticated) {
      loadDocuments();
    }
  }, [isAuthenticated]); // 添加 isAuthenticated 到依赖数组

  // 修改重命名函数
  const handleRename = async (docId, currentTitle) => {
    const newTitle = prompt('请输入新的文档名称:', currentTitle);
    if (newTitle && newTitle.trim() && newTitle !== currentTitle) {
      try {
        const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents/` + docId, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ title: newTitle.trim() }),
        });
        
        if (response && response.ok) {
          loadDocuments();
        }
      } catch (error) {
        console.error('Rename document error:', error);
        alert('重命名失败');
      }
    }
  };

  // 修改删除函数
  const handleDelete = async (docId) => {
    if (window.confirm('确定要删除这个文档吗？')) {
      try {
        const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents/` + docId, {
          method: 'DELETE',
        });
        
        if (response && response.ok) {
          if (currentDocId === docId) {
            setCurrentDocId(null);
          }
          loadDocuments();
        }
      } catch (error) {
        console.error('Delete document error:', error);
        alert('删除失败');
      }
    }
  };

  // 修改文档列表渲染函数
  const renderDocumentList = () => {
    return (
        <div className="document-list">
            {documents.map(doc => {
                const isActive = currentDocId && Number(currentDocId) === doc.id;
                return (
                    <div 
                        key={doc.id} 
                        className={`document-item ${isActive ? 'active' : ''}`}
                        onClick={() => setCurrentDocId(doc.id.toString())}
                    >
                        <span className="doc-title">
                            {doc.title}
                        </span>
                        <div className="doc-info">
                            <span className="doc-time">{doc.updated_at}</span>
                            <div className="doc-actions">
                                <button 
                                    className="doc-action-btn"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleRename(doc.id, doc.title);
                                    }}
                                >
                                    重命名
                                </button>
                                <button 
                                    className="doc-action-btn delete"
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        handleDelete(doc.id);
                                    }}
                                >
                                    删除
                                </button>
                            </div>
                        </div>
                    </div>
                );
            })}
        </div>
    );
  };

  // 修改新建文档函数
  const handleNewDocument = async () => {
    if (!newDocTitle.trim()) {
        alert('请输入文档标题');
        return;
    }

    try {
        const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                title: newDocTitle,
                content: ''
            }),
        });

        const result = await response.json();

        if (response.ok) {
            // 清理对话框状态
            setShowNewDocDialog(false);
            setNewDocTitle('');
            
            try {
                // 更新文档列表
                const docsResponse = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents`);
                if (docsResponse.ok) {
                    const docsResult = await docsResponse.json();
                    
                    // 更新文档列表
                    setDocuments(docsResult.data);
                    
                    // 找到新创建的文档（根据标题匹配）
                    if (docsResult.data) {
                        const newDoc = docsResult.data.find(doc => doc.title === newDocTitle.trim());
                        if (newDoc) {
                            setCurrentDocId(newDoc.id.toString());
                        }
                    }
                }
                
                // 确保编辑器被清空并获得焦点
                if (editorRef.current) {
                    editorRef.current.setContent('');
                    editorRef.current.focusStart();
                }
            } catch (error) {
                console.error('Failed to fetch documents:', error);
            }
        } else {
            throw new Error(result.message || '创建文档失败');
        }
    } catch (error) {
        console.error('Create document error:', error);
        alert(error.message || '创建文档失败，请稍后重试');
    }
  };

  // 添加导出功能
  const handleExport = async (format) => {
    if (!editorRef.current) return;

    try {
      if (format === "pdf") {
        saveAsPdf();
      } else if (format === "docx") {
        const content = editorRef.current.getHtml();
        saveAsDocx(content);
      }
    } catch (error) {
      console.error("Export error:", error);
      alert("导出失败，请稍后重试");
    }
  };

  // 监听 currentDocId 变化，保存到 localStorage
  useEffect(() => {
    if (currentDocId) {
      localStorage.setItem(CURRENT_DOC_KEY, currentDocId);
    } else {
      localStorage.removeItem(CURRENT_DOC_KEY);
    }
  }, [currentDocId]);

  return (
    <div style={{ padding: 0, margin: 0, background: "#f3f4f6" }}>
      {!isAuthenticated ? (
        showRegister ? (
          <RegisterForm 
            onRegister={handleRegister}
            onSwitchToLogin={() => setShowRegister(false)}
          />
        ) : (
          <LoginForm 
            onLogin={handleLogin}
            onSwitchToRegister={() => setShowRegister(true)}
          />
        )
      ) : (
        <>
          <div className="page-header">
            <h1>售前方案写作助手</h1>
            <div className="header-buttons">
              <button 
                onClick={() => setShowNewDocDialog(true)}
                className="new-doc-btn"
              >
                新建文档
              </button>
              <ExportBtnGroup handleExport={handleExport} />
              {currentDocId && (
                <button 
                  className="history-btn"
                  onClick={() => setShowVersionHistory(true)}
                >
                  版本历史
                </button>
              )}
              
              <div className="user-buttons">
                <button 
                  className="profile-btn"
                  onClick={() => setShowProfile(true)}
                >
                  个人信息
                </button>
                <button 
                  onClick={handleLogout}
                  className="logout-btn"
                >
                  退出登录
                </button>
              </div>
            </div>
          </div>

          {/* 添加个人信息对话框 */}
          {showProfile && (
            <UserProfile onClose={() => setShowProfile(false)} />
          )}

          {/* 新建文档对话框 */}
          {showNewDocDialog && (
            <div className="dialog-overlay">
              <div className="dialog">
                <h2>新建文档</h2>
                <input
                  type="text"
                  value={newDocTitle}
                  onChange={(e) => setNewDocTitle(e.target.value)}
                  placeholder="请输入文档标题"
                />
                <div className="dialog-buttons">
                  <button onClick={handleNewDocument}>确定</button>
                  <button onClick={() => setShowNewDocDialog(false)}>取消</button>
                </div>
              </div>
            </div>
          )}

          {showVersionHistory && currentDocId && (
            <VersionHistory
              docId={currentDocId}
              onClose={() => setShowVersionHistory(false)}
              onRollback={async () => {
                loadDocuments();
                if (editorRef.current) {
                  try {
                    const response = await fetchWithAuth(`${API_BASE_URL}/api/v1/documents/` + currentDocId);
                    if (response && response.ok) {
                      const result = await response.json();
                      editorRef.current.setContent(result.data.content || '');
                    }
                  } catch (error) {
                    console.error('Load document content error:', error);
                  }
                }
              }}
            />
          )}

          <div ref={divRef} style={{ padding: 0, margin: 0 }}>
            <div className="aie-container" style={{ backgroundColor: "#f3f4f6" }}>
              <div className="aie-header-panel">
                <div className="aie-container-header" style={{ background: "#fff" }}></div>
              </div>
              <div className="aie-main">
                <div className="aie-directory-content">
                  <div className="aie-directory">
                    <h5>我的文档</h5>
                    {renderDocumentList()}
                  </div>
                </div>
                <div className="aie-container-panel">
                  <div className="aie-container-main"></div>
                </div>
                <div className="aie-outline">
                  <h5>文档目录</h5>
                  <div id="outline"></div>
                </div>
              </div>
              <div className="aie-container-footer"></div>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

export default App;
