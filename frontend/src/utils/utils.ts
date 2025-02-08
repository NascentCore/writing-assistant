import { Document, HeadingLevel, Packer, Paragraph, TextRun } from 'docx';
import html2pdf from 'html2pdf.js';
import TurndownService from 'turndown';

// 配置 turndown
const turndownService = new TurndownService({
  headingStyle: 'atx',
  codeBlockStyle: 'fenced',
  bulletListMarker: '-',
  emDelimiter: '*',
});

// 解析 markdown 为文档元素
const parseMarkdownToDocElements = (markdown: string): Paragraph[] => {
  const elements: Paragraph[] = [];
  const lines = markdown.split('\n');

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // 处理标题
    if (line.startsWith('#')) {
      const level = line.match(/^#+/)?.[0].length || 1;
      const text = line.replace(/^#+\s/, '');
      const headingKey = `HEADING_${level}` as keyof typeof HeadingLevel;
      elements.push(
        new Paragraph({
          children: [
            new TextRun({
              text,
              size: 24,
              color: '000000',
              bold: true,
            }),
          ],
          heading: HeadingLevel[headingKey],
          spacing: {
            before: 240,
            after: 120,
          },
        }),
      );
      continue;
    }

    // 处理代码块
    if (line.startsWith('```')) {
      let codeContent = '';
      i++;
      while (i < lines.length && !lines[i].startsWith('```')) {
        codeContent += lines[i] + '\n';
        i++;
      }
      elements.push(
        new Paragraph({
          children: [
            new TextRun({
              text: codeContent,
              font: 'Consolas',
              size: 20,
            }),
          ],
          spacing: {
            before: 240,
            after: 240,
          },
          shading: {
            type: 'solid',
            color: 'F5F5F5',
          },
        }),
      );
      continue;
    }

    // 处理普通段落
    if (line.trim()) {
      elements.push(
        new Paragraph({
          children: [
            new TextRun({
              text: line,
              size: 24,
            }),
          ],
          spacing: {
            before: 120,
            after: 120,
          },
        }),
      );
    }
  }

  return elements;
};

export const saveAsDocx = async (htmlContent: string): Promise<boolean> => {
  try {
    // 1. HTML -> Markdown
    let markdown = turndownService.turndown(htmlContent);

    // 移除两个或更多的星号（包括空格分隔的情况）
    markdown = markdown.replace(/(\*\s*){2,}/g, '');

    // 2. Markdown -> Word 文档元素
    const docElements = parseMarkdownToDocElements(markdown);

    // 3. 创建文档
    const doc = new Document({
      sections: [
        {
          properties: {
            page: {
              margin: {
                top: 1440, // 1 inch
                right: 1440,
                bottom: 1440,
                left: 1440,
              },
            },
          },
          children: docElements,
        },
      ],
      styles: {
        paragraphStyles: [
          {
            id: 'Normal',
            name: 'Normal',
            basedOn: 'Normal',
            next: 'Normal',
            quickFormat: true,
            run: {
              font: 'Microsoft YaHei',
              size: 24,
              color: '#000000',
            },
          },
        ],
      },
    });

    // 4. 生成并下载文件
    const blob = await Packer.toBlob(doc);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = '售前方案写作助手.docx';
    link.click();
    window.URL.revokeObjectURL(url);

    return true;
  } catch (error) {
    console.error('转换文档失败:', error);
    return false;
  }
};

export const saveAsPdf = (): Promise<void> => {
  const element = document.querySelector('.aie-container-main');

  const opt = {
    margin: 1,
    filename: '售前方案.pdf',
    image: { type: 'jpeg', quality: 0.98 },
    html2canvas: { scale: 2 },
    jsPDF: {
      unit: 'in',
      format: 'letter',
      orientation: 'portrait',
    },
  };

  return html2pdf().set(opt).from(element).save();
};
