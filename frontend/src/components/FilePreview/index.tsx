import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons';
import {
  Button,
  Input,
  message,
  Modal,
  Popover,
  Space,
  Spin,
  Tooltip,
} from 'antd';
import * as docx from 'docx-preview';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { FilePreviewProps, SupportedFileType } from './type';

// 配置 PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

// 检查 docx-preview 是否正确导入
console.log('docx-preview 可用方法:', Object.keys(docx || {}));

// 添加一个测试文件响应的函数
async function testFileResponse(url: string): Promise<void> {
  try {
    console.log('正在测试文件响应:', url);
    const response = await fetch(url, { method: 'HEAD' });
    console.log('文件响应状态:', response.status, response.statusText);
    console.log('响应头:', [...response.headers.entries()]);

    // 如果有跨域问题，尝试普通的 GET 请求
    if (!response.ok) {
      const fullResponse = await fetch(url);
      console.log('完整 GET 响应状态:', fullResponse.status);
      console.log('内容类型:', fullResponse.headers.get('content-type'));
      console.log('响应大小可用:', fullResponse.headers.has('content-length'));

      if (fullResponse.headers.has('content-length')) {
        console.log(
          '响应大小:',
          fullResponse.headers.get('content-length'),
          'bytes',
        );
      }
    }
  } catch (error) {
    console.error('测试文件响应时出错:', error);
  }
}

const FilePreview: React.FC<FilePreviewProps> = ({
  open,
  onCancel,
  fetchFile,
  fileName,
}) => {
  const [fileData, setFileData] = useState<string>();
  const [numPages, setNumPages] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const docxContainerRef = useRef<HTMLDivElement>(null);
  const pdfContainerRef = useRef<HTMLDivElement>(null);
  const [windowWidth, setWindowWidth] = useState(window.innerWidth);
  const [pdfScale, setPdfScale] = useState<number>(1);
  const [isFullscreen, setIsFullscreen] = useState<boolean>(false);
  const [pageInputValue, setPageInputValue] = useState<string>('1');
  const [docxScale, setDocxScale] = useState<number>(1);

  useEffect(() => {
    if (open) {
      setLoading(true);
      setError(null);
      setCurrentPage(1);
      setPageInputValue('1');
      fetchFile()
        .then((data) => {
          console.log('获取到文件 URL:', data ? '成功' : '失败');
          setFileData(data);

          // 如果有 URL，先测试一下
          if (data) {
            testFileResponse(data);
          }

          setLoading(false);
        })
        .catch((err) => {
          console.error('获取文件数据出错:', err);
          setError(
            `获取文件失败: ${err instanceof Error ? err.message : String(err)}`,
          );
          setLoading(false);
        });
    } else if (fileData) {
      URL.revokeObjectURL(fileData);
      setFileData(undefined);
      setNumPages(null);
      setError(null);
      setPdfScale(1); // 重置缩放比例
      setDocxScale(1);
    }
  }, [open, fetchFile]);

  useEffect(() => {
    // 组件卸载时清理
    return () => {
      if (fileData) {
        URL.revokeObjectURL(fileData);
      }
    };
  }, [fileData]);

  // 检测文件类型
  const fileType = useMemo((): SupportedFileType => {
    if (!fileName) return 'other';
    const extension = fileName.split('.').pop()?.toLowerCase() || '';

    console.log('文件名:', fileName, '扩展名:', extension);

    if (extension === 'pdf') return 'pdf';
    if (extension === 'docx') return 'docx';
    if (extension === 'doc') return 'doc';

    return 'other';
  }, [fileName]);

  // 处理 DOCX 文件预览
  useEffect(() => {
    if (
      (fileType === 'docx' || fileType === 'doc') &&
      fileData &&
      docxContainerRef.current
    ) {
      console.log('开始处理 DOCX 文件预览，文件类型:', fileType);
      console.log('文件 URL:', fileData);
      console.log('容器引用存在:', !!docxContainerRef.current);

      // 清空容器
      if (docxContainerRef.current) {
        docxContainerRef.current.innerHTML = '';
        console.log('已清空容器内容');
      }

      try {
        // 获取 Blob 对象
        fetch(fileData)
          .then((res) => {
            console.log('Fetch 响应:', res.status, res.statusText);
            console.log('响应头:', [...res.headers.entries()]);

            if (!res.ok) {
              throw new Error(`HTTP 错误: ${res.status}`);
            }
            return res.blob();
          })
          .then((blob) => {
            console.log('获取到 Blob 数据:', blob.type, blob.size, 'bytes');

            if (!blob || blob.size === 0) {
              throw new Error('获取到的文件数据为空');
            }

            if (docxContainerRef.current) {
              console.log('准备渲染 DOCX 文件到容器中');

              // 检查是否为有效的 docx 文件类型
              if (
                blob.type &&
                !blob.type.includes(
                  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                ) &&
                !blob.type.includes('application/octet-stream')
              ) {
                console.warn('文件类型可能不是 DOCX:', blob.type);
              }

              const options = {
                inWrapper: true,
                ignoreWidth: true,
                ignoreHeight: false,
                ignoreFonts: false,
                debug: true,
                experimental: false,
                className: 'docx',
                useBase64URL: true,
                maxWidth: 1200,
                breakPages: false,
                renderHeaders: true,
                renderFooters: true,
                renderFootnotes: true,
                pageBorderTop: 0,
                pageBorderRight: 0,
                pageBorderBottom: 0,
                pageBorderLeft: 0,
                backgroundStyle: {
                  background: 'white',
                },
              };

              console.log('使用的渲染选项:', options);
              console.log('docx 渲染方法:', typeof docx.renderAsync);

              // 渲染 docx
              if (typeof docx.renderAsync !== 'function') {
                throw new Error('docx-preview 库的 renderAsync 方法不可用');
              }

              docx
                .renderAsync(
                  blob,
                  docxContainerRef.current,
                  docxContainerRef.current,
                  options,
                )
                .then(() => {
                  console.log('DOCX: 渲染完成');
                  setError(null);
                })
                .catch((error) => {
                  console.error('DOCX 渲染错误:', error);
                  console.error(
                    '错误详情:',
                    error instanceof Error ? error.stack : '无堆栈',
                  );
                  setError(
                    `DOCX 渲染错误: ${
                      error instanceof Error ? error.message : String(error)
                    }`,
                  );
                  message.error('文档预览失败，可能格式不兼容');
                });
            } else {
              console.error('渲染前容器引用丢失');
              setError('预览容器不可用');
            }
          })
          .catch((error) => {
            console.error('DOCX 预览错误:', error);
            console.error(
              '错误详情:',
              error instanceof Error ? error.stack : '无堆栈',
            );
            setError(
              `DOCX 获取错误: ${
                error instanceof Error ? error.message : String(error)
              }`,
            );
            message.error('文档加载失败');
          });
      } catch (error: unknown) {
        console.error('DOCX 处理外部错误:', error);
        console.error(
          '错误详情:',
          error instanceof Error ? error.stack : '无堆栈',
        );
        setError(
          `处理错误: ${error instanceof Error ? error.message : String(error)}`,
        );
      }
    }
  }, [fileType, fileData]);

  // PDF 缩放控制函数
  const handleZoomIn = () => {
    setPdfScale((prevScale) => Math.min(prevScale + 0.2, 3));
  };

  const handleZoomOut = () => {
    setPdfScale((prevScale) => Math.max(prevScale - 0.2, 0.5));
  };

  const handleResetZoom = () => {
    setPdfScale(1);
  };

  // 应用DOCX缩放
  const applyDocxZoom = (scale: number) => {
    if (docxContainerRef.current) {
      const docxContent = docxContainerRef.current.querySelector(
        '.docx',
      ) as HTMLElement;
      if (docxContent) {
        docxContent.style.transform = `scale(${scale})`;
        docxContent.style.transformOrigin = 'top left';
      }
    }
  };

  // DOCX缩放控制函数
  const handleDocxZoomIn = () => {
    setDocxScale((prevScale) => {
      const newScale = Math.min(prevScale + 0.2, 3);
      applyDocxZoom(newScale);
      return newScale;
    });
  };

  const handleDocxZoomOut = () => {
    setDocxScale((prevScale) => {
      const newScale = Math.max(prevScale - 0.2, 0.5);
      applyDocxZoom(newScale);
      return newScale;
    });
  };

  const handleDocxResetZoom = () => {
    setDocxScale(1);
    applyDocxZoom(1);
  };

  // PDF 加载完成的回调
  const onDocumentLoadSuccess = ({ numPages }: { numPages: number }) => {
    setNumPages(numPages);
    console.log('PDF 加载成功，页数:', numPages);
  };

  // 添加窗口大小监听器
  useEffect(() => {
    const handleResize = () => {
      setWindowWidth(window.innerWidth);
    };

    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
    };
  }, []);

  // 处理页码导航
  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= (numPages || 1)) {
      setCurrentPage(newPage);
      setPageInputValue(newPage.toString());

      // 滚动到指定页面
      if (pdfContainerRef.current) {
        const pageElement = pdfContainerRef.current.querySelector(
          `[data-page-number="${newPage}"]`,
        );
        if (pageElement) {
          pageElement.scrollIntoView({ behavior: 'smooth' });
        }
      }
    }
  };

  const handleNextPage = () => {
    handlePageChange(currentPage + 1);
  };

  const handlePrevPage = () => {
    handlePageChange(currentPage - 1);
  };

  const handlePageInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setPageInputValue(e.target.value);
  };

  const handlePageInputConfirm = () => {
    const pageNumber = parseInt(pageInputValue, 10);
    if (!isNaN(pageNumber)) {
      handlePageChange(pageNumber);
    } else {
      setPageInputValue(currentPage.toString());
    }
  };

  // 全屏控制
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      if (
        pdfContainerRef.current &&
        pdfContainerRef.current.requestFullscreen
      ) {
        pdfContainerRef.current
          .requestFullscreen()
          .then(() => {
            setIsFullscreen(true);
          })
          .catch((err) => {
            console.error('全屏模式错误:', err);
          });
      }
    } else {
      if (document.exitFullscreen) {
        document
          .exitFullscreen()
          .then(() => {
            setIsFullscreen(false);
          })
          .catch((err) => {
            console.error('退出全屏模式错误:', err);
          });
      }
    }
  };

  // 监听全屏状态变化
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  // 重置缩放状态
  useEffect(() => {
    if (open) {
      setPdfScale(1);
      setDocxScale(1);
    }
  }, [open, fileType]);

  // 应用DOCX文档加载完成后的缩放
  useEffect(() => {
    if (
      (fileType === 'docx' || fileType === 'doc') &&
      !loading &&
      docxScale !== 1
    ) {
      setTimeout(() => {
        applyDocxZoom(docxScale);
      }, 500);
    }
  }, [fileType, loading, docxScale]);

  // 添加DOCX全屏相关的状态和函数
  const toggleDocxFullscreen = () => {
    if (!document.fullscreenElement) {
      if (
        docxContainerRef.current &&
        docxContainerRef.current.requestFullscreen
      ) {
        docxContainerRef.current
          .requestFullscreen()
          .then(() => {
            setIsFullscreen(true);
          })
          .catch((err) => {
            console.error('DOCX全屏模式错误:', err);
          });
      }
    } else {
      if (document.exitFullscreen) {
        document
          .exitFullscreen()
          .then(() => {
            setIsFullscreen(false);
          })
          .catch((err) => {
            console.error('退出全屏模式错误:', err);
          });
      }
    }
  };

  // 根据文件类型渲染不同的预览组件
  const renderPreview = () => {
    console.log('渲染预览组件，文件类型:', fileType);

    if (loading) {
      return (
        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <Spin tip="加载中..." />
        </div>
      );
    }

    if (!fileData) {
      console.log('没有文件数据可用');
      return <div>没有文件数据</div>;
    }

    switch (fileType) {
      case 'pdf':
        console.log('渲染 PDF 预览');
        return (
          <div>
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                margin: '10px 0',
              }}
            >
              <Space>
                <Tooltip title="缩小">
                  <Button icon={<ZoomOutOutlined />} onClick={handleZoomOut} />
                </Tooltip>
                <Button onClick={handleResetZoom}>
                  {Math.round(pdfScale * 100)}%
                </Button>
                <Tooltip title="放大">
                  <Button icon={<ZoomInOutlined />} onClick={handleZoomIn} />
                </Tooltip>
                <Tooltip title={isFullscreen ? '退出全屏' : '全屏'}>
                  <Button
                    icon={
                      isFullscreen ? (
                        <FullscreenExitOutlined />
                      ) : (
                        <FullscreenOutlined />
                      )
                    }
                    onClick={toggleFullscreen}
                  />
                </Tooltip>
                <Space.Compact>
                  <Button
                    icon={<ArrowUpOutlined />}
                    onClick={handlePrevPage}
                    disabled={currentPage <= 1}
                  />
                  <Popover
                    content={
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <Input
                          value={pageInputValue}
                          onChange={handlePageInputChange}
                          onPressEnter={handlePageInputConfirm}
                          style={{ width: '60px', marginRight: 8 }}
                        />
                        <Button type="primary" onClick={handlePageInputConfirm}>
                          跳转
                        </Button>
                      </div>
                    }
                    title="跳转到页码"
                    trigger="click"
                  >
                    <Button>
                      {currentPage} / {numPages || 1}
                    </Button>
                  </Popover>
                  <Button
                    icon={<ArrowDownOutlined />}
                    onClick={handleNextPage}
                    disabled={currentPage >= (numPages || 1)}
                  />
                </Space.Compact>
              </Space>
            </div>
            <div
              ref={pdfContainerRef}
              style={{
                width: '100%',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'flex-start',
              }}
            >
              <Document
                file={fileData}
                onLoadSuccess={onDocumentLoadSuccess}
                onLoadError={(error) => {
                  console.error('PDF 加载错误:', error);
                  setError(`PDF 加载错误: ${error.message}`);
                }}
                loading={<Spin tip="加载PDF中..." />}
              >
                {Array.from(new Array(numPages || 0), (_, index) => (
                  <Page
                    key={`page_${index + 1}`}
                    pageNumber={index + 1}
                    scale={pdfScale}
                    width={windowWidth > 1400 ? 1100 : windowWidth - 300}
                    renderTextLayer={true}
                    renderAnnotationLayer={true}
                  />
                ))}
              </Document>
            </div>
          </div>
        );
      case 'docx':
      case 'doc':
        console.log('渲染 DOCX/DOC 预览');
        return (
          <div style={{ backgroundColor: 'white', padding: '10px' }}>
            <div
              style={{
                display: 'flex',
                justifyContent: 'center',
                margin: '10px 0',
              }}
            >
              <Space>
                <Tooltip title="缩小">
                  <Button
                    icon={<ZoomOutOutlined />}
                    onClick={handleDocxZoomOut}
                  />
                </Tooltip>
                <Button onClick={handleDocxResetZoom}>
                  {Math.round(docxScale * 100)}%
                </Button>
                <Tooltip title="放大">
                  <Button
                    icon={<ZoomInOutlined />}
                    onClick={handleDocxZoomIn}
                  />
                </Tooltip>
                <Tooltip title={isFullscreen ? '退出全屏' : '全屏'}>
                  <Button
                    icon={
                      isFullscreen ? (
                        <FullscreenExitOutlined />
                      ) : (
                        <FullscreenOutlined />
                      )
                    }
                    onClick={toggleDocxFullscreen}
                  />
                </Tooltip>
              </Space>
            </div>
            <div
              ref={docxContainerRef}
              style={{
                minWidth: '100%',
                width: 'auto',
                padding: '20px',
                minHeight: '300px',
                background: '#fff',
                position: 'relative',
                border: 'none',
                borderRadius: '0',
                boxShadow: 'none',
              }}
            />
            {error && (
              <div style={{ color: 'red', margin: '10px 0' }}>{error}</div>
            )}
          </div>
        );
      default:
        console.log('不支持的文件类型');
        return <div>无法预览该文件格式，请下载后查看</div>;
    }
  };

  // 添加自定义样式，修复 DOCX 背景问题和缩放效果，移除 box-shadow
  useEffect(() => {
    // 添加全局样式来确保表格完整显示和背景颜色正确
    const styleElement = document.createElement('style');
    styleElement.textContent = `
      .docx table {
        table-layout: auto !important;
        width: auto !important;
        min-width: 100% !important;
      }
      .docx table td {
        white-space: normal !important;
        word-break: break-word !important;
      }
      .docx {
        background: white !important;
        transition: transform 0.3s ease;
        transform-origin: top left;
        box-shadow: none !important;
      }
      .docx-wrapper {
        background: white !important;
        padding: 0 !important;
        margin: 0 !important;
        box-shadow: none !important;
      }
      .docx-wrapper::before,
      .docx-wrapper::after {
        display: none !important;
        box-shadow: none !important;
      }
      .docx-wrapper > div {
        background: white !important;
        box-shadow: none !important;
      }
      .docx p, .docx div, .docx section, .docx * {
        box-shadow: none !important;
      }
    `;
    document.head.appendChild(styleElement);

    return () => {
      document.head.removeChild(styleElement);
    };
  }, []);

  // 添加样式修复
  useEffect(() => {
    // 修改 Modal 背景
    if (open) {
      const modalContent = document.querySelector('.ant-modal-content');
      if (modalContent) {
        modalContent.setAttribute(
          'style',
          'background-color: white !important',
        );
      }

      // 修改 docx 预览容器的外层元素背景
      const docxWrappers = document.querySelectorAll('.docx-wrapper');
      docxWrappers.forEach((wrapper) => {
        wrapper.setAttribute(
          'style',
          'background-color: white !important; padding: 0 !important; margin: 0 !important; box-shadow: none !important;',
        );
      });

      // 修改 docx 预览内容背景
      const docxContainers = document.querySelectorAll('.docx');
      docxContainers.forEach((container) => {
        container.setAttribute(
          'style',
          'background-color: white !important; box-shadow: none !important;',
        );
      });

      // 移除所有可能存在的 box-shadow
      const allDocxElements = document.querySelectorAll('.docx *');
      allDocxElements.forEach((element) => {
        const currentStyle = element.getAttribute('style') || '';
        if (
          currentStyle.includes('box-shadow') ||
          currentStyle.includes('shadow')
        ) {
          const newStyle =
            currentStyle
              .replace(/box-shadow:[^;]+;?/g, '')
              .replace(/shadow:[^;]+;?/g, '') +
            '; box-shadow: none !important;';
          element.setAttribute('style', newStyle);
        }
      });
    }
  }, [open]);

  // 添加 MutationObserver 监听 DOM 变化，确保新添加的元素没有 box-shadow
  useEffect(() => {
    if (open && (fileType === 'docx' || fileType === 'doc')) {
      // 处理移除 box-shadow 的函数
      const removeBoxShadow = () => {
        // 移除所有 DOCX 相关元素的 box-shadow
        const allDocxElements = document.querySelectorAll(
          '.docx, .docx-wrapper, .docx *, .docx-wrapper *',
        );
        allDocxElements.forEach((element) => {
          if (element instanceof HTMLElement) {
            // 移除内联样式
            const currentStyle = element.getAttribute('style') || '';
            if (
              currentStyle.includes('box-shadow') ||
              currentStyle.includes('shadow')
            ) {
              const newStyle =
                currentStyle
                  .replace(/box-shadow:[^;]+;?/g, '')
                  .replace(/shadow:[^;]+;?/g, '') +
                '; box-shadow: none !important;';
              element.setAttribute('style', newStyle);
            } else if (currentStyle) {
              element.setAttribute(
                'style',
                currentStyle + '; box-shadow: none !important;',
              );
            } else {
              element.setAttribute('style', 'box-shadow: none !important;');
            }

            // 使用 CSS API 移除计算样式
            if (window.getComputedStyle(element).boxShadow !== 'none') {
              element.style.boxShadow = 'none';
            }
          }
        });
      };

      // 初始处理
      removeBoxShadow();

      // 创建 MutationObserver 持续监听 DOM 变化
      const observer = new MutationObserver(() => {
        removeBoxShadow();
      });

      // 开始观察 docx 容器
      if (docxContainerRef.current) {
        observer.observe(docxContainerRef.current, {
          childList: true,
          subtree: true,
          attributes: true,
          attributeFilter: ['style', 'class'],
        });
      }

      // 清理函数
      return () => {
        observer.disconnect();
      };
    }
  }, [open, fileType]);

  return (
    <Modal
      title={`文件预览 - ${fileName || '未知文件'}`}
      open={open}
      onCancel={onCancel}
      footer={null}
      width="85%"
      style={{ top: 20, minHeight: 300 }}
      bodyStyle={{
        padding: '0',
        background: '#fff',
      }}
      destroyOnClose
    >
      {renderPreview()}
    </Modal>
  );
};

export default FilePreview;
