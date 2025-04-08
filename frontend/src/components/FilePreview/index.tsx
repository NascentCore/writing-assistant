import {
  ArrowDownOutlined,
  ArrowUpOutlined,
  FullscreenExitOutlined,
  FullscreenOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  SearchOutlined,
  UnorderedListOutlined,
  ZoomInOutlined,
  ZoomOutOutlined,
} from '@ant-design/icons';
import {
  Badge,
  Button,
  Empty,
  Input,
  message,
  Modal,
  Popover,
  Space,
  Spin,
  Tooltip,
  Tree,
} from 'antd';
import type { DataNode } from 'antd/es/tree';
import * as docx from 'docx-preview';
import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import { FilePreviewProps, SupportedFileType } from './type';

// 配置 PDF.js worker
pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

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
  const [tocVisible, setTocVisible] = useState<boolean>(true);
  const [tocData, setTocData] = useState<DataNode[]>([]);
  const [tocLoading, setTocLoading] = useState<boolean>(false);
  const [tocSearchValue, setTocSearchValue] = useState<string>('');
  const [filteredTocData, setFilteredTocData] = useState<DataNode[]>([]);

  useEffect(() => {
    if (open) {
      setLoading(true);
      setError(null);
      setCurrentPage(1);
      setPageInputValue('1');
      // 重置目录相关状态
      setTocData([]);
      setFilteredTocData([]);
      setTocVisible(true);
      setTocLoading(false);
      setTocSearchValue('');

      fetchFile()
        .then((data) => {
          setFileData(data);
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

    if (extension === 'pdf') return 'pdf';
    if (extension === 'docx') return 'docx';
    if (extension === 'doc') return 'doc';

    return 'other';
  }, [fileName]);

  // 根据字体大小估算层级的辅助函数
  const estimateLevelByFontSize = (
    fontSize: number,
    allFontSizes: number[],
  ): number => {
    // 对所有字体大小去重并降序排序
    const uniqueSizes = Array.from(new Set(allFontSizes)).sort((a, b) => b - a);

    // 找到当前字体大小在排序列表中的位置
    const position = uniqueSizes.indexOf(fontSize);

    // 返回 1 到 6 之间的层级
    return Math.min(Math.max(position + 1, 1), 6);
  };

  // 分析标题层级的辅助函数
  const determineHeadingLevels = (headings: Element[]): number[] => {
    const levels: number[] = [];

    // 分析字体大小和样式模式
    const fontSizes: number[] = [];
    const fontWeights: number[] = [];
    const isNumbered: boolean[] = [];
    const numberingDepths: number[] = [];

    // 收集样式信息
    headings.forEach((heading) => {
      const style = window.getComputedStyle(heading);
      fontSizes.push(parseInt(style.fontSize, 10));
      fontWeights.push(parseInt(style.fontWeight, 10) || 400);

      // 检查是否有编号及其深度
      const text = heading.textContent?.trim() || '';
      const numberMatch = text.match(/^(\d+(\.\d+)*)\./);
      isNumbered.push(!!numberMatch);
      if (numberMatch) {
        // 计算编号的深度，如 "1.2.3" 深度为 3
        numberingDepths.push(numberMatch[1].split('.').length);
      } else {
        numberingDepths.push(0);
      }
    });

    // 检测是否使用标准HTML标签
    const usingHTMLHeadings = headings.some((h) => /^h[1-6]$/i.test(h.tagName));

    // 如果使用标准标签，直接从标签获取层级
    if (usingHTMLHeadings) {
      headings.forEach((heading) => {
        const tagName = heading.tagName.toLowerCase();
        if (/^h[1-6]$/.test(tagName)) {
          levels.push(parseInt(tagName.substring(1), 10));
        } else {
          // 对于非标准标签，估算层级
          const fontSize = parseInt(
            window.getComputedStyle(heading).fontSize,
            10,
          );
          const estimatedLevel = estimateLevelByFontSize(fontSize, fontSizes);
          levels.push(estimatedLevel);
        }
      });
    }
    // 如果有清晰的编号模式，优先使用编号确定层级
    else if (isNumbered.filter(Boolean).length > headings.length * 0.5) {
      headings.forEach((heading, index) => {
        if (isNumbered[index]) {
          levels.push(numberingDepths[index]);
        } else {
          // 对于没有编号的，估算层级
          const fontSize = fontSizes[index];
          const estimatedLevel = estimateLevelByFontSize(fontSize, fontSizes);
          levels.push(estimatedLevel);
        }
      });
    }
    // 否则基于字体大小和其他样式估算层级
    else {
      // 按字体大小降序排序
      const sortedFontSizes = [...fontSizes].sort((a, b) => b - a);
      const uniqueFontSizes = Array.from(new Set(sortedFontSizes));

      // 映射字体大小到层级
      headings.forEach((_, index) => {
        const fontSize = fontSizes[index];
        // 查找字体大小在排序数组中的位置作为层级估计
        const level = uniqueFontSizes.indexOf(fontSize) + 1;
        levels.push(level);
      });
    }

    return levels;
  };

  // 构建目录树的辅助函数
  const buildTocTree = (headings: Element[], levels: number[]): DataNode[] => {
    const toc: DataNode[] = [];

    // 标准化层级，确保最小层级为 1
    const minLevel = Math.min(...levels);
    const normalizedLevels = levels.map((level) => level - minLevel + 1);

    // 初始化节点堆栈 (为每个可能的层级保留当前活动节点)
    const activeNodes: (DataNode | null)[] = Array(10).fill(null);

    headings.forEach((heading, index) => {
      const level = normalizedLevels[index];
      const title = heading.textContent?.trim() || `标题 ${index + 1}`;

      // 为标题元素添加 ID，以便导航
      const headingId = `toc-heading-${index}`;
      heading.setAttribute('id', headingId);

      const newNode: DataNode = {
        title,
        key: headingId,
        isLeaf: true,
        children: [],
      };

      // 更新层级对应的活动节点
      activeNodes[level] = newNode;

      // 重置更高层级的节点
      for (let i = level + 1; i < activeNodes.length; i++) {
        activeNodes[i] = null;
      }

      // 将新节点添加到合适的父节点
      if (level === 1) {
        // 一级标题直接添加到根
        toc.push(newNode);
      } else {
        // 查找最近的上级标题
        let parentLevel = level - 1;
        while (parentLevel > 0 && !activeNodes[parentLevel]) {
          parentLevel--;
        }

        if (parentLevel > 0 && activeNodes[parentLevel]) {
          // 添加到父节点
          activeNodes[parentLevel]!.children!.push(newNode);
          activeNodes[parentLevel]!.isLeaf = false;
        } else {
          // 如果没有找到父节点，作为顶级节点
          toc.push(newNode);
        }
      }
    });

    return toc;
  };

  // 提取文档标题并构建目录结构
  const extractTableOfContents = () => {
    if (!docxContainerRef.current) return;

    setTocLoading(true);

    // 延迟执行，确保文档已经完全渲染
    setTimeout(() => {
      try {
        // 查找所有标题元素
        const docxContent = docxContainerRef.current;
        if (!docxContent) {
          setTocLoading(false);
          return;
        }

        // 收集所有可能的标题，使用统一的标准
        let allPossibleHeadings: Element[] = [];

        // 1. 首先尝试查找真正的标题标签
        const standardHeadings = Array.from(
          docxContent.querySelectorAll('h1, h2, h3, h4, h5, h6'),
        );
        console.log('找到标准标题标签数量:', standardHeadings.length);

        // 过滤掉居中的标题（通常是文章的主标题）
        const filteredStandardHeadings = standardHeadings.filter((heading) => {
          const style = window.getComputedStyle(heading);
          // 如果文本居中且位于文档顶部区域，则认为是主标题，排除它
          const isCentered = style.textAlign === 'center';
          if (isCentered) {
            const rect = heading.getBoundingClientRect();
            const containerRect = docxContent.getBoundingClientRect();
            // 检查是否在文档的顶部区域（前20%）
            const isInTopArea =
              rect.top - containerRect.top < containerRect.height * 0.2;
            return !isInTopArea; // 过滤掉在顶部区域且居中的标题
          }
          return true;
        });

        allPossibleHeadings = [
          ...allPossibleHeadings,
          ...filteredStandardHeadings,
        ];

        // 2. 识别通过样式特征的标题
        console.log('尝试通过样式特征识别标题');

        // 获取所有可能包含标题的元素
        const allTextElements = Array.from(
          docxContent.querySelectorAll('.docx p, .docx div, .docx span'),
        );

        // 标题特征分析
        const styleBasedHeadings: Element[] = [];

        for (const element of allTextElements) {
          const textContent = element.textContent?.trim() || '';
          if (!textContent) continue; // 跳过空元素

          // 检查文本长度 - 标题通常较短，如果文本过长则可能是段落
          if (textContent.length > 150) continue; // 标题不应超过150个字符

          // 检查是否有太多标点符号 - 标题通常标点符号较少
          const punctuationCount = (
            textContent.match(/[，。；：""、？！，《》【】（）]/g) || []
          ).length;
          if (punctuationCount > 3) continue; // 如果标点符号过多，可能是正文段落

          // 检查是否有完整的句子结构（中文句号结尾）- 标题通常不是完整句子
          if (textContent.endsWith('。') && textContent.length > 15) continue;

          // 获取计算样式
          const computedStyle = window.getComputedStyle(element);
          const fontSize = parseInt(computedStyle.fontSize, 10);
          const fontWeight = computedStyle.fontWeight;
          const textAlign = computedStyle.textAlign;
          const marginTop = parseInt(computedStyle.marginTop, 10);
          const marginBottom = parseInt(computedStyle.marginBottom, 10);
          const lineHeight = parseFloat(computedStyle.lineHeight);

          // 检查行高 - 标题通常行高较小
          // 注：如果行高不在标准范围内，可能不是普通段落
          const hasAbnormalLineHeight =
            !isNaN(lineHeight) && (lineHeight < 1.2 || lineHeight > 2.5);

          // 检查是否是居中的文本（可能是文章主标题）
          const isCentered = textAlign === 'center';
          if (isCentered) {
            const rect = element.getBoundingClientRect();
            const containerRect = docxContent.getBoundingClientRect();
            // 如果是居中且在文档顶部区域的文本，跳过它
            if (rect.top - containerRect.top < containerRect.height * 0.2) {
              continue;
            }
          }

          // 检查是否有序号格式但实际是正文段落
          const hasNumberingFormat = /^(\d+(\.\d+)*\.?)\s+/.test(textContent);
          if (hasNumberingFormat) {
            // 如果内容很长或包含多个句子，可能是带编号的段落而非标题
            const sentenceCount = (textContent.match(/[。！？；]/g) || [])
              .length;
            if (sentenceCount > 1 || textContent.length > 100) continue;
          }

          // 文本内容特征
          const isBold =
            fontWeight === 'bold' || parseInt(fontWeight, 10) >= 600;
          const isLargeFont = fontSize > 14;
          const isShort = textContent.length < 100;
          const hasMargins = marginTop > 5 || marginBottom > 5;
          const startsWithNumber = hasNumberingFormat; // 使用上面的结果

          // 增加缩进检查 - 标题通常没有或缩进很小
          const textIndent = parseInt(computedStyle.textIndent, 10);
          const hasSmallIndent = isNaN(textIndent) || textIndent < 20;

          // 组合多种特征判断是否可能是标题
          const titleScore =
            (isBold ? 2 : 0) +
            (isLargeFont ? 2 : 0) +
            (isShort ? 1 : 0) +
            (isCentered ? 0 : 0) + // 居中不再作为标题特征
            (hasMargins ? 1 : 0) +
            (startsWithNumber ? 2 : 0) + // 降低编号的权重
            (hasSmallIndent ? 1 : -1) + // 缩进小加分，缩进大减分
            (hasAbnormalLineHeight ? 1 : 0); // 异常行高可能是标题的特征之一

          // 如果分数达到阈值，则可能是标题
          if (titleScore >= 4) {
            // 提高阈值，使识别更严格
            // 检查是否已包含在标题列表中（避免重复）
            const isDuplicate = styleBasedHeadings.some(
              (h) =>
                h.textContent?.trim() === textContent ||
                h.contains(element) ||
                element.contains(h),
            );

            if (!isDuplicate && (isLargeFont || isBold)) {
              // 额外检查 - 排除明显是段落的文本
              // 如果文本中包含常见的段落标识词，则跳过
              const paragraphIndicators = [
                '如下',
                '包括',
                '其中',
                '例如',
                '通过',
                '因此',
                '如此',
                '所以',
                '以便',
                '为了',
              ];
              const containsParagraphIndicator = paragraphIndicators.some(
                (indicator) =>
                  textContent.includes(indicator) && textContent.length > 30,
              );

              if (!containsParagraphIndicator) {
                styleBasedHeadings.push(element);
              }
            }
          }
        }

        console.log(
          '通过样式特征识别到的潜在标题数量:',
          styleBasedHeadings.length,
        );
        allPossibleHeadings = [...allPossibleHeadings, ...styleBasedHeadings];

        // 3. 识别编号格式标题，但更严格地过滤
        console.log('尝试识别编号格式标题');
        const textElements = Array.from(
          docxContent.querySelectorAll('.docx p'),
        );
        const numberingPattern = /^(\d+(\.\d+)*\.?)\s+(.+)$/;

        const numberedHeadings = textElements.filter((elem) => {
          const text = elem.textContent?.trim() || '';

          // 基本检查
          if (text.length > 100 || text.length < 2) return false;

          // 检查是否是编号标题格式
          const match = text.match(numberingPattern);
          if (!match) return false;

          // 提取编号和内容部分
          const numberPart = match[1];
          const contentPart = match[3];

          // 编号不应过长
          if (numberPart.length > 8) return false;

          // 内容部分不应该有太多标点或太长
          const punctuationCount = (
            contentPart.match(/[，。；：""、？！，《》【】（）]/g) || []
          ).length;
          if (punctuationCount > 2 || contentPart.length > 50) return false;

          // 检查是否是常见的标题格式（如第一章、一、等）
          const titlePatterns = [
            /^第[一二三四五六七八九十]+[章节篇]/, // 匹配"第一章"、"第二节"等
            /^[一二三四五六七八九十]+、/, // 匹配"一、"、"二、"等
            /^（[一二三四五六七八九十]+）/, // 匹配"（一）"、"（二）"等
          ];
          const isTitleFormat = titlePatterns.some((pattern) =>
            pattern.test(text),
          );

          // 同样过滤掉居中的标题
          const style = window.getComputedStyle(elem);
          const isCentered = style.textAlign === 'center';

          if (isCentered) {
            const rect = elem.getBoundingClientRect();
            const containerRect = docxContent.getBoundingClientRect();
            const isInTopArea =
              rect.top - containerRect.top < containerRect.height * 0.2;
            if (isInTopArea) return false; // 过滤掉居中且在顶部区域的标题
          }

          // 验证字体大小和粗细
          const fontSize = parseInt(style.fontSize, 10);
          const fontWeight = style.fontWeight;
          const isBold =
            fontWeight === 'bold' || parseInt(fontWeight, 10) >= 600;
          const isLargeFont = fontSize > 14;

          // 结合所有条件判断
          return (
            (isTitleFormat || (isLargeFont && isBold)) && !text.endsWith('。')
          );
        });

        console.log('通过编号模式识别到的标题数量:', numberedHeadings.length);

        // 合并所有可能的标题并去重
        allPossibleHeadings = [...allPossibleHeadings, ...numberedHeadings];
        const uniqueHeadings = Array.from(new Set(allPossibleHeadings));

        if (uniqueHeadings.length === 0) {
          console.log('未能识别到任何标题结构');
          setTocLoading(false);
          return;
        }

        // 4. 最终过滤 - 检查标题的上下文
        const finalHeadings = uniqueHeadings.filter((heading) => {
          // 获取该元素的边界位置
          const rect = heading.getBoundingClientRect();

          // 检查相邻元素，判断是否为正文段落的一部分
          const siblings = Array.from(
            docxContent.querySelectorAll('.docx p, .docx div'),
          );
          const index = siblings.indexOf(heading as Element);

          if (index !== -1) {
            // 检查前后的元素
            const prevElement = index > 0 ? siblings[index - 1] : null;
            const nextElement =
              index < siblings.length - 1 ? siblings[index + 1] : null;

            if (prevElement && nextElement) {
              const prevRect = prevElement.getBoundingClientRect();
              const nextRect = nextElement.getBoundingClientRect();

              // 判断元素之间的垂直间距
              const spaceBefore = rect.top - prevRect.bottom;
              const spaceAfter = nextRect.top - rect.bottom;

              // 标题通常与前面的内容有较大间距，与后面的内容间距较小
              const hasProperSpacing =
                spaceBefore > 5 && spaceBefore > spaceAfter;

              // 检查文本长度 - 标题通常短于周围段落
              const headingText = heading.textContent?.trim() || '';
              const prevText = prevElement.textContent?.trim() || '';
              const nextText = nextElement.textContent?.trim() || '';

              const isShorterThanPrev =
                headingText.length < prevText.length * 0.8;
              const isShorterThanNext =
                headingText.length < nextText.length * 0.8;

              // 结合间距和长度判断
              if (
                !hasProperSpacing &&
                !(isShorterThanPrev && isShorterThanNext)
              ) {
                // 还可以检查样式差异
                const headingStyle = window.getComputedStyle(heading);
                const prevStyle = window.getComputedStyle(prevElement);
                const nextStyle = window.getComputedStyle(nextElement);

                const headingFontSize = parseInt(headingStyle.fontSize, 10);
                const prevFontSize = parseInt(prevStyle.fontSize, 10);
                const nextFontSize = parseInt(nextStyle.fontSize, 10);

                const isLargerFont =
                  headingFontSize > prevFontSize &&
                  headingFontSize > nextFontSize;

                if (!isLargerFont) {
                  return false; // 可能是普通段落
                }
              }
            }
          }

          return true;
        });

        console.log('最终筛选后的标题数量:', finalHeadings.length);

        // 对标题进行排序，确保它们按照在文档中的顺序出现
        finalHeadings.sort((a, b) => {
          const aRect = a.getBoundingClientRect();
          const bRect = b.getBoundingClientRect();

          // 首先按 y 坐标排序
          if (Math.abs(aRect.top - bRect.top) > 5) {
            return aRect.top - bRect.top;
          }

          // 如果 y 坐标相近，则按 x 坐标排序
          return aRect.left - bRect.left;
        });

        // 分析标题层级
        const headingLevels = determineHeadingLevels(finalHeadings);

        // 创建目录树结构
        const toc = buildTocTree(finalHeadings, headingLevels);

        console.log('构建的目录树节点数:', toc.length);
        setTocData(toc);
        setFilteredTocData(toc);
      } catch (error) {
        console.error('提取目录时出错:', error);
      } finally {
        setTocLoading(false);
      }
    }, 1000); // 给予足够的时间让文档渲染完成
  };

  // 目录搜索函数，添加高亮处理
  const handleTocSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value.trim().toLowerCase();
    setTocSearchValue(value);

    if (!value) {
      setFilteredTocData(tocData);
      return;
    }

    // 递归搜索节点并高亮匹配的文本
    const searchNodes = (nodes: DataNode[]): DataNode[] => {
      return nodes
        .map((node) => {
          // 检查当前节点是否匹配
          const nodeTitle = node.title?.toString() || '';
          const matchesTitle = nodeTitle.toLowerCase().includes(value);

          // 检查子节点是否匹配
          const matchingChildren = node.children
            ? searchNodes(node.children)
            : [];

          // 如果当前节点匹配或有匹配的子节点，则保留该节点
          if (matchesTitle || matchingChildren.length > 0) {
            // 如果当前节点标题匹配，则高亮匹配的部分
            let highlightedTitle: React.ReactNode = nodeTitle;

            if (matchesTitle) {
              const lowerTitle = nodeTitle.toLowerCase();
              const startIndex = lowerTitle.indexOf(value);
              const endIndex = startIndex + value.length;

              highlightedTitle = (
                <span>
                  {nodeTitle.substring(0, startIndex)}
                  <span style={{ backgroundColor: 'yellow', padding: '0 2px' }}>
                    {nodeTitle.substring(startIndex, endIndex)}
                  </span>
                  {nodeTitle.substring(endIndex)}
                </span>
              );
            }

            return {
              ...node,
              title: tocSearchValue ? highlightedTitle : nodeTitle,
              children: matchingChildren,
            } as DataNode;
          }

          // 否则过滤掉该节点
          return null;
        })
        .filter((node): node is DataNode => node !== null);
    };

    const filtered = searchNodes(tocData);
    setFilteredTocData(filtered);
  };

  // 处理目录项点击事件，不需要关闭抽屉，因为目录已经固定显示
  const handleTocItemClick = (selectedKeys: React.Key[]) => {
    if (selectedKeys.length === 0) return;

    const selectedKey = selectedKeys[0].toString();
    const selectedElement = document.getElementById(selectedKey);

    if (selectedElement) {
      // 不再关闭目录
      // setTocVisible(false);

      // 重置搜索状态
      if (tocSearchValue) {
        setTocSearchValue('');
        setFilteredTocData(tocData);
      }

      // 直接滚动到对应位置
      selectedElement.scrollIntoView({
        behavior: 'smooth',
        block: 'start',
        inline: 'nearest',
      });

      // 添加高亮效果
      selectedElement.classList.add('toc-highlighted');

      // 延迟移除高亮效果
      setTimeout(() => {
        selectedElement.classList.remove('toc-highlighted');
      }, 2000);
    }
  };

  // 处理 DOCX 文件预览
  useEffect(() => {
    if (
      (fileType === 'docx' || fileType === 'doc') &&
      fileData &&
      docxContainerRef.current
    ) {
      // 清空容器
      if (docxContainerRef.current) {
        docxContainerRef.current.innerHTML = '';
      }

      try {
        // 获取 Blob 对象
        fetch(fileData)
          .then((res) => {
            if (!res.ok) {
              throw new Error(`HTTP 错误: ${res.status}`);
            }
            return res.blob();
          })
          .then((blob) => {
            if (!blob || blob.size === 0) {
              throw new Error('获取到的文件数据为空');
            }

            if (docxContainerRef.current) {
              // 检查是否为有效的 docx 文件类型
              if (
                blob.type &&
                !blob.type.includes(
                  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                ) &&
                !blob.type.includes('application/octet-stream')
              ) {
              }

              const options = {
                inWrapper: true,
                ignoreWidth: false,
                ignoreHeight: false,
                ignoreFonts: false,
                debug: true,
                experimental: false,
                className: 'docx',
                useBase64URL: true,
                maxWidth: undefined,
                breakPages: true,
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
                pageStyle: {
                  margin: '20px auto',
                  boxSizing: 'border-box',
                  boxShadow: 'none',
                  padding: '0',
                  border: 'none',
                },
              };

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
                  setError(null);
                  // 文档渲染完成后，提取目录结构
                  extractTableOfContents();
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
      setTimeout(() => {
        if (pdfContainerRef.current) {
          const pageElement = pdfContainerRef.current.querySelector(
            `[data-page-number="${newPage}"]`,
          );
          if (pageElement) {
            pageElement.scrollIntoView({ behavior: 'smooth' });
          }
        }
      }, 50);
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
            // 确保全屏元素可滚动
            if (document.fullscreenElement) {
              (document.fullscreenElement as HTMLElement).style.overflow =
                'auto';
            }
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
            // 确保全屏元素可滚动
            if (document.fullscreenElement) {
              (document.fullscreenElement as HTMLElement).style.overflow =
                'auto';
            }
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
    if (loading) {
      return (
        <div style={{ textAlign: 'center', marginTop: '20px' }}>
          <Spin tip="加载中..." />
        </div>
      );
    }

    if (!fileData) {
      return <div>没有文件数据</div>;
    }

    switch (fileType) {
      case 'pdf':
        return (
          <div style={{ position: 'relative' }}>
            <div
              style={{
                position: 'sticky',
                top: 0,
                zIndex: 10,
                background: '#fff',
                padding: '10px 0',
                borderBottom: '1px solid #f0f0f0',
                display: 'flex',
                justifyContent: 'center',
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
                overflow: 'auto',
                height: isFullscreen ? '100vh' : 'auto',
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
                    inputRef={(ref) => {
                      if (ref) {
                        // 手动添加页码属性，确保可以被查询到
                        ref.setAttribute(
                          'data-page-number',
                          (index + 1).toString(),
                        );
                      }
                    }}
                  />
                ))}
              </Document>
            </div>
          </div>
        );
      case 'docx':
      case 'doc':
        return (
          <div style={{ backgroundColor: 'white' }}>
            <div
              style={{
                position: 'sticky',
                top: 0,
                zIndex: 10,
                background: '#fff',
                padding: '10px 0',
                borderBottom: '1px solid #f0f0f0',
                display: 'flex',
                justifyContent: 'center',
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
                <Tooltip title={tocVisible ? '隐藏目录' : '显示目录'}>
                  {tocData.length > 0 ? (
                    <Badge count={tocData.length} size="small" offset={[2, -2]}>
                      <Button
                        icon={
                          tocVisible ? (
                            <MenuFoldOutlined />
                          ) : (
                            <MenuUnfoldOutlined />
                          )
                        }
                        onClick={() => setTocVisible(!tocVisible)}
                        type={tocVisible ? 'primary' : 'default'}
                      />
                    </Badge>
                  ) : (
                    <Button
                      icon={<UnorderedListOutlined />}
                      onClick={() => setTocVisible(!tocVisible)}
                      disabled={tocLoading || tocData.length === 0}
                    />
                  )}
                </Tooltip>
              </Space>
            </div>

            <div style={{ display: 'flex', height: 'calc(100vh - 170px)' }}>
              {/* 文档内容区域 */}
              <div
                style={{
                  flex:
                    tocVisible && tocData.length > 0 ? '1 1 75%' : '1 1 100%',
                  overflow: 'auto',
                  transition: 'flex 0.3s ease',
                  position: 'relative',
                }}
              >
                <div
                  ref={docxContainerRef}
                  style={{
                    width: '100%',
                    padding: '20px',
                    minHeight: '300px',
                    background: '#fff',
                    position: 'relative',
                    border: 'none',
                    borderRadius: '0',
                    boxShadow: 'none',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                  }}
                />
              </div>

              {/* 侧边栏目录区域 */}
              {tocVisible && tocData.length > 0 && (
                <div
                  style={{
                    flex: '0 0 25%',
                    maxWidth: '300px',
                    height: '100%',
                    borderLeft: '1px solid #f0f0f0',
                    display: 'flex',
                    flexDirection: 'column',
                    transition: 'all 0.3s ease',
                    background: '#fff',
                  }}
                >
                  <div
                    style={{
                      padding: '8px 16px',
                      borderBottom: '1px solid #f0f0f0',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                    }}
                  >
                    <div
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center' }}>
                        <UnorderedListOutlined style={{ marginRight: 8 }} />
                        <span style={{ fontWeight: 'bold' }}>文档目录</span>
                        {tocData.length > 0 && (
                          <Badge
                            count={tocData.length}
                            style={{
                              backgroundColor: '#52c41a',
                              marginLeft: 8,
                            }}
                          />
                        )}
                      </div>
                      <Button
                        type="text"
                        icon={<MenuFoldOutlined />}
                        size="small"
                        onClick={() => setTocVisible(false)}
                      />
                    </div>
                    <Input
                      placeholder="搜索标题..."
                      prefix={<SearchOutlined />}
                      value={tocSearchValue}
                      onChange={handleTocSearch}
                      allowClear
                      size="small"
                      onPressEnter={() => {
                        if (filteredTocData.length === 1) {
                          handleTocItemClick([filteredTocData[0].key]);
                        }
                      }}
                    />
                    <div style={{ color: '#999', fontSize: '12px' }}>
                      点击标题可快速跳转到对应位置
                    </div>
                  </div>

                  <div style={{ overflow: 'auto', flex: 1, padding: '8px 0' }}>
                    {tocLoading ? (
                      <div style={{ textAlign: 'center', padding: '20px 0' }}>
                        <Spin tip="加载目录中..." />
                      </div>
                    ) : filteredTocData.length > 0 ? (
                      <Tree
                        treeData={filteredTocData}
                        defaultExpandAll
                        onSelect={handleTocItemClick}
                        blockNode
                        className="doc-toc-tree"
                      />
                    ) : (
                      <Empty
                        image={Empty.PRESENTED_IMAGE_SIMPLE}
                        description="没有找到匹配的标题"
                        style={{ margin: '40px 0' }}
                      />
                    )}
                  </div>
                </div>
              )}
            </div>

            {error && (
              <div style={{ color: 'red', margin: '10px 0' }}>{error}</div>
            )}
          </div>
        );
      default:
        return <div>无法预览该文件格式，请下载后查看</div>;
    }
  };

  // 添加自定义样式，优化 DOCX 文档显示效果
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
        transform-origin: top center;
        box-shadow: none !important;
        margin: 0 auto !important;
      }
      .docx-wrapper {
        background: white !important;
        padding: 0 !important;
        margin: 0 auto !important;
        box-shadow: none !important;
        width: auto !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
      }
      .docx-wrapper::before,
      .docx-wrapper::after {
        display: none !important;
        box-shadow: none !important;
      }
      .docx-wrapper > div {
        background: white !important;
        box-shadow: none !important;
        width: auto !important;
        max-width: 100% !important;
        margin: 0 auto !important;
      }
      .docx p, .docx div, .docx section, .docx * {
        box-shadow: none !important;
      }
      /* 保持原始大小的样式 */
      .docx-wrapper > div > div {
        width: auto !important;
        margin: 0 auto !important;
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

      // 添加目录树的样式
      const style = document.createElement('style');
      style.textContent = `
        .doc-toc-tree .ant-tree-treenode {
          width: 100%;
          padding: 4px 8px !important;
          transition: background-color 0.3s ease;
        }
        .doc-toc-tree .ant-tree-node-content-wrapper {
          width: calc(100% - 24px);
          white-space: normal;
          word-break: break-word;
          height: auto !important;
          line-height: 1.4;
          padding: 4px 4px !important;
        }
        .doc-toc-tree .ant-tree-treenode:hover {
          background-color: #f5f5f5;
        }
        .toc-highlighted {
          background-color: rgba(255, 255, 0, 0.3) !important;
          transition: background-color 0.5s ease;
        }
        
        /* 侧边栏样式 */
        .doc-toc-sidebar {
          border-left: 1px solid #f0f0f0;
          background: white;
          z-index: 100;
        }
        
        @media (max-width: 768px) {
          .doc-toc-sidebar {
            position: fixed;
            right: 0;
            top: 0;
            height: 100%;
            width: 250px;
            box-shadow: -2px 0 8px rgba(0,0,0,0.15);
          }
        }
      `;
      document.head.appendChild(style);

      return () => {
        document.head.removeChild(style);
      };
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
