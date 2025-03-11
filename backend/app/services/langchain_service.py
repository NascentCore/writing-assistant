from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Dict, Any, Optional, Tuple
from app.config import settings
import logging
import re
import markdown
import concurrent.futures

from app.utils.outline import build_paragraph_key, build_paragraph_data
from app.models.outline import SubParagraph, Outline

logger = logging.getLogger(__name__)

def get_sub_paragraph_titles(paragraph: SubParagraph) -> List[str]:
    """
    获取段落的所有子标题
    
    Args:
        paragraph: 段落对象
        
    Returns:
        List[str]: 子标题列表
    """
    titles = []
    
    def collect_titles(para: SubParagraph):
        if para.children:
            for child in para.children:
                titles.append(child.title)
                collect_titles(child)
    
    collect_titles(paragraph)
    return titles

class OutlineGenerator:
    """使用LangChain调用大模型生成结构化大纲"""
    
    def __init__(self, readable_model_name: Optional[str] = None):
        """
        初始化大纲生成器
        
        Args:
            readable_model_name: 模型名称
        """
        logger.info(f"初始化OutlineGenerator [model={readable_model_name or 'default'}]")
        
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
        logger.info(f"开始生成大纲 [prompt_length={len(prompt)}]")
        
        # 处理文件内容
        file_context = ""
        if file_contents and len(file_contents) > 0:
            file_context = "参考以下文件内容:\n" + "\n".join(file_contents)
            logger.info(f"使用参考文件内容 [files_count={len(file_contents)}]")
        else:
            file_context = "没有提供参考文件内容。"
            logger.info("无参考文件内容")
        
        try:
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
            
            # 创建提示
            prompt_template = ChatPromptTemplate.from_template(template)
            logger.info("创建提示模板完成")
            
            # 创建链
            chain = prompt_template | self.llm | self.parser
            logger.info("创建处理链完成")
            
            # 执行链
            logger.info("开始执行大模型调用")
            result = chain.invoke({"prompt": prompt, "file_context": file_context})
            logger.info("大模型调用完成")
            
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
        from app.models.outline import CountStyle, ReferenceStatus
        from sqlalchemy.orm import Session
        import uuid
        
        logger.info(f"开始保存大纲到数据库 [outline_id={outline_id}, user_id={user_id}]")
        
        try:
            # 创建或更新大纲
            if outline_id:
                outline = db_session.query(Outline).filter(Outline.id == outline_id).first()
                if not outline:
                    logger.warning(f"未找到指定的大纲，将创建新大纲 [outline_id={outline_id}]")
                    outline = Outline(id=outline_id)
            else:
                outline = Outline()
                logger.info("创建新大纲")
            
            # 设置基本信息
            outline.title = outline_data.get("title", "未命名大纲")
            if user_id:
                outline.user_id = user_id
            
            db_session.add(outline)
            db_session.flush()  # 获取新ID
            logger.info(f"保存大纲基本信息完成 [outline_id={outline.id}]")
            
            # 递归保存段落
            def save_paragraphs(paragraphs_data, parent_id=None, level=1):
                saved_paragraphs = []
                for para_data in paragraphs_data:
                    # 创建段落
                    paragraph = SubParagraph(
                        outline_id=outline.id,
                        parent_id=parent_id,
                        title=para_data.get("title", ""),
                        description=para_data.get("description", ""),
                        level=level
                    )
                    
                    # 只有1级段落才设置count_style
                    if level == 1:
                        count_style = para_data.get("count_style", "medium").lower()
                        # 确保count_style是有效的枚举值
                        if count_style not in [e.value for e in CountStyle]:
                            count_style = "medium"
                        paragraph.count_style = count_style
                    
                    db_session.add(paragraph)
                    db_session.flush()  # 获取新ID
                    logger.info(f"保存段落 [id={paragraph.id}, level={level}, parent_id={parent_id}]")
                    
                    # 递归保存子段落
                    children = para_data.get("children", [])
                    if children:
                        logger.info(f"开始保存子段落 [parent_id={paragraph.id}, count={len(children)}]")
                        save_paragraphs(children, paragraph.id, level + 1)
                    
                    saved_paragraphs.append(paragraph)
                
                return saved_paragraphs
            
            # 删除现有段落（如果是更新模式）
            if outline_id:
                logger.info(f"删除现有段落 [outline_id={outline_id}]")
                db_session.query(SubParagraph).filter(
                    SubParagraph.outline_id == outline_id
                ).delete()
            
            # 开始保存段落
            logger.info("开始保存段落结构")
            save_paragraphs(outline_data.get("sub_paragraphs", []))
            
            # 提交事务
            db_session.commit()
            logger.info(f"大纲保存完成 [outline_id={outline.id}]")
            
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
        logger.info(f"开始根据大纲生成全文 [outline_id={outline_id}]")
        
        try:
            # 查找大纲
            outline = db_session.query(Outline).filter(Outline.id == outline_id).first()
            if not outline:
                error_msg = f"未找到ID为{outline_id}的大纲"
                logger.error(error_msg)
                raise ValueError(error_msg)
            
            logger.info(f"找到大纲 [title={outline.title}]")
            
            # 获取所有1级段落（只有1级段落需要生成内容）
            level_one_paragraphs = db_session.query(SubParagraph).filter(
                SubParagraph.outline_id == outline_id,
                SubParagraph.level == 1
            ).all()
            
            logger.info(f"获取到{len(level_one_paragraphs)}个一级段落")
            
            # 准备全文内容
            full_content = {
                "title": outline.title,
                "content": [],
                "markdown": ""
            }
            
            # 使用outline.markdown_content获取大纲的基本结构
            outline_structure = outline.markdown_content
            logger.info("获取大纲结构完成")
            
            # 创建线程池执行器
            with concurrent.futures.ThreadPoolExecutor() as executor:
                # 准备并发任务
                future_to_para = {}
                
                for para in level_one_paragraphs:
                    if not para.count_style:
                        logger.warning(f"段落缺少count_style设置 [id={para.id}]")
                        continue
                    
                    # 获取子段落标题列表
                    sub_titles = get_sub_paragraph_titles(para)
                    logger.info(f"获取到{len(sub_titles)}个子标题 [para_id={para.id}]")
                    
                    # 提交任务到线程池
                    future = executor.submit(
                        self._generate_paragraph_content,
                        outline.title,
                        para,
                        sub_titles,
                        para.count_style.value
                    )
                    future_to_para[future] = para
                
                # 收集结果
                para_contents = []
                for future in concurrent.futures.as_completed(future_to_para):
                    para = future_to_para[future]
                    try:
                        content = future.result()
                        para_contents.append({
                            "para": para,
                            "content": content
                        })
                        logger.info(f"段落内容生成完成 [id={para.id}]")
                    except Exception as e:
                        logger.error(f"生成段落内容时出错 [id={para.id}]: {str(e)}")
            
            # 按原始段落顺序排序结果
            para_contents.sort(key=lambda x: next(
                (i for i, p in enumerate(level_one_paragraphs) if p.id == x["para"].id), 
                float('inf')
            ))
            
            # 生成最终的markdown内容
            markdown_content = f"# {outline.title}\n\n"
            
            for item in para_contents:
                para = item["para"]
                content = item["content"]
                
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
            
            # 设置markdown内容
            full_content["markdown"] = markdown_content
            
            # 转换为HTML
            full_content["html"] = markdown.markdown(markdown_content, extensions=['extra'])
            logger.info("Markdown转HTML完成")
            
            # 添加大纲结构
            full_content["outline_structure"] = outline_structure
            
            logger.info("全文生成完成")
            return full_content
            
        except Exception as e:
            logger.error(f"生成全文内容时出错: {str(e)}")
            raise

    def _generate_paragraph_content(self, article_title: str, paragraph: SubParagraph, sub_titles: List[str], count_style: str) -> str:
        """生成段落内容"""
        # 根据count_style确定字数范围
        word_count_range = {
            "short": "800-1200",
            "medium": "1500-2000",
            "long": "2500-3000"
        }.get(count_style, "1500-2000")
        
        template = f"""
        你是一个专业的写作助手。现在正在写一篇题为"{article_title}"的文章。
        
        当前需要生成的是一个段落，主题是"{paragraph.title}"。
        段落描述：{paragraph.description or '无'}
        
        这个段落包含以下子主题：
        {chr(10).join([f'- {title}' for title in sub_titles])}
        
        请生成一个字数在{word_count_range}字之间的内容，内容应该符合章节描述，并且与整体文章主题保持一致。
        内容应该有逻辑性、连贯性，并且包含足够的细节和例子。
        请确保内容涵盖所有列出的子段落主题。
        
        请直接返回生成的内容，不需要添加标题。
        """
        
        try:
            # 创建提示
            prompt_template = ChatPromptTemplate.from_template(template)
            
            # 创建链
            chain = prompt_template | self.llm
            
            # 执行链
            result = chain.invoke({})
            
            return result.content
            
        except Exception as e:
            logger.error(f"生成段落内容时出错: {str(e)}")
            return f"生成内容失败: {str(e)}"

    def generate_content_directly(self, prompt: str, file_contents: List[str] = None) -> Dict[str, Any]:
        """
        直接生成文章内容，不需要先生成大纲
        
        Args:
            prompt: 写作提示
            file_contents: 参考文件内容列表
            
        Returns:
            Dict: 生成的文章内容，包含标题、内容、markdown格式和html格式
        """
        logger.info(f"开始直接生成文章 [prompt_length={len(prompt)}]")
        
        try:
            # 处理文件内容
            file_context = ""
            if file_contents and len(file_contents) > 0:
                file_context = "参考以下文件内容:\n" + "\n".join(file_contents)
                logger.info(f"使用参考文件内容 [files_count={len(file_contents)}]")
            else:
                file_context = "没有提供参考文件内容。"
                logger.info("无参考文件内容")
            
            try:
                # 创建提示
                template = """
                你是一个专业的写作助手。请根据以下提示生成一篇完整的文章：
                
                提示: {prompt}
                
                {file_context}
                
                请生成一篇结构清晰、内容丰富的文章。文章应该包含标题（使用# 标记）、
                适当的小标题（使用## 和 ### 标记）以及详细的内容。
                确保文章逻辑连贯，有足够的论据支持，并且语言流畅。
                """
                prompt_template = ChatPromptTemplate.from_template(template)
                logger.info("创建提示模板完成")
                
                # 创建链
                chain = prompt_template | self.llm
                logger.info("创建处理链完成")
                
                # 执行链
                logger.info("开始调用大模型生成内容")
                result = chain.invoke({
                    "prompt": prompt,
                    "file_context": file_context
                })
                logger.info("内容生成完成")
                
                # 提取内容
                markdown_content = result.content if hasattr(result, 'content') else str(result)
                
                # 解析markdown内容
                logger.info("开始解析生成的内容")
                
                # 提取文章标题
                title_match = re.search(r'^#\s+(.+)$', markdown_content, re.MULTILINE)
                title = title_match.group(1) if title_match else "生成的文章"
                logger.info(f"提取到文章标题: {title}")
                
                # 提取所有章节
                sections = []
                section_pattern = r'^##\s+(.+)\n(.*?)(?=##|\Z)'
                for match in re.finditer(section_pattern, markdown_content, re.MULTILINE | re.DOTALL):
                    section_title = match.group(1).strip()
                    section_content = match.group(2).strip()
                    sections.append({
                        "id": len(sections) + 1,
                        "title": section_title,
                        "content": section_content,
                        "count_style": "medium",
                        "level": 1
                    })
                logger.info(f"提取到{len(sections)}个章节")
                
                # 构建返回数据
                result = {
                    "title": title,
                    "content": sections,
                    "markdown": markdown_content,
                    "html": markdown.markdown(markdown_content, extensions=['extra'])
                }
                
                logger.info("文章生成和解析完成")
                return result
                
            except Exception as e:
                logger.error(f"生成文章内容时出错: {str(e)}")
                raise
                
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