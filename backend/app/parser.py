import PyPDF2
from docx import Document

class DocumentParser:
    """文档解析器基类"""
    def parse(self, file_path: str) -> str:
        raise NotImplementedError
    
class PDFEncryptedError(Exception):
    """当 PDF 文件加密且无法解析时抛出的异常"""
    pass

class PDFParser(DocumentParser):
    """PDF文档解析器"""
    def parse(self, file_path: str) -> str:
        try:
            # 创建PDF reader对象
            pdf_reader = PyPDF2.PdfReader(file_path)
            
            # 检查是否加密
            if pdf_reader.is_encrypted:
                try:
                    # 尝试用空密码解密（对于只有权限密码的PDF通常可行）
                    pdf_reader.decrypt('')
                    
                    # 尝试提取文本
                    text_content = []
                    for page in pdf_reader.pages:
                        text_content.append(page.extract_text())
                    return "\n".join(text_content)
                except:
                    raise PDFEncryptedError("无法解析加密的PDF文件，请先解除文件加密后再上传")
                
            # 提取所有页面的文本
            text_content = []
            for page in pdf_reader.pages:
                text_content.append(page.extract_text())
                
            return "\n".join(text_content)
        except Exception as e:
            if "PyCryptodome is required for AES algorithm" in str(e):
                raise PDFEncryptedError("无法解析加密的PDF文件，请先解除文件加密后再上传")
            elif "File has not been decrypted" in str(e):
                raise PDFEncryptedError("无法解析加密的PDF文件，请先解除文件加密后再上传")
            else:
                raise Exception(f"PDF解析错误: {str(e)}")

class DocxParser(DocumentParser):
    """Word文档解析器"""
    def parse(self, file_path: str) -> str:
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

def get_parser(file_type: str) -> DocumentParser:
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
