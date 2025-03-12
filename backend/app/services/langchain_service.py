from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Dict, Any, Optional, Tuple
from app.config import settings
import logging
import re
import markdown
import concurrent.futures
import json

from app.utils.outline import build_paragraph_key, build_paragraph_data
from app.models.outline import SubParagraph, Outline
from app.rag.rag_api import rag_api

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
    
    def __init__(self, readable_model_name: Optional[str] = None, use_rag: bool = True):
        """
        初始化大纲生成器
        
        Args:
            readable_model_name: 模型名称
            use_rag: 是否使用RAG API，默认为True
        """
        logger.info(f"初始化OutlineGenerator [model={readable_model_name or 'default'}, use_rag={use_rag}]")
        
        # 初始化LLM
        if readable_model_name:
            model_config = next(
                (model for model in settings.LLM_MODELS if model.get("readable_model_name") == readable_model_name),
                settings.LLM_MODELS[0]  # 如果没有找到匹配的，则使用第一个模型
            )
            self.model = model_config["model"]   
            self.api_key = model_config["api_key"]
            self.base_url = model_config["base_url"]
        else:
            self.model = settings.LLM_MODELS[0]["model"]
            self.api_key = settings.LLM_MODELS[0]["api_key"]
            self.base_url = settings.LLM_MODELS[0]["base_url"]
        
        self.llm = ChatOpenAI(
            model=self.model,
            openai_api_key=self.api_key,
            openai_api_base=self.base_url,
            temperature=0.7,
        )
        
        # 初始化输出解析器
        self.parser = JsonOutputParser()
        
        # 是否使用RAG API
        self.use_rag = use_rag
        
        # 初始化RAG API（如果启用）
        if self.use_rag:
            self.rag_api = rag_api
        else:
            self.rag_api = None
            logger.info("RAG API 已禁用")
        
    def _call_rag_api(
        self,
        question: str,
        kb_ids: List[str],
        user_id: str,
        streaming: bool = True,
        only_need_search_results: bool = False,
        context_msg: str = ""
    ) -> Optional[str]:
        """
        调用RAG API的通用方法
        
        Args:
            question: 问题内容
            kb_ids: 知识库ID列表
            user_id: 用户ID
            streaming: 是否使用流式返回
            only_need_search_results: 是否只需要搜索结果
            context_msg: 上下文信息，用于日志记录
            
        Returns:
            Optional[str]: RAG响应文本，如果失败则返回None
        """
        try:
            
            logger.info(f"开始获取RAG搜索结果 [user_id={user_id}, kb_ids={kb_ids}] {context_msg}")
            rag_result = self.rag_api.chat(
                kb_ids=kb_ids,
                question=question,
                streaming=streaming,
                only_need_search_results=only_need_search_results,
                temperature=settings.RAG_CHAT_TEMPERATURE,
                top_p=settings.RAG_CHAT_TOP_P,
                top_k=settings.RAG_CHAT_TOP_K,
                max_token=settings.RAG_CHAT_MAX_TOKENS,
                api_base=self.base_url,
                api_key=self.api_key,
                model=self.model
            )

            # 记录完整的RAG响应
            logger.info(f"RAG API响应类型: {type(rag_result)}")
            
            # 处理流式响应
            rag_response = None
            if isinstance(rag_result, dict):
                # 非流式响应处理
                logger.info(f"处理非流式响应: {rag_result}")
                if "response" in rag_result:
                    rag_response = rag_result["response"]
                    logger.info(f"提取到非流式RAG响应文本: {rag_response}")
            elif isinstance(rag_result, list) or hasattr(rag_result, '__iter__'):
                # 流式响应处理
                logger.info("检测到流式响应，开始处理")
                last_response = None
                chunk_count = 0
                
                try:
                    for chunk in rag_result:
                        chunk_count += 1
                        
                        if not chunk:
                            continue
                        
                        # 获取当前chunk的响应
                        current_response = chunk.get("response", "")
                        if current_response:
                            last_response = current_response
                    
                    # 使用最后一个chunk的响应
                    if last_response:
                        logger.info(f"流式响应处理完成，共处理 {chunk_count} 个数据块，最后一个响应: {last_response}")
                        rag_response = last_response
                    else:
                        logger.warning("未找到有效的响应内容")
                        
                except Exception as e:
                    logger.error(f"处理流式响应时出错: {str(e)}")
                    return None
            else:
                logger.error(f"未知的响应类型: {type(rag_result)}")
            
            # 验证响应内容
            if not rag_response:
                logger.warning("检测到无效的响应内容")
                return None
            
            logger.info(f"最终返回的响应内容: {rag_response}")
            return rag_response
            
        except Exception as e:
            logger.error(f"获取RAG搜索结果失败: {str(e)}")
            return None

    def _get_rag_context(self, question: str, user_id: Optional[str], kb_ids: Optional[List[str]], context_msg: str = "") -> str:
        """
        获取RAG上下文的通用方法
        
        Args:
            question: 问题内容
            user_id: 用户ID
            kb_ids: 知识库ID列表
            context_msg: 上下文信息，用于日志记录
            
        Returns:
            str: RAG上下文文本
        """
        # 如果未启用RAG，直接返回空字符串
        if not self.use_rag:
            logger.info("RAG API已禁用，跳过RAG搜索")
            return ""
            
        rag_context = ""
        if user_id and kb_ids:
            rag_response = self._call_rag_api(
                question=question,
                kb_ids=kb_ids,
                user_id=user_id,
                context_msg=context_msg
            )
            
            if rag_response:
                rag_context = f"大模型回答:\n{rag_response}\n\n"
                logger.info("已将RAG响应文本添加到上下文中")
            else:
                logger.warning("RAG响应内容无效或为空")
                rag_context = "知识库搜索未返回有效内容。"
        else:
            logger.info("未提供用户ID或知识库ID，跳过RAG搜索")
        
        return rag_context

    def generate_outline(self, prompt: str, file_contents: List[str] = None, user_id: str = None, kb_ids: List[str] = None) -> Dict[str, Any]:
        """
        生成结构化大纲
        
        Args:
            prompt: 用户提供的写作提示
            file_contents: 用户上传的文件内容列表
            user_id: 用户ID，用于RAG搜索（如果启用）
            kb_ids: 知识库ID列表，用于RAG搜索（如果启用）
            
        Returns:
            Dict: 包含大纲结构的字典
        """
        logger.info(f"开始生成大纲 [prompt_length={len(prompt)}, use_rag={self.use_rag}]")
        
        # 处理文件内容
        file_context = ""
        if file_contents and len(file_contents) > 0:
            file_context = "参考以下文件内容:\n" + "\n".join(file_contents)
            logger.info(f"使用参考文件内容 [files_count={len(file_contents)}]")
        else:
            file_context = "没有提供参考文件内容。"
            logger.info("无参考文件内容")
        
        # 获取RAG搜索结果（如果启用）
        rag_context = ""
        if self.use_rag:
            rag_prompt = f"关于主题：{prompt}，请提供参考内容"
            rag_context = self._get_rag_context(
                question=rag_prompt,
                user_id=user_id,
                kb_ids=kb_ids,
                context_msg="生成大纲"
            )
        
        try:
            # 构建提示模板
            template = """
            你是一个专业的写作助手，请根据用户的写作需求生成一个结构化的文章大纲。
            
            用户的写作需求是: {prompt}
            
            {file_context}
            
            {rag_context}
            
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
                            }}
                        ]
                    }}
                ]
            }}
            
            确保返回的是有效的JSON格式，不要包含任何注释或额外的文本。
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
            try:
                result = chain.invoke({"prompt": prompt, "file_context": file_context, "rag_context": rag_context})
                logger.info("大模型调用完成")
                return result
            except Exception as parser_error:
                logger.error(f"解析大模型输出时出错: {str(parser_error)}")
                
                # 尝试直接获取大模型的原始输出
                raw_chain = prompt_template | self.llm
                raw_output = raw_chain.invoke({"prompt": prompt, "file_context": file_context, "rag_context": rag_context})
                
                if hasattr(raw_output, 'content'):
                    raw_content = raw_output.content
                    logger.info("获取到大模型原始输出，尝试手动解析")
                    
                    # 尝试清理和修复JSON
                    try:
                        # 移除可能的注释
                        cleaned_content = re.sub(r'//.*?(\n|$)', '', raw_content)
                        # 尝试解析JSON
                        parsed_json = json.loads(cleaned_content)
                        logger.info("手动解析JSON成功")
                        return parsed_json
                    except Exception as json_error:
                        logger.error(f"手动解析JSON失败: {str(json_error)}")
                
                # 如果所有尝试都失败，返回基本结构
                raise ValueError(f"无法解析大模型输出: {str(parser_error)}")
            
        except Exception as e:
            logger.error(f"生成大纲时出错: {str(e)}")
            # 返回一个基本结构，避免完全失败
            return {
                "title": "生成失败，请重试",
                "sub_paragraphs": [
                    {
                        "title": "第一部分",
                        "description": "请重新尝试生成大纲",
                        "count_style": "medium",
                        "level": 1,
                        "children": []
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

    def generate_full_content(self, outline_id: str, db_session, user_id: Optional[str] = None, kb_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        根据大纲生成完整内容
        
        Args:
            outline_id: 大纲ID
            db_session: 数据库会话
            user_id: 用户ID，用于RAG搜索（如果启用）
            kb_ids: 知识库ID列表，用于RAG搜索（如果启用）
            
        Returns:
            Dict: 包含生成内容的字典
        """
        logger.info(f"开始生成全文内容 [outline_id={outline_id}, use_rag={self.use_rag}]")
        
        try:
            # 获取大纲信息
            outline = db_session.query(Outline).filter(Outline.id == outline_id).first()
            if not outline:
                raise ValueError(f"未找到大纲: {outline_id}")
            
            # 获取所有段落
            paragraphs = db_session.query(SubParagraph).filter(
                SubParagraph.outline_id == outline_id
            ).all()
            
            if not paragraphs:
                raise ValueError(f"大纲没有段落: {outline_id}")
            
            # 构建段落树
            paragraph_map = {p.id: p for p in paragraphs}
            root_paragraphs = [p for p in paragraphs if p.parent_id is None]
            
            for p in paragraphs:
                if p.parent_id:
                    parent = paragraph_map.get(p.parent_id)
                    if parent:
                        if not hasattr(parent, 'children'):
                            parent.children = []
                        parent.children.append(p)
            
            # 一次性获取RAG搜索结果（如果启用）
            rag_context = ""
            if self.use_rag:
                # 构建完整的搜索查询
                search_query = f"关于主题：{outline.title}，需要生成一篇完整的文章。文章大纲如下：\n"
                for p in paragraphs:
                    search_query += f"- {p.title}"
                    if p.description:
                        search_query += f"：{p.description}"
                    search_query += "\n"
                
                logger.info(f"执行一次性RAG查询 [outline_id={outline_id}]")
                rag_context = self._get_rag_context(
                    question=search_query,
                    user_id=user_id,
                    kb_ids=kb_ids,
                    context_msg="生成全文内容"
                )
            
            # 生成内容
            full_content = {
                "title": outline.title,
                "outline_id": outline_id,
                "content": "",
                "markdown": "",
                "html": "",
                "outline_structure": []
            }
            
            # 构建大纲结构
            outline_structure = []
            markdown_content = f"# {outline.title}\n\n"
            
            # 递归生成内容
            def generate_content_for_paragraph(paragraph, level=1, parent_structure=None):
                nonlocal markdown_content
                
                # 获取子标题
                sub_titles = get_sub_paragraph_titles(paragraph)
                
                # 创建结构节点
                structure_node = {
                    "id": paragraph.id,
                    "title": paragraph.title,
                    "level": level,
                    "children": []
                }
                
                if parent_structure is None:
                    outline_structure.append(structure_node)
                else:
                    parent_structure["children"].append(structure_node)
                
                # 只为1级段落生成内容
                if level == 1:
                    # 为1级段落生成内容
                    count_style = paragraph.count_style or "medium"
                    
                    # 使用全局RAG上下文生成内容
                    content = self._generate_paragraph_content(
                        outline.title, 
                        paragraph, 
                        sub_titles, 
                        count_style,
                        rag_context
                    )
                    
                    # 添加到Markdown
                    markdown_content += f"## {paragraph.title}\n\n{content}\n\n"
                
                # 递归处理子段落
                if hasattr(paragraph, 'children') and paragraph.children:
                    for child in paragraph.children:
                        generate_content_for_paragraph(child, level + 1, structure_node)
            
            # 开始递归生成
            for root_paragraph in root_paragraphs:
                generate_content_for_paragraph(root_paragraph)
            
            # 设置内容
            full_content["content"] = markdown_content
            full_content["markdown"] = markdown_content
            full_content["html"] = markdown.markdown(markdown_content, extensions=['extra'])
            logger.info("Markdown转HTML完成")
            
            # 添加大纲结构
            full_content["outline_structure"] = outline_structure
            
            logger.info("全文生成完成")
            return full_content
            
        except Exception as e:
            logger.error(f"生成全文内容时出错: {str(e)}")
            raise

    def _generate_paragraph_content(self, article_title: str, paragraph: SubParagraph, sub_titles: List[str], count_style: str, rag_context: str = "") -> str:
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
        
        {rag_context}
        
        请遵循以下要求生成内容：
        1. 格式要求：
           - 每个段落必须有清晰的主题句
           - 每个观点必须有具体的论据和例子支持
           - 段落之间使用恰当的过渡词衔接
           - 使用统一的写作语气和风格
           
           段落层级编号规范：
           - 二级标题使用：（一）（二）（三）（四）...
           - 三级标题使用：1、2、3、4...
           - 四级标题使用：(1)(2)(3)(4)...
           - 五级标题使用：①②③④...
           严格遵循以上编号规范，确保全文格式统一。
           
           注意：不要在内容开头重复章节标题，因为标题会在其他地方自动添加。直接从正文内容开始。
        
        2. 内容要求：
           - 字数控制在{word_count_range}字之间
           - 确保内容与整体文章主题"{article_title}"保持一致
           - 与文章其他部分建立明确的逻辑关联
           - 合理引用和整合知识库提供的相关内容
           - 每个子主题都要得到充分展开
           - 所有子主题必须按照上述编号规范进行编号
        
        3. 连贯性要求：
           - 在开头部分，简要回顾上文的关键内容（如果不是第一个段落）
           - 在结尾部分，预示下文将要讨论的内容（如果不是最后一个段落）
           - 使用适当的过渡语句，确保段落间的自然衔接
        
        请生成符合以上要求的段落内容。内容应该专业、严谨，同时保持生动有趣。确保严格遵循段落编号规范，不得混用不同的编号方式。记住：不要在内容中包含章节标题，直接从正文内容开始。
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

    def generate_content_directly(self, prompt: str, file_contents: List[str] = None, user_id: Optional[str] = None, kb_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        直接生成内容（不基于大纲）
        
        Args:
            prompt: 用户提供的写作提示
            file_contents: 用户上传的文件内容列表
            user_id: 用户ID，用于RAG搜索（如果启用）
            kb_ids: 知识库ID列表，用于RAG搜索（如果启用）
            
        Returns:
            Dict: 包含生成内容的字典
        """
        logger.info(f"开始直接生成内容 [prompt_length={len(prompt)}, use_rag={self.use_rag}]")
        
        # 处理文件内容
        file_context = ""
        if file_contents and len(file_contents) > 0:
            file_context = "参考以下文件内容:\n" + "\n".join(file_contents)
            logger.info(f"使用参考文件内容 [files_count={len(file_contents)}]")
        else:
            file_context = "没有提供参考文件内容。"
            logger.info("无参考文件内容")
        
        # 获取RAG搜索结果（如果启用）
        rag_context = ""
        if self.use_rag:
            rag_context = self._get_rag_context(
                question=prompt,
                user_id=user_id,
                kb_ids=kb_ids,
                context_msg="直接生成内容"
            )
        
        try:
            # 构建提示模板
            template = """
            你是一个专业的写作助手，请根据用户的写作需求生成一篇完整的文章。
            
            用户的写作需求是: {prompt}
            
            {file_context}
            
            {rag_context}
            
            请生成一篇结构良好、内容丰富的文章，包括标题和正文。文章应该有清晰的段落划分，每个段落都有明确的主题。
            """
            
            # 创建提示
            prompt_template = ChatPromptTemplate.from_template(template)
            logger.info("创建提示模板完成")
            
            # 创建链
            chain = prompt_template | self.llm
            logger.info("创建处理链完成")
            
            # 执行链
            logger.info("开始执行大模型调用")
            content = chain.invoke({"prompt": prompt, "file_context": file_context, "rag_context": rag_context})
            logger.info("大模型调用完成")
            
            # 提取标题
            lines = content.content.strip().split('\n')
            title = lines[0].strip().replace('#', '').strip()
            if not title or len(title) > 100:
                title = "生成的文章"
            
            # 构建返回结果
            result = {
                "title": title,
                "content": content.content,
                "markdown": content.content,
                "html": markdown.markdown(content.content, extensions=['extra']),
                "outline_structure": []
            }
            
            logger.info("直接生成内容完成")
            return result
            
        except Exception as e:
            logger.error(f"直接生成内容时出错: {str(e)}")
            raise 