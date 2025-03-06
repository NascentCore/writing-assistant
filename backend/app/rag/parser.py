import PyPDF2
from docx import Document
from app.config import settings
import openai
import aiofiles
import pytesseract
from pdf2image import convert_from_path
import asyncio

class FileParser:
    """文件解析器基类"""
    def content(self, file_path: str) -> str:
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
    """PDF文档解析器，支持文本提取和OCR图像解析"""
    def content(self, file_path: str) -> str:
        text_content = []
        try:
            # 创建PDF reader对象
            pdf_reader = PyPDF2.PdfReader(file_path)
            
            # 检查是否加密
            if pdf_reader.is_encrypted:
                try:
                    pdf_reader.decrypt('')
                except Exception:
                    raise PDFEncryptedError("无法解析加密的PDF文件，请先解除文件加密后再上传")
            
            # 遍历所有页面
            for i, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                # 如果页面文本有效，则使用提取的文本
                if page_text and page_text.strip():
                    text_content.append(page_text)
                else:
                    # 否则使用OCR：将当前页转换为图片，再识别文字
                    try:
                        # convert_from_path 的页码参数是 1-indexed
                        images = convert_from_path(file_path, 
                                                   first_page=i+1, 
                                                   last_page=i+1, 
                                                   dpi=300,                            
                                                   fmt='jpeg',
                                                   thread_count=4)
                        if images:
                            for image in images:
                                # 优化图像处理（转换为灰度图提升OCR速度）
                                image = image.convert('L')
                                # 执行快速OCR
                                ocr_text = pytesseract.image_to_string(
                                    image,
                                    lang='chi_sim',
                                    config='--oem 1 --psm 6'
                                )
                                page_text += ocr_text + "\n"
                            # # 使用 pytesseract 进行OCR，lang参数可根据需要调整
                            # ocr_text = pytesseract.image_to_string(images[0], lang='chi_sim', config='--oem 1 --psm 6')
                            # text_content.append(ocr_text)
                            text_content.append(page_text)
                        else:
                            text_content.append("")
                    except Exception:
                        text_content.append("[OCR 解析失败]")
            
            return "\n".join(text_content)
        except Exception as e:
            # 针对加密相关异常的处理
            if "PyCryptodome is required for AES algorithm" in str(e):
                raise PDFEncryptedError("无法解析加密的PDF文件，请先解除文件加密后再上传")
            elif "File has not been decrypted" in str(e):
                raise PDFEncryptedError("无法解析加密的PDF文件，请先解除文件加密后再上传")
            else:
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

