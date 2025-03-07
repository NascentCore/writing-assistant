from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain.chains import LLMChain
from typing import List, Dict, Any, Optional
from app.config import settings
import json
import logging
import re
import markdown

from app.utils.outline import build_paragraph_key

logger = logging.getLogger(__name__)

class OutlineGenerator:
    """使用LangChain调用大模型生成结构化大纲"""
    
    def __init__(self,readable_model_name: Optional[str] = None):
        # 初始化LLM
        if readable_model_name:
            model_config = next(
                (model for model in settings.LLM_MODELS if model.get("readable_model_name") == readable_model_name),
                settings.LLM_MODELS[0]  # 如果没有找到匹配的，则使用第一个模型
            )
            model = model_config["model"]   
            api_key = model_config["api_key"]
            base_url = model_config["base_url"]
        else:
            model = settings.LLM_MODELS[0]["model"]
            api_key = settings.LLM_MODELS[0]["api_key"]
            base_url = settings.LLM_MODELS[0]["base_url"]
        
        self.llm = ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
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
        2. 多个段落，每个段落可以有不同的级别:
           - 1级段落: 主要段落，包含标题、描述和篇幅风格(short/medium/long)
           - 2级及以上段落: 子段落，包含标题和描述，但没有篇幅风格
        
        以JSON格式返回，格式如下:
        {{
            "title": "文章标题",
            "sub_paragraphs": [
                {{
                    "title": "1级段落标题",
                    "description": "1级段落描述",
                    "count_style": "short/medium/long",
                    "level": 1,
                    "children": [
                        {{
                            "title": "2级段落标题",
                            "description": "2级段落描述",
                            "level": 2,
                            "children": []
                        }},
                        // 更多子段落...
                    ]
                }},
                // 更多1级段落...
            ]
        }}
        
        确保返回的是有效的JSON格式。
        注意:
        1. 只有1级段落才有 count_style 属性
        2. 所有段落都必须有 level 属性
        3. 所有段落都必须有 children 数组，即使为空
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
    
    def save_outline_to_db(self, outline_data: Dict[str, Any], db_session, outline_id: Optional[str] = None, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        将生成的大纲保存到数据库
        
        Args:
            outline_data: 大纲数据
            db_session: 数据库会话
            outline_id: 大纲ID（如果是更新现有大纲）
            user_id: 用户ID（如果为空则表示系统预留大纲）
            
        Returns:
            Dict: 保存后的大纲数据
        """
        from app.models.outline import Outline, SubParagraph, CountStyle, ReferenceStatus
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
                    user_id=user_id,  # 设置用户ID
                    reference_status=ReferenceStatus.NOT_REFERENCED  # 使用枚举对象而不是枚举值
                )
                db_session.add(outline)
                db_session.flush()  # 获取ID
            
            # 递归添加段落及其子段落
            def add_paragraphs(paragraphs_data, parent_id=None, level=1):
                result_paragraphs = []
                
                for para_data in paragraphs_data:
                    # 处理 count_style，只有1级段落才有
                    count_style_value = None
                    if level == 1 and "count_style" in para_data:
                        count_style_value = para_data["count_style"].lower()
                        # 确保count_style是有效的枚举值
                        if count_style_value not in [e.value for e in CountStyle]:
                            count_style_value = "medium"  # 默认值
                    
                    # 创建段落
                    paragraph = SubParagraph(
                        outline_id=outline.id,
                        parent_id=parent_id,
                        level=para_data.get("level", level),  # 优先使用数据中的level，否则使用当前计算的level
                        title=para_data["title"],
                        description=para_data.get("description", ""),
                        count_style=count_style_value,
                        reference_status=ReferenceStatus.NOT_REFERENCED  # 使用枚举对象而不是枚举值
                    )
                    db_session.add(paragraph)
                    db_session.flush()  # 获取ID
                    result_paragraphs.append(paragraph)
                    
                    # 递归处理子段落
                    children = para_data.get("children", [])
                    if children:
                        add_paragraphs(children, paragraph.id, level + 1)
                
                return result_paragraphs
            
            # 添加所有段落
            top_level_paragraphs = add_paragraphs(outline_data["sub_paragraphs"])
            
            # 提交事务
            db_session.commit()
            
            # 一次性获取所有段落
            all_paragraphs = db_session.query(SubParagraph).filter(
                SubParagraph.outline_id == outline.id
            ).all()
            
            # 构建段落字典和父子关系字典
            paragraphs_dict = {p.id: p for p in all_paragraphs}
            siblings_dict = {}  # parent_id -> [ordered_child_ids]
            for p in all_paragraphs:
                if p.parent_id not in siblings_dict:
                    siblings_dict[p.parent_id] = []
                siblings_dict[p.parent_id].append(p.id)
            
            # 确保每个列表都是按ID排序的
            for parent_id in siblings_dict:
                siblings_dict[parent_id].sort()
            
            # 递归构建返回数据
            def build_paragraph_data(paragraph):
                data = {
                    "id": str(paragraph.id),
                    "key": build_paragraph_key(paragraph, siblings_dict, paragraphs_dict),
                    "title": paragraph.title,
                    "description": paragraph.description,
                    "level": paragraph.level
                }
                
                # 只有1级段落才有count_style
                if paragraph.level == 1 and paragraph.count_style:
                    data["count_style"] = paragraph.count_style.value
                
                # 获取子段落
                children = db_session.query(SubParagraph).filter(
                    SubParagraph.parent_id == paragraph.id
                ).all()
                
                if children:
                    data["children"] = [build_paragraph_data(child) for child in children]
                else:
                    data["children"] = []
                
                return data
            
            # 返回保存的数据
            return {
                "id": outline.id,
                "title": outline.title,
                "sub_paragraphs": [
                    build_paragraph_data(para) for para in db_session.query(SubParagraph).filter(
                        SubParagraph.outline_id == outline.id,
                        SubParagraph.parent_id == None
                    ).all()
                ]
            }
        
        except Exception as e:
            db_session.rollback()
            logger.error(f"保存大纲到数据库时出错: {str(e)}")
            raise

    def generate_full_content(self, outline_id: str, db_session) -> Dict[str, Any]:
        """
        根据大纲生成全文内容
        
        Args:
            outline_id: 大纲ID
            db_session: 数据库会话
            
        Returns:
            Dict: 生成的全文内容，包含markdown和html格式
        """
        from app.models.outline import Outline, SubParagraph, CountStyle
        
        try:
            # 查找大纲
            outline = db_session.query(Outline).filter(Outline.id == outline_id).first()
            if not outline:
                raise ValueError(f"未找到ID为{outline_id}的大纲")
            
            # 获取所有1级段落（只有1级段落需要生成内容）
            level_one_paragraphs = db_session.query(SubParagraph).filter(
                SubParagraph.outline_id == outline_id,
                SubParagraph.level == 1
            ).all()
            
            # 准备全文内容
            full_content = {
                "title": outline.title,
                "content": [],
                "markdown": ""
            }
            
            # 使用outline.markdown_content获取大纲的基本结构
            # 这包含了所有段落的标题和描述
            outline_structure = outline.markdown_content
            
            # 递归获取段落的所有子段落标题
            def get_sub_paragraph_titles(paragraph):
                titles = []
                children = db_session.query(SubParagraph).filter(
                    SubParagraph.parent_id == paragraph.id
                ).all()
                
                for child in children:
                    titles.append(f"- {child.title}")
                    sub_titles = get_sub_paragraph_titles(child)
                    if sub_titles:
                        # 添加缩进
                        titles.extend([f"  {t}" for t in sub_titles])
                
                return titles
            
            # 为每个1级段落生成内容
            markdown_content = f"# {outline.title}\n\n"
            
            for para in level_one_paragraphs:
                # 只有1级段落才有count_style
                if not para.count_style:
                    continue
                    
                # 获取子段落标题列表，用于提示
                sub_titles = get_sub_paragraph_titles(para)
                sub_titles_text = "\n".join(sub_titles) if sub_titles else "无子段落"
                
                # 根据count_style确定内容长度
                word_count_range = {
                    "short": "300-500",
                    "medium": "800-1200",
                    "long": "1500-2500"
                }.get(para.count_style.value, "800-1200")
                
                # 构建提示模板
                template = f"""
                你是一个专业的写作助手，请根据以下大纲生成高质量的内容。
                
                文章标题: {outline.title}
                当前章节: {para.title}
                章节描述: {para.description}
                子段落结构:
                {sub_titles_text}
                
                请生成一个字数在{word_count_range}字之间的内容，内容应该符合章节描述，并且与整体文章主题保持一致。
                内容应该有逻辑性、连贯性，并且包含足够的细节和例子。
                请确保内容涵盖所有列出的子段落主题。
                
                请直接返回生成的内容，不需要添加标题。
                """
                
                # 创建提示
                prompt_template = ChatPromptTemplate.from_template(template)
                
                # 创建链
                chain = prompt_template | self.llm
                
                # 执行链
                result = chain.invoke({})
                
                # 提取内容
                content = result.content if hasattr(result, 'content') else str(result)
                
                # 添加到全文内容
                full_content["content"].append({
                    "id": para.id,
                    "title": para.title,
                    "content": content,
                    "count_style": para.count_style.value,
                    "level": para.level
                })
                
                # 添加到markdown
                markdown_content += f"## {para.title}\n\n{content}\n\n"
                
                # 递归生成子段落的标题结构
                def add_child_headings(parent_id, current_level=3):
                    # 声明使用外部的markdown_content变量
                    nonlocal markdown_content
                    
                    children = db_session.query(SubParagraph).filter(
                        SubParagraph.parent_id == parent_id
                    ).all()
                    
                    for child in children:
                        heading = "#" * current_level
                        markdown_content += f"{heading} {child.title}\n\n"
                        add_child_headings(child.id, current_level + 1)
                
                # 添加子段落标题
                add_child_headings(para.id)
            
            # 设置markdown内容
            full_content["markdown"] = markdown_content
            
            # 转换为HTML
            full_content["html"] = markdown.markdown(markdown_content, extensions=['extra'])
            
            # 添加大纲结构
            full_content["outline_structure"] = outline_structure
            
            return full_content
            
        except Exception as e:
            logger.error(f"生成全文内容时出错: {str(e)}")
            raise 

    def generate_content_directly(self, prompt: str, file_contents: List[str] = None) -> Dict[str, Any]:
        """
        直接生成文章内容，不需要先生成大纲
        
        Args:
            prompt: 写作提示
            file_contents: 参考文件内容列表
            
        Returns:
            Dict: 生成的文章内容，包含标题、内容、markdown格式和html格式
        """
        try:
            # 构建提示模板
            template = """
            你是一个专业的写作助手，请根据用户的写作需求直接生成一篇完整的文章。

            写作需求: {prompt}

            {file_context}

            请生成一篇结构完整、内容丰富的文章，要求：
            1. 生成合适的文章标题
            2. 自动规划合理的章节结构
            3. 每个章节生成800-1200字的内容
            4. 内容要有逻辑性、连贯性，并包含充分的论据和例子
            5. 使用markdown格式，一级标题使用 # ，二级标题使用 ##

            直接返回文章内容，使用markdown格式。
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
            chain = prompt_template | self.llm

            # 执行链
            result = chain.invoke({
                "prompt": prompt,
                "file_context": file_context
            })

            # 提取内容
            markdown_content = result.content if hasattr(result, 'content') else str(result)

            # 解析markdown内容，提取标题和章节
            # 提取文章标题（第一个一级标题）
            title_match = re.search(r'^#\s+(.+)$', markdown_content, re.MULTILINE)
            title = title_match.group(1) if title_match else "生成的文章"

            # 提取所有章节（二级标题及其内容）
            sections = []
            section_pattern = r'^##\s+(.+)\n(.*?)(?=##|\Z)'
            for match in re.finditer(section_pattern, markdown_content, re.MULTILINE | re.DOTALL):
                section_title = match.group(1).strip()
                section_content = match.group(2).strip()
                sections.append({
                    "id": len(sections) + 1,  # 简单的自增ID
                    "title": section_title,
                    "content": section_content,
                    "count_style": "medium",  # 默认使用medium长度
                    "level": 1  # 所有章节都作为一级段落
                })

            # 构建返回数据
            result = {
                "title": title,
                "content": sections,
                "markdown": markdown_content,
                "html": markdown.markdown(markdown_content, extensions=['extra'])
            }
            return result

        except Exception as e:
            logger.error(f"直接生成文章内容时出错: {str(e)}")
            error_content = "# 生成失败，请重试\n\n## 生成失败\n\n生成文章内容时出错，请重试"
            # 返回一个基本结构，避免完全失败
            return {
                "title": "生成失败，请重试",
                "content": [{
                    "id": 1,
                    "title": "生成失败",
                    "content": "生成文章内容时出错，请重试",
                    "count_style": "medium",
                    "level": 1
                }],
                "markdown": error_content,
                "html": markdown.markdown(error_content, extensions=['extra'])
            } 