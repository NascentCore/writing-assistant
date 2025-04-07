import markdownit from 'markdown-it';
import React from 'react';
import { InlineReferencesContent } from './InlineReferencesContent';
import ReferenceMarker from './ReferenceMarker';
import { ReferenceFile } from './type';

const md = markdownit({ html: true, breaks: true });

/**
 * 渲染消息文本，处理引用标记
 *
 * @param content 要渲染的内容文本
 * @param referenceFiles 引用文件数组
 * @returns 渲染后的React组件
 */
const ReferenceContentRenderer: React.FC<{
  content: string;
  referenceFiles?: ReferenceFile[];
}> = ({ content, referenceFiles }) => {
  // 如果没有引用文件，直接渲染markdown
  if (!referenceFiles || referenceFiles.length === 0) {
    return <div dangerouslySetInnerHTML={{ __html: md.render(content) }} />;
  }

  // 使用内联引用标记组件渲染
  return (
    <InlineReferencesContent
      content={content}
      referenceFiles={referenceFiles}
    />
  );
};

export default ReferenceContentRenderer;
export * from './type';
export { InlineReferencesContent, ReferenceMarker };
