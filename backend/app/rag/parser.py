import asyncio
import PyPDF2
from docx import Document
from app.config import settings
import openai
import aiofiles
import pytesseract
from pdf2image import convert_from_path
import time
import logging
import cv2
import numpy as np

logger = logging.getLogger(__name__)

class FileParser:
    """文件解析器基类"""
    def content(self, file_path: str) -> str:
        raise NotImplementedError

    async def async_content(self, file_path: str) -> str:
        raise NotImplementedError

    async def summary(self, content: str, length: str = "small") -> str:
        """
        使用LLM生成文章摘要
        
        Args:
            content: 需要总结的文章内容
            length: 摘要长度 - "small"(100字), "medium"(500字), "large"(1000字)
            
        Returns:
            str: 文章摘要
        """
        
        # 根据长度设置提示词
        length_prompts = {
            "small": "请用100字左右总结这篇文章的要点：",
            "medium": "请用500字左右总结这篇文章的主要内容：",
            "large": "请用1000字左右详细总结这篇文章的内容："
        }
        
        prompt = length_prompts.get(length, length_prompts["small"])
        
        try:
            # 配置OpenAI客户端
            client = openai.AsyncOpenAI(
                base_url=settings.RAG_LLM_BASE_URL,
                api_key=settings.RAG_LLM_API_KEY
            )
            
            # 调用API生成摘要
            completion = await client.chat.completions.create(
                model=settings.RAG_LLM_MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的文章摘要助手。"},
                    {"role": "user", "content": f"{prompt}\n\n{content}"}
                ],
                temperature=settings.RAG_LLM_TEMPERATURE,
                max_tokens=settings.RAG_LLM_MAX_TOKENS,
                timeout=settings.RAG_LLM_REQUEST_TIMEOUT
            )
            
            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            raise Exception(f"生成摘要时发生错误: {str(e)}")

class PDFEncryptedError(Exception):
    """当 PDF 文件加密且无法解析时抛出的异常"""
    pass

class PDFParser(FileParser):
    """PDF文档解析器，支持文本提取和OCR图像解析（并发优化版）"""
    
    def preprocess_image(self, image):
        """对OCR图片进行预处理"""
        img = np.array(image)
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary

    async def ocr_page(self, file_path: str, page_number: int) -> str:
        """并发OCR解析单页PDF"""
        try:
            # 转换PDF页为图片（在独立线程中执行）
            convert_start = time.time()
            images = await asyncio.to_thread(
                convert_from_path, file_path, first_page=page_number, last_page=page_number, dpi=300, fmt='jpeg', thread_count=4
            )
            logger.debug(f"第{page_number}页PDF转图片耗时: {time.time() - convert_start:.2f}秒")

            if not images:
                logger.warning(f"第{page_number}页转换图片失败")
                return ""

            # 进行OCR识别
            ocr_start = time.time()
            ocr_tasks = [
                asyncio.to_thread(self.ocr_image, image) for image in images
            ]
            ocr_texts = await asyncio.gather(*ocr_tasks)
            ocr_time = time.time() - ocr_start
            logger.debug(f"第{page_number}页OCR总耗时: {ocr_time:.2f}秒")

            return "\n".join(ocr_texts)
        except Exception as e:
            logger.error(f"第{page_number}页OCR解析失败: {str(e)}")
            return "[OCR 解析失败]"

    def ocr_image(self, image):
        """对单张图片进行OCR"""
        processed_image = self.preprocess_image(image)
        ocr_text = pytesseract.image_to_string(
            processed_image, lang='chi_sim', config='--oem 3 --psm 4'
        )
        return ''.join(ocr_text.split())

    def content(self, file_path: str) -> str:
        """同步方法，通过运行异步方法实现"""
        return asyncio.run(self.async_content(file_path))
    
    async def async_content(self, file_path: str) -> str:
        """异步解析PDF文本和OCR"""
        start_time = time.time()
        text_content = []

        try:
            # 读取PDF
            pdf_reader = PyPDF2.PdfReader(file_path)

            # 检查是否加密
            if pdf_reader.is_encrypted:
                try:
                    pdf_reader.decrypt('')
                except Exception:
                    raise PDFEncryptedError("无法解析加密的PDF文件，请先解除文件加密后再上传")

            total_pages = len(pdf_reader.pages)
            logger.debug(f"PDF总页数: {total_pages}")

            # 遍历PDF页面，提取文本或OCR
            tasks = []
            for i, page in enumerate(pdf_reader.pages, start=1):
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text_content.append(page_text)
                    logger.debug(f"第{i}页文本提取成功")
                else:
                    # 创建异步OCR任务
                    tasks.append(self.ocr_page(file_path, i))

            # 并行执行OCR任务
            if tasks:
                ocr_results = await asyncio.gather(*tasks)
                text_content.extend(ocr_results)

            total_time = time.time() - start_time
            logger.info(f"PDF解析完成，{file_path}，共{total_pages}页，耗时: {total_time:.2f}秒")

            return "\n".join(text_content)
        except Exception as e:
            raise Exception(f"PDF解析错误: {str(e)}")
    
class DocxParser(FileParser):
    """Word文档解析器"""
    def content(self, file_path: str) -> str:
        try:
            # 加载Word文档
            doc = Document(file_path)
            
            # 提取所有段落的文本
            text_content = []
            for paragraph in doc.paragraphs:
                if paragraph.text.strip():  # 只添加非空段落
                    text_content.append(paragraph.text)
                    
            return "\n".join(text_content)
        except Exception as e:
            raise Exception(f"Word文档解析错误: {str(e)}")
    
    async def async_content(self, file_path: str) -> str:
        return await asyncio.to_thread(self.content, file_path)

def get_parser(file_type: str) -> FileParser:
    """
    根据文件类型返回对应的解析器
    
    Args:
        file_type: 文件类型 ('pdf' 或 'docx')
        
    Returns:
        DocumentParser: 对应的文档解析器实例
    """
    parsers = {
        'pdf': PDFParser(),
        'docx': DocxParser()
    }
    
    parser = parsers.get(file_type.lower())
    if not parser:
        raise ValueError(f"不支持的文件类型: {file_type}")
    
    return parser

def get_file_format(file_path: str) -> str:
    """
    通过读取文件头部信息来判断文件格式
    
    Args:
        file_path: 文件路径
        
    Returns:
        str: 文件格式 ('pdf' 或 'docx')
    """
    with open(file_path, 'rb') as f:
        header = f.read(4)
        
    # PDF文件头: %PDF (25 50 44 46)
    if header.startswith(b'%PDF'):
        return 'pdf'
    # DOCX文件头: PK (50 4B)
    elif header.startswith(b'PK'):
        return 'docx'
    else:
        raise ValueError(f"不支持的文件格式")

class BaseParser:
    async def content(self, file_path: str) -> str:
        """异步读取文件内容"""
        async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
            return await f.read()

