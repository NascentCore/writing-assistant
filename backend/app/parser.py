import PyPDF2
from docx import Document
from docx.document import Document as _Document
from docx.oxml.text.paragraph import CT_P
from docx.text.paragraph import Paragraph
from docx.oxml.table import CT_Tbl
from docx.table import _Cell, Table, _Row
from typing import List, Union, Optional, Dict, Any

class DocumentParser:
    """文档解析器基类"""
    def parse(self, file_path: str) -> Union[Document, str]:
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
    def parse(self, file_path: str) -> Document:
        """
        解析Word文档，返回Document对象
        
        Args:
            file_path: 文件路径
            
        Returns:
            Document: python-docx的Document对象
        """
        try:
            return Document(file_path)
        except Exception as e:
            raise Exception(f"Word文档解析错误: {str(e)}")
    
    def get_outline_structure(self, doc: Document) -> Dict[str, Any]:
        """
        从Word文档中提取大纲结构
        
        Args:
            doc: python-docx的Document对象
            
        Returns:
            Dict: 包含大纲结构的字典
        """
        # 提取标题（使用第一个段落作为标题）
        title = doc.paragraphs[0].text if doc.paragraphs else "未命名大纲"
        
        # 构建大纲结构
        outline_data = {
            "title": title,
            "sub_paragraphs": []
        }
        
        # 遍历段落，根据段落样式和缩进级别构建大纲结构
        paragraphs_stack = []
        
        for paragraph in doc.paragraphs[1:]:  # 跳过标题段落
            if not paragraph.text.strip():
                continue
            
            # 获取段落级别
            level = self._get_paragraph_level(paragraph)
            
            # 构建段落数据
            para_data = {
                "title": paragraph.text,
                "description": self._get_paragraph_description(paragraph),
                "level": level,
                "children": []
            }
            
            # 如果是一级段落，添加count_style
            if level == 1:
                para_data["count_style"] = "medium"
            
            # 根据层级关系添加到正确的父节点
            while paragraphs_stack and paragraphs_stack[-1]["level"] >= level:
                paragraphs_stack.pop()
            
            if paragraphs_stack:
                if "children" not in paragraphs_stack[-1]:
                    paragraphs_stack[-1]["children"] = []
                paragraphs_stack[-1]["children"].append(para_data)
            else:
                outline_data["sub_paragraphs"].append(para_data)
            
            paragraphs_stack.append(para_data)
        
        return outline_data
    
    def _get_paragraph_level(self, paragraph: Paragraph) -> int:
        """
        获取段落的层级
        
        Args:
            paragraph: 段落对象
            
        Returns:
            int: 段落层级（1-6）
        """
        try:
            # 首先检查是否是标题样式
            if hasattr(paragraph, 'style') and paragraph.style and paragraph.style.name:
                if paragraph.style.name.startswith('Heading'):
                    try:
                        level = int(paragraph.style.name[-1])
                        if 1 <= level <= 6:
                            return level
                    except (ValueError, IndexError):
                        pass
            
            # 检查大纲级别
            try:
                if (paragraph._element is not None and 
                    hasattr(paragraph._element, 'pPr') and 
                    paragraph._element.pPr is not None):
                    pPr = paragraph._element.pPr
                    if hasattr(pPr, 'outlineLvl') and pPr.outlineLvl is not None:
                        val = pPr.outlineLvl.val
                        if val is not None:
                            return min(int(val) + 1, 6)
            except (AttributeError, ValueError):
                pass
            
            # 根据缩进判断级别
            try:
                if (hasattr(paragraph, 'paragraph_format') and 
                    paragraph.paragraph_format is not None and
                    paragraph.paragraph_format.left_indent is not None):
                    indent = paragraph.paragraph_format.left_indent.pt
                    if indent > 0:
                        return min(max(int(indent / 36) + 1, 1), 6)  # 36pt = 0.5英寸
            except (AttributeError, ValueError):
                pass
            
            # 检查是否使用项目符号或编号
            try:
                if (hasattr(paragraph, '_p') and 
                    paragraph._p is not None and 
                    hasattr(paragraph._p, 'pPr') and 
                    paragraph._p.pPr is not None and
                    hasattr(paragraph._p.pPr, 'numPr') and 
                    paragraph._p.pPr.numPr is not None and
                    hasattr(paragraph._p.pPr.numPr, 'ilvl') and 
                    paragraph._p.pPr.numPr.ilvl is not None and
                    hasattr(paragraph._p.pPr.numPr.ilvl, 'val')):
                    val = paragraph._p.pPr.numPr.ilvl.val
                    if val is not None:
                        return min(int(val) + 1, 6)
            except (AttributeError, ValueError):
                pass
            
            return 1
            
        except Exception as e:
            print(f"获取段落级别时出错: {str(e)}")  # 记录错误但不影响处理
            return 1  # 出错时返回默认级别
    
    def _get_paragraph_description(self, paragraph: Paragraph) -> str:
        """
        获取段落的描述（查找下一个非空段落直到遇到新的标题）
        
        Args:
            paragraph: 段落对象
            
        Returns:
            str: 段落描述
        """
        description_parts = []
        next_p = paragraph._element.getnext()
        
        while (next_p is not None and 
               isinstance(next_p, CT_P) and 
               not Paragraph(next_p, paragraph._parent).style.name.startswith('Heading')):
            next_para = Paragraph(next_p, paragraph._parent)
            if next_para.text.strip():
                description_parts.append(next_para.text)
            next_p = next_p.getnext()
        
        return "\n".join(description_parts)

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
