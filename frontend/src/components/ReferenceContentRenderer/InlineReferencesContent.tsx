import markdownit from 'markdown-it';
import React, { useEffect, useRef } from 'react';
import ReactDOM from 'react-dom/client';
import ReferenceMarker from './ReferenceMarker';
import { InlineReferencesContentProps } from './type';

const md = markdownit({ html: true, breaks: true });

/**
 * 内联引用标记渲染组件
 */
export const InlineReferencesContent: React.FC<
  InlineReferencesContentProps
> = ({ content, referenceFiles = [] }) => {
  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!contentRef.current || referenceFiles.length === 0) return;

    // 查找所有引用标记的占位符
    const placeholders = contentRef.current.querySelectorAll(
      '.reference-marker-placeholder',
    );

    placeholders.forEach((placeholder) => {
      const indexAttr = placeholder.getAttribute('data-index');
      if (!indexAttr) return;

      const index = parseInt(indexAttr, 10);
      if (isNaN(index) || index < 0 || index >= referenceFiles.length) return;

      // 创建容器
      const container = document.createElement('span');
      container.style.display = 'inline';

      // 替换占位符
      placeholder.replaceWith(container);

      // 渲染React组件
      const root = ReactDOM.createRoot(container);
      root.render(
        <ReferenceMarker index={index} referenceFile={referenceFiles[index]} />,
      );
    });
  }, [content, referenceFiles]);

  // 处理内容，替换引用标记为占位符
  const processContent = () => {
    // 使用正则表达式找到所有[数字]格式的引用
    const regex = /\[(\d+)\]/g;
    let result = md.render(content);
    let match;

    // 查找所有匹配并替换
    while ((match = regex.exec(content)) !== null) {
      const refNumber = parseInt(match[1], 10);
      const index = refNumber - 1;

      if (referenceFiles && index >= 0 && index < referenceFiles.length) {
        // 创建一个特殊的span作为占位符
        const placeholder = `<span class="reference-marker-placeholder" data-index="${index}"></span>`;

        // 替换原始文本中的引用标记
        result = result.replace(match[0], placeholder);
      }
    }

    return result;
  };

  return (
    <div
      ref={contentRef}
      className="reference-content"
      dangerouslySetInnerHTML={{ __html: processContent() }}
    />
  );
};
