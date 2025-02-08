declare module 'html2pdf.js' {
  const html2pdf: any;
  export default html2pdf;
}

declare module 'turndown' {
  class TurndownService {
    constructor(options?: {
      headingStyle?: string;
      codeBlockStyle?: string;
      bulletListMarker?: string;
      emDelimiter?: string;
    });
    turndown(html: string): string;
  }
  export default TurndownService;
}
