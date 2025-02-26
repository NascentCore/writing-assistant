from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.chains import LLMChain
from typing import List, Dict, Any, Optional
from app.config import settings
import json
import logging

logger = logging.getLogger(__name__)

class OutlineGenerator:
    """使用LangChain调用大模型生成结构化大纲"""
    
    def __init__(self):
        # 初始化LLM
        self.llm = ChatOpenAI(
            model=settings.LLM_MODELS[0]["model"],
            openai_api_key=settings.LLM_MODELS[0]["api_key"],
            openai_api_base=settings.LLM_MODELS[0]["base_url"],
            temperature=0.7,
        )
        
        # 初始化输出解析器
        self.parser = JsonOutputParser()
        
    def generate_outline(self, prompt: str, file_contents: List[str] = None) -> Dict[str, Any]:
        """
        生成结构化大纲
        
        Args:
            prompt: 用户提供的写作提示
            file_contents: 用户上传的文件内容列表
            
        Returns:
            Dict: 包含大纲结构的字典
        """
        # 构建提示模板
        template = """
        你是一个专业的写作助手，请根据用户的写作需求生成一个结构化的文章大纲。
        
        用户的写作需求是: {prompt}
        
        {file_context}
        
        请生成一个包含以下内容的结构化大纲:
        1. 文章标题
        2. 多个子段落，每个子段落包含:
           - 标题
           - 简短描述
           - 篇幅风格(short/medium/long)
        
        以JSON格式返回，格式如下:
        {{
            "title": "文章标题",
            "sub_paragraphs": [
                {{
                    "title": "子段落标题",
                    "description": "子段落描述",
                    "count_style": "short/medium/long"
                }},
                // 更多子段落...
            ]
        }}
        
        确保返回的是有效的JSON格式。
        """
        
        # 处理文件内容
        file_context = ""
        if file_contents and len(file_contents) > 0:
            file_context = "参考以下文件内容:\n" + "\n".join(file_contents)
        else:
            file_context = "没有提供参考文件内容。"
        
        # 创建提示
        prompt_template = ChatPromptTemplate.from_template(template)
        
        # 创建链
        chain = prompt_template | self.llm | self.parser
        
        try:
            # 执行链
            result = chain.invoke({"prompt": prompt, "file_context": file_context})
            return result
        except Exception as e:
            logger.error(f"生成大纲时出错: {str(e)}")
            # 返回一个基本结构，避免完全失败
            return {
                "title": "生成失败，请重试",
                "sub_paragraphs": [
                    {
                        "title": "第一部分",
                        "description": "请重新尝试生成大纲",
                        "count_style": "medium"
                    }
                ]
            }
    
    def save_outline_to_db(self, outline_data: Dict[str, Any], db_session, outline_id: Optional[str] = None) -> Dict[str, Any]:
        """
        将生成的大纲保存到数据库
        
        Args:
            outline_data: 大纲数据
            db_session: 数据库会话
            outline_id: 大纲ID（如果是更新现有大纲）
            
        Returns:
            Dict: 保存后的大纲数据
        """
        from app.models.outline import Outline, SubParagraph, CountStyle
        from sqlalchemy.orm import Session
        import uuid
        
        try:
            # 创建或更新大纲
            if outline_id:
                # 更新现有大纲
                outline = db_session.query(Outline).filter(Outline.id == outline_id).first()
                if not outline:
                    raise ValueError(f"未找到ID为{outline_id}的大纲")
                
                # 更新标题
                outline.title = outline_data["title"]
                
                # 删除现有子段落
                db_session.query(SubParagraph).filter(SubParagraph.outline_id == outline_id).delete()
            else:
                # 创建新大纲
                outline = Outline(
                    title=outline_data["title"],
                    reference_status=0  # 初始状态：未引用
                )
                db_session.add(outline)
                db_session.flush()  # 获取ID
            
            # 添加子段落
            for sub_para_data in outline_data["sub_paragraphs"]:
                count_style_value = sub_para_data["count_style"].lower()
                # 确保count_style是有效的枚举值
                if count_style_value not in [e.value for e in CountStyle]:
                    count_style_value = "medium"  # 默认值
                
                sub_paragraph = SubParagraph(
                    outline_id=outline.id,
                    title=sub_para_data["title"],
                    description=sub_para_data.get("description", ""),
                    count_style=count_style_value,
                    reference_status=0  # 初始状态：未引用
                )
                db_session.add(sub_paragraph)
            
            # 提交事务
            db_session.commit()
            
            # 返回保存的数据
            return {
                "id": outline.id,
                "title": outline.title,
                "sub_paragraphs": [
                    {
                        "id": sub_para.id,
                        "title": sub_para.title,
                        "description": sub_para.description,
                        "count_style": sub_para.count_style.value
                    }
                    for sub_para in outline.sub_paragraphs
                ]
            }
        
        except Exception as e:
            db_session.rollback()
            logger.error(f"保存大纲到数据库时出错: {str(e)}")
            raise 