import { useEffect, useRef, useState } from "react";
import { AiEditor } from "aieditor";
import "aieditor/dist/style.css";
import "./custom.css";
import ExportBtnGroup from "./components/export-btn-group";
import { saveAsDocx, saveAsPdf } from "./utils";

function App() {
  const divRef = useRef(null);
  const [headings, setHeadings] = useState([]);
  const editorRef = useRef(null);
  const [showOutline, setShowOutline] = useState(true); // 控制目录显示/隐藏
  const [outlineWidth, setOutlineWidth] = useState(280); // 目录区宽度
  const [isDragging, setIsDragging] = useState(false); // 是否正在拖动分隔线
  const [lastSavedTime, setLastSavedTime] = useState(null);
  const STORAGE_KEY = "aieditor_content";
  const AUTOSAVE_DELAY = 1000; // 自动保存延迟（毫秒）
  const autoSaveTimerRef = useRef(null);

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

  // 保存内容到 localStorage
  const saveContent = (content) => {
    try {
      localStorage.setItem(STORAGE_KEY, content);
      setLastSavedTime(new Date());
    } catch (error) {
      console.error("Save content error:", error);
    }
  };

  // 从 localStorage 加载内容
  const loadContent = () => {
    try {
      const savedContent = localStorage.getItem(STORAGE_KEY);
      if (savedContent) {
        return savedContent;
      }
    } catch (error) {
      console.error("Load content error:", error);
      return ``;
    }
  };

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

  useEffect(() => {
    if (divRef.current) {
      // 加载缓存的内容
      const initialContent = loadContent();

      // 初始化时解析标题
      setHeadings(parseHeadings(initialContent));

      const aiEditor = new AiEditor({
        element: divRef.current,
        placeholder: "点击输入内容...",
        content: initialContent,
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
        onCreated: (editor) => {
          updateOutLine(editor);
          // 获取当前内容
          const content = editor.getHtml();

          // 创建临时 div 来解析内容
          const tempDiv = document.createElement("div");
          tempDiv.innerHTML = content;

          // 查找所有段落和标题元素
          const elements = tempDiv.querySelectorAll(
            "p, h1, h2, h3, h4, h5, h6"
          );

          // 检查每个元素的样式
          elements.forEach((element) => {
            const style = window.getComputedStyle(element);
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

          // 重新设置内容
          setTimeout(() => {
            editor.setContent(tempDiv.innerHTML);

            // 将光标移动到末尾
            editor.focusEnd();
          }, 100);
        },
        onChange: (editor) => {
          updateOutLine(editor);
          // 清除之前的定时器
          if (autoSaveTimerRef.current) {
            clearTimeout(autoSaveTimerRef.current);
          }

          // 获取编辑器内容
          const content = editor.getHtml();

          // 设置新的定时器
          autoSaveTimerRef.current = setTimeout(() => {
            saveContent(content);
          }, AUTOSAVE_DELAY);

          // 更新标题
          setHeadings(parseHeadings(content));
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
                icon: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor"><path d="M21 6.75736L19 8.75736V4H10V9H5V20H19V17.2426L21 15.2426V21.0082C21 21.556 20.5551 22 20.0066 22H3.9934C3.44476 22 3 21.5501 3 20.9932V8L9.00319 2H19.9978C20.5513 2 21 2.45531 21 2.9918V6.75736ZM21.7782 8.80761L23.1924 10.2218L15.4142 18L13.9979 17.9979L14 16.5858L21.7782 8.80761Z"></path></svg>`,
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
      editorRef.current = aiEditor;

      // 添加离线存储事件监听
      const handleBeforeUnload = () => {
        if (editorRef.current) {
          const content = editorRef.current.getHtml();
          saveContent(content);
        }
      };

      window.addEventListener("beforeunload", handleBeforeUnload);

      // 添加在线状态监听
      const handleOnline = () => {
        console.log("网络已连接");
      };

      const handleOffline = () => {
        if (editorRef.current) {
          const content = editorRef.current.getHtml();
          saveContent(content);
        }
        console.log("网络已断开，内容已保存");
      };

      window.addEventListener("online", handleOnline);
      window.addEventListener("offline", handleOffline);

      return () => {
        aiEditor.destroy();
        window.removeEventListener("beforeunload", handleBeforeUnload);
        window.removeEventListener("online", handleOnline);
        window.removeEventListener("offline", handleOffline);
        if (autoSaveTimerRef.current) {
          clearTimeout(autoSaveTimerRef.current);
        }
      };
    }
  }, []);

  // 点击目录项时滚动到对应位置
  const scrollToHeading = (id) => {
    if (editorRef.current) {
      const element = editorRef.current.getElement().querySelector(`#${id}`);
      if (element) {
        element.scrollIntoView({ behavior: "smooth" });
      }
    }
  };

  // 修改导出功能
  const handleExport = async (format) => {
    if (!editorRef.current) return;

    try {
      if (format === "pdf") {
        saveAsPdf();
        // 使用浏览器的打印功能
        /*
                window.print();
                */
      } else if (format === "docx") {
        const content = editorRef.current.getHtml();
        saveAsDocx(content);
        /*
                // 获取编辑器内容
                const content = editorRef.current.getHtml();
                
                // 创建一个完整的 HTML 文档
                const htmlContent = `
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="utf-8">
                        <title>售前方案写作助手</title>
                        <style>
                            body { font-family: Arial, sans-serif; }
                            img { max-width: 100%; }
                        </style>
                    </head>
                    <body>
                        ${content}
                    </body>
                    </html>
                `;
                
                // 创建 Blob 对象
                const blob = new Blob([htmlContent], { type: 'application/msword' });
                const url = window.URL.createObjectURL(blob);
                
                // 创建下载链接
                const a = document.createElement('a');
                a.href = url;
                a.download = '售前方案写作助手.doc';  // 使用 .doc 扩展名
                document.body.appendChild(a);
                a.click();
                
                // 清理
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
                */
      }
    } catch (error) {
      console.error("Export error:", error);
      alert("导出失败，请稍后重试");
    }
  };
  return (
    <div style={{ padding: 0, margin: 0, background: "#f3f4f6" }}>
      <div className="page-header">
        <h1>售前方案写作助手</h1>
        {lastSavedTime && (
          <span
            style={{
              marginLeft: "12px",
              fontSize: "12px",
              color: "#999",
            }}
          >
            {`最后保存: ${lastSavedTime.toLocaleTimeString()}`}
          </span>
        )}
        <ExportBtnGroup handleExport={handleExport}></ExportBtnGroup>
      </div>

      <div ref={divRef} style={{ padding: 0, margin: 0 }}>
        <div className="aie-container" style={{ backgroundColor: "#f3f4f6" }}>
          <div className="aie-header-panel">
            <div
              className="aie-container-header"
              style={{ background: "#fff" }}
            ></div>
          </div>
          <div className="aie-main">
            <div className="aie-directory-content">
              <div className="aie-directory">
                <h5>文档目录</h5>
                <div id="outline"></div>
              </div>
            </div>
            <div className="aie-container-panel">
              <div className="aie-container-main"></div>
            </div>
          </div>
          <div className="aie-container-footer"></div>
        </div>
      </div>
    </div>
  );
}

export default App;
