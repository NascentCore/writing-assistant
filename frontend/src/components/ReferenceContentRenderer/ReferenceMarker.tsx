import { fetchWithAuthNew } from '@/utils/fetch';
import { DownOutlined, FileTextOutlined, UpOutlined } from '@ant-design/icons';
import {
  Button,
  Drawer,
  Flex,
  Popover,
  Spin,
  Tooltip,
  Typography,
  message,
} from 'antd';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { FileFullContent, ReferenceMarkerProps } from './type';

/**
 * 自定义引用标识组件
 */
const ReferenceMarker: React.FC<ReferenceMarkerProps> = ({
  index,
  referenceFile,
}) => {
  const [hovered, setHovered] = useState(false);
  const [drawerVisible, setDrawerVisible] = useState(false);
  const [fileContent, setFileContent] = useState<FileFullContent | null>(null);
  const [loading, setLoading] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);
  const [currentHighlightIndex, setCurrentHighlightIndex] = useState(1);
  const [totalHighlights, setTotalHighlights] = useState(0);
  const [highlightIdPrefix, setHighlightIdPrefix] = useState<string>('');

  // 获取文件全文内容
  const fetchFileContent = async () => {
    if (!referenceFile.file_id) return;

    try {
      setLoading(true);
      const response = await fetchWithAuthNew(
        `/api/v1/rag/files/${referenceFile.file_id}/markdown`,
      );
      if (response) {
        setFileContent(response);
        // 重置高亮导航状态
        setCurrentHighlightIndex(1);
      }
    } catch (error) {
      console.error('获取文件内容失败:', error);
      message.error('获取文件内容失败');
    } finally {
      setLoading(false);
    }
  };

  // 点击标题时打开抽屉并获取文件内容
  const handleTitleClick = () => {
    setDrawerVisible(true);
    if (!fileContent) {
      fetchFileContent();
    }
  };

  // 跳转到指定的高亮处
  const navigateToHighlight = (index: number) => {
    const highlightId = `${highlightIdPrefix}-${index}`;
    const element = document.getElementById(highlightId);
    if (element) {
      // 先恢复所有高亮的颜色
      const allHighlights = document.querySelectorAll('.content-highlight');
      allHighlights.forEach((el) => {
        (el as HTMLElement).style.backgroundColor = '#FFEE5880';
      });

      // 滚动到目标元素并高亮显示
      element.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });

      // 特殊高亮当前元素
      element.style.backgroundColor = '#FFCC00';
    }
  };

  // 高亮导航 - 下一个
  const navigateToNextHighlight = () => {
    if (currentHighlightIndex < totalHighlights) {
      const nextIndex = currentHighlightIndex + 1;
      navigateToHighlight(nextIndex);
      setCurrentHighlightIndex(nextIndex);
    }
  };

  // 高亮导航 - 上一个
  const navigateToPrevHighlight = () => {
    if (currentHighlightIndex > 1) {
      const prevIndex = currentHighlightIndex - 1;
      navigateToHighlight(prevIndex);
      setCurrentHighlightIndex(prevIndex);
    }
  };

  // 高亮显示Popover中的内容
  const highlightContent = (fullContent: string, snippetContent: string) => {
    if (!snippetContent || !fullContent) return fullContent;

    try {
      // 处理可能存在的特殊字符和换行符
      const sanitizedSnippet = snippetContent
        .replace(/[-/\\^$*+?.()|[\]{}]/g, '\\$&')
        .replace(/\n/g, '\\n');

      // 创建正则表达式查找片段内容
      const regex = new RegExp(`(${sanitizedSnippet})`, 'g');

      // 生成唯一标识ID
      const highlightId = `highlight-${Date.now()}-${Math.random()
        .toString(36)
        .substring(2, 9)}`;

      // 计数器，用于给每个匹配项添加唯一ID
      let matchCount = 0;

      // 替换为带高亮的内容和特殊类，方便后续滚动定位
      const result = fullContent.replace(regex, (match) => {
        matchCount++;
        return `<mark id="${highlightId}-${matchCount}" class="content-highlight" 
          style="background-color: #FFEE5880; padding: 2px 0; border-radius: 2px; transition: background-color 0.5s;">${match}</mark>`;
      });

      // 只在第一次渲染时设置，避免在渲染函数中直接修改状态
      if (highlightIdPrefix === '') {
        // 使用setTimeout将状态更新移出渲染流程
        setTimeout(() => {
          setHighlightIdPrefix(highlightId);
          setTotalHighlights(matchCount);
        }, 0);
      }

      // 保存第一个高亮元素的ID，用于滚动定位
      if (matchCount > 0) {
        setTimeout(() => {
          // 使用data属性传递第一个高亮元素的ID和总数
          const container = contentRef.current;
          if (container) {
            container.setAttribute('data-first-highlight', `${highlightId}-1`);
            container.setAttribute('data-highlight-count', String(matchCount));
          }
        }, 0);
      }

      return result;
    } catch (error) {
      console.error('高亮内容失败:', error);
      return fullContent;
    }
  };

  // 当内容加载完成后滚动到高亮区域
  useEffect(() => {
    if (!loading && fileContent && contentRef.current) {
      // 首次加载完成后，设置高亮ID前缀和总数
      if (highlightIdPrefix === '' && contentRef.current) {
        const container = contentRef.current;
        const firstHighlightId = container.getAttribute('data-first-highlight');
        if (firstHighlightId) {
          // 从firstHighlightId中提取前缀（去掉最后的序号）
          const prefix = firstHighlightId.substring(
            0,
            firstHighlightId.lastIndexOf('-'),
          );
          setHighlightIdPrefix(prefix);
        }

        const highlightCount = parseInt(
          container.getAttribute('data-highlight-count') || '0',
          10,
        );
        if (highlightCount > 0) {
          setTotalHighlights(highlightCount);
        }
      }

      // 使用setTimeout确保DOM已完全渲染
      setTimeout(() => {
        const container = contentRef.current;
        if (!container) return;

        // 获取第一个高亮元素的ID
        const firstHighlightId = container.getAttribute('data-first-highlight');
        const highlightCount = parseInt(
          container.getAttribute('data-highlight-count') || '0',
          10,
        );

        if (firstHighlightId) {
          const highlightElement = document.getElementById(firstHighlightId);
          if (highlightElement) {
            // 滚动到高亮元素
            highlightElement.scrollIntoView({
              behavior: 'smooth',
              block: 'center',
            });

            // 添加特别的动画效果，增强视觉反馈
            setTimeout(() => {
              // 闪烁动画效果
              highlightElement.style.backgroundColor = '#FFCC00';
              setTimeout(() => {
                highlightElement.style.backgroundColor = '#FFEE5880';
              }, 700);

              // 如果有多个高亮，添加提示信息
              if (highlightCount > 1) {
                message.info(`找到${highlightCount}处匹配内容，已滚动到第一处`);
              }
            }, 300);
          }
        }
      }, 100);
    }
  }, [loading, fileContent]);

  // 自定义标题组件
  const customTitle = (
    <div
      style={{
        cursor: 'pointer',
        display: 'flex',
        alignItems: 'center',
        color: '#1677ff',
      }}
      onClick={handleTitleClick}
    >
      <FileTextOutlined style={{ marginRight: 4 }} />
      {referenceFile.file_name || '引用文件'}
    </div>
  );

  // 渲染高亮导航控件
  const renderHighlightNavigation = () => {
    if (totalHighlights <= 1) return null;

    return (
      <Flex
        gap={8}
        align="center"
        style={{
          marginTop: 8,
          padding: '8px 0',
          borderTop: '1px solid #f0f0f0',
        }}
      >
        <Typography.Text type="secondary" style={{ fontSize: 13 }}>
          {currentHighlightIndex}/{totalHighlights}
        </Typography.Text>
        <Tooltip title="上一处">
          <Button
            size="small"
            icon={<UpOutlined />}
            disabled={currentHighlightIndex <= 1}
            onClick={navigateToPrevHighlight}
          />
        </Tooltip>
        <Tooltip title="下一处">
          <Button
            size="small"
            icon={<DownOutlined />}
            disabled={currentHighlightIndex >= totalHighlights}
            onClick={navigateToNextHighlight}
          />
        </Tooltip>
      </Flex>
    );
  };

  // 预先计算footer，避免在Drawer渲染时计算导致的问题
  const drawerFooter = useMemo(
    () => renderHighlightNavigation(),
    [totalHighlights, currentHighlightIndex],
  );

  // 预处理高亮内容
  const highlightedContent = useMemo(() => {
    if (!fileContent || !referenceFile.content) return '';
    return highlightContent(fileContent.content, referenceFile.content);
  }, [fileContent, referenceFile.content]);

  return (
    <>
      <Popover
        title={customTitle}
        content={
          <div
            style={{ maxWidth: '300px', maxHeight: '200px', overflow: 'auto' }}
          >
            <div style={{ whiteSpace: 'pre-wrap' }}>
              {referenceFile.content || '无内容'}
            </div>
          </div>
        }
        trigger="hover"
      >
        <span
          style={{
            display: 'inline-block',
            backgroundColor: hovered ? '#1677ff' : 'rgba(0, 0, 0, 0.15)',
            color: 'white',
            width: '16px',
            height: '16px',
            borderRadius: '50%',
            textAlign: 'center',
            lineHeight: '16px',
            fontSize: '10px',
            cursor: 'pointer',
            margin: '0 2px',
            userSelect: 'none',
            transition: 'background-color 0.2s',
            verticalAlign: 'text-bottom',
          }}
          onMouseEnter={() => setHovered(true)}
          onMouseLeave={() => setHovered(false)}
        >
          {index + 1}
        </span>
      </Popover>

      <Drawer
        title={referenceFile.file_name || '文件内容'}
        open={drawerVisible}
        onClose={() => setDrawerVisible(false)}
        width={600}
        mask={false}
        footer={drawerFooter}
        styles={{
          body: {
            padding: '16px',
            overflow: 'auto',
          },
        }}
      >
        {loading ? (
          <Flex justify="center" align="center" style={{ height: '100px' }}>
            <Spin tip="加载中..." />
          </Flex>
        ) : (
          fileContent && (
            <div
              ref={contentRef}
              style={{ whiteSpace: 'pre-wrap', lineHeight: '1.6' }}
              dangerouslySetInnerHTML={{ __html: highlightedContent }}
            />
          )
        )}
      </Drawer>
    </>
  );
};

export default ReferenceMarker;
