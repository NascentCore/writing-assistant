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
import time

from app.utils.outline import build_paragraph_key, build_paragraph_data
from app.models.outline import SubParagraph, Outline
from app.rag.rag_api import rag_api

logger = logging.getLogger(__name__)

# 段落生成的提示词模板常量
PARAGRAPH_GENERATION_TEMPLATE = """
你是一位专业的写作助手，正在为一篇题为"{article_title}"的文章撰写每一章的内容。

【用户需求】
{user_prompt}

-------------------

【参考资料】
{rag_context}

-------------------

【文章整体大纲】
{outline_content}

-------------------

【当前段落信息】
- 段落主题：{paragraph_title}
- 段落描述：{paragraph_description}
- 大纲中定义的子主题：
{sub_topics}

-------------------


【内容要求】
- 字数范围：{word_count_range}字
- 内容必须与文章主题"{article_title}"保持一致性
- 充分展开每个子主题，确保逻辑清晰
- 与文章其他部分建立明确的逻辑关联
- 适当引用参考资料中的内容，但不要出现引用说明
- 层级结构以段落信息为准

【格式要求】
- 使用markdown格式
- 不要添加任何编号，最终会通过markdown自动处理编号格式
- 不要在内容开头重复章节标题，直接从正文内容开始
- 不要包含"参考文档"、"参考文献"等辅助说明文本
- 不要出现"根据xxx标准"、"参考了xxx文件"等说明性文字
- 严格禁止在标题或层级标题中使用任何形式的编号，包括但不限于：
  * 不要使用"第一章"、"第二章"等章节编号
  * 不要使用"（一）"、"（二）"等中文编号
  * 不要使用"1."、"2."等数字编号
  * 不要使用"一、"、"二、"等中文序号
  * 不要使用"1、"、"2、"等数字序号
  * 不要使用"①"、"②"等特殊符号编号
- 遵循以下层级规范来组织内容：
  * 文章主标题使用"#"（已添加）
  * 当前段落标题使用"##"（已添加）
  * 如果有子主题，可以使用"###"来标记
  * 更深层次的内容可以使用"####"及更多"#"
- 注意：大纲中的描述内容已用括号括起来，以区分标题和描述

【段落结构要求】
- 每个段落必须有清晰的主题句
- 每个观点必须有具体的论据和例子支持
- 使用恰当的过渡词衔接段落
- 保持统一的写作语气和风格
- 根据提供的子主题列表自然组织内容，如有必要可使用适当的标题层级

请生成一段专业、严谨且内容丰富的文本，根据提供的子主题自然组织内容。
"""

# 直接生成内容的提示词模板常量
DIRECT_CONTENT_GENERATION_TEMPLATE = """
你是一位专业的写作助手，请根据用户的写作需求生成一篇完整的文章。

【用户需求】
{prompt}

【参考文件】
{file_context}

【参考资料】
{rag_context}

【写作要求】

【内容要求】
- 内容必须与用户需求保持一致
- 确保文章结构完整，逻辑清晰
- 适当引用参考资料中的内容，但不要出现引用说明
- 每个段落都要有明确的主题和充分的论述

【格式要求】
- 使用markdown格式组织文章
- 文章主标题使用"#"
- 主要段落标题使用"##"
- 如果有子主题，可以使用"###"来标记
- 更深层次的内容可以使用"####"及更多"#"
- 根据内容自然组织层级结构
- 如果需要添加描述性内容，请使用括号将其括起来，以区分标题和描述，避免层级结构的歧义

【段落结构要求】
- 每个段落必须有清晰的主题句
- 每个观点必须有具体的论据和例子支持
- 使用恰当的过渡词衔接段落
- 保持统一的写作语气和风格
- 根据内容自然组织段落结构，确保层次分明

请生成一篇结构完整、内容丰富的文章，确保符合以上要求。
"""

# 最大并发生成段落数
MAX_CONCURRENT_GENERATIONS = 3

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

# 清理标题中的编号
def clean_numbering_from_title(title: str) -> str:
    """
    清理标题中的编号格式，如"第一章"、"（一）"、"1."等
    
    Args:
        title: 原始标题
        
    Returns:
        str: 清理后的标题
    """
    # 清理常见的编号格式
    patterns = [
        r'^第[零一二三四五六七八九十百千万亿]+章\s*',  # 第一章
        r'^[（(][零一二三四五六七八九十]+[）)]\s*',    # （一）或(一)
        r'^\d+[、.．]\s*',                           # 1、或1.
        r'^\([0-9]+\)\s*',                          # (1)
        r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*'                       # ①②③等
    ]
    
    result = title
    for pattern in patterns:
        result = re.sub(pattern, '', result)
    
    return result.strip()

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

    def _clean_rag_content(self, rag_content: str) -> str:
        """清理RAG返回的内容格式"""
        # 移除markdown标题标记
        cleaned = re.sub(r'^#+\s+', '', rag_content, flags=re.MULTILINE)
        
        # 移除元信息标记
        cleaned = re.sub(r'\[无参考文档 ID\]', '', cleaned)
        
        # 移除编号格式
        cleaned = re.sub(r'^[一二三四五六七八九十]+、', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^（[一二三四五六七八九十]+）', '', cleaned, flags=re.MULTILINE)
        cleaned = re.sub(r'^\d+[.、]', '', cleaned, flags=re.MULTILINE)
        
        return cleaned.strip()

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
                # 清理RAG返回的内容
                cleaned_response = self._clean_rag_content(rag_response)
                rag_context = f"\n{cleaned_response}\n\n"
                logger.info("已清理并添加RAG响应文本到上下文中")
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
            
            【用户需求】
            {prompt}
            
            【参考文件】
            {file_context}
            
            【参考资料】
            {rag_context}
            
            【大纲要求】
            请生成一个包含以下内容的结构化大纲:
            1. 文章标题
            2. 多个段落，每个段落可以有不同的级别:
               - 1级段落: 主要段落，包含标题、描述和篇幅风格(short/medium/long)
               - 2级及以上段落: 子段落，包含标题和描述，但没有篇幅风格
            3. 严格禁止在标题或层级标题中使用任何形式的编号，包括但不限于：
               - 不要使用"第一章"、"第二章"等章节编号
               - 不要使用"（一）"、"（二）"等中文编号
               - 不要使用"1."、"2."等数字编号
               - 不要使用"一、"、"二、"等中文序号
               - 不要使用"1、"、"2、"等数字序号
               - 不要使用"①"、"②"等特殊符号编号
            4. 标题，描述中不能包含参考资料的应用的文件名称
            
           【返回格式】
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
            
            【注意事项】
            确保返回的是有效的JSON格式，不要包含任何注释或额外的文本。
            1. 只有1级段落才有 count_style 属性
            2. 所有段落都必须有 level 属性
            3. 所有段落都必须有 children 数组，即使为空
            4. 在最终生成的文档中，描述内容将用括号括起来，以区分标题和描述，避免层级结构的歧义
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

    def _build_outline_content(self, outline: Outline, paragraphs: List[SubParagraph]) -> str:
        """
        构建完整的大纲内容，用于生成提示词
        
        Args:
            outline: 大纲对象
            paragraphs: 段落列表
            
        Returns:
            str: 格式化的大纲内容
        """
        logger.info(f"开始构建大纲内容 [outline_id={outline.id}]")
        
        try:
            # 构建段落树
            paragraph_map = {p.id: p for p in paragraphs}
            root_paragraphs = [p for p in paragraphs if p.parent_id is None]
            
            # 构建段落树结构
            for p in paragraphs:
                if p.parent_id:
                    parent = paragraph_map.get(p.parent_id)
                    if parent:
                        if not hasattr(parent, 'children'):
                            parent.children = []
                        # 检查是否已经添加过这个子段落
                        if p not in parent.children:
                            parent.children.append(p)
            
            # 开始构建大纲内容
            outline_content = f"# {outline.title}\n"
            
            def build_outline_text(paragraphs, level=0):
                """
                递归构建大纲文本
                
                Args:
                    paragraphs: 段落列表
                    level: 当前层级（0表示一级段落，1表示二级段落，以此类推）
                """
                result = []
                for p in paragraphs:
                    # 清理标题中的编号
                    clean_title = clean_numbering_from_title(p.title)
                    # 添加标题，一级段落使用二级标题(##)，子段落依次增加层级
                    prefix = "#" * (level + 2)  # 一级段落使用##，二级段落使用###，依此类推
                    result.append(f"{prefix} {clean_title}")
                    
                    # 添加描述（如果有）
                    if p.description:
                        # 将描述用括号括起来，避免层级结构歧义
                        result.append(f"({p.description})")
                    
                    # 递归处理子段落
                    if hasattr(p, 'children') and p.children:
                        # 确保子段落按顺序排序
                        sorted_children = sorted(p.children, key=lambda x: x.title)
                        result.extend(build_outline_text(sorted_children, level + 1))
                return result
            
            # 构建大纲文本
            outline_text = build_outline_text(root_paragraphs)
            outline_content += "\n".join(outline_text)
            
            logger.info(f"大纲内容构建完成 [outline_id={outline.id}, content_length={len(outline_content)}]")
            return outline_content
            
        except Exception as e:
            logger.error(f"构建大纲内容时出错: {str(e)}")
            # 返回一个基本的大纲结构，避免完全失败
            return f"# {outline.title}\n## 大纲生成失败，请重试\n(构建大纲内容时发生错误: {str(e)})"

    def _generate_article_title(self, user_prompt: str, outline_title: str, outline_content: str) -> str:
        """
        生成文章标题
        
        Args:
            user_prompt: 用户需求
            outline_title: 大纲标题
            outline_content: 大纲内容
            
        Returns:
            str: 生成的文章标题
        """
        logger.info("开始生成文章标题")
        
        title_prompt = f"""
        请根据以下信息生成一个合适的文章标题：

        【用户需求】
        {user_prompt}

        【大纲标题】
        {outline_title}

        【大纲结构】
        {outline_content}

        【要求】
        1. 标题要简洁、准确、吸引人
        2. 标题长度在10-30个字之间
        3. 标题要体现文章的核心主题
        4. 标题要符合学术写作风格
        5. 直接返回标题文本，不要包含任何其他内容
        """
        
        try:
            # 创建标题生成提示
            title_template = ChatPromptTemplate.from_template(title_prompt)
            title_chain = title_template | self.llm
            
            # 生成标题
            title_result = title_chain.invoke({})
            generated_title = title_result.content.strip()
            
            # 验证标题
            if not generated_title or len(generated_title) > 100:
                generated_title = outline_title
                logger.warning("生成的标题无效，使用大纲标题作为备选")
            
            logger.info(f"生成的文章标题: {generated_title}")
            return generated_title
            
        except Exception as e:
            logger.error(f"生成文章标题时出错: {str(e)}")
            return outline_title

    def generate_full_content(self, outline_id: str, db_session, user_id: Optional[str] = None, kb_ids: Optional[List[str]] = None, user_prompt: str = "") -> Dict[str, Any]:
        """
        根据大纲生成完整内容
        
        Args:
            outline_id: 大纲ID
            db_session: 数据库会话
            user_id: 用户ID，用于RAG搜索（如果启用）
            kb_ids: 知识库ID列表，用于RAG搜索（如果启用）
            user_prompt: 用户的第一条消息，作为额外的提示词
            
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
            
            # 构建完整大纲内容（用于提示词）
            outline_content = self._build_outline_content(outline, paragraphs)
            
            # 生成内容
            full_content = {
                "title": "",
                "outline_id": outline_id,
                "content": "",
                "markdown": "",
                "html": "",
                "outline_structure": []
            }
            
            # 生成文章标题
            full_content["title"] = self._generate_article_title(
                user_prompt=user_prompt,
                outline_title=outline.title,
                outline_content=outline_content
            )
            
            # 一次性获取RAG搜索结果（如果启用）
            rag_context = ""
            if self.use_rag:
                # 构建完整的搜索查询，使用生成的标题
                search_query = f"关于主题：{full_content['title']}，需要生成一篇完整的文章。请提供参考资料，参考资料的文件名称不能出现在标题或描述中。并按照安条目顺序输出"
                if user_prompt:
                    search_query += f"\n用户需求：{user_prompt}"
                search_query += "\n文章大纲如下：\n"
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
            
            # 构建大纲结构
            outline_structure = []
            
            # 获取根段落
            root_paragraphs = [p for p in paragraphs if p.parent_id is None]
            
            # 构建结构节点的函数
            def build_structure_node(paragraph, level=1, parent_structure=None):
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
                
                # 递归处理子段落
                if hasattr(paragraph, 'children') and paragraph.children:
                    for child in paragraph.children:
                        build_structure_node(child, level + 1, structure_node)
                        
                return structure_node
            
            # 构建结构树
            for root_paragraph in root_paragraphs:
                build_structure_node(root_paragraph)
            
            # 准备并发生成内容
            markdown_content = []  # 使用列表存储各部分内容
            
            # 收集需要生成内容的段落（只处理1级段落）
            paragraphs_to_generate = []
            for i, root_paragraph in enumerate(root_paragraphs):
                chapter_number = i + 1
                paragraphs_to_generate.append({
                    "paragraph": root_paragraph,
                    "chapter_number": chapter_number,
                    "index": i
                })
            
            # 并发生成段落内容
            def generate_paragraph_worker(item):
                paragraph = item["paragraph"]
                chapter_number = item["chapter_number"]
                index = item["index"]
                
                logger.info(f"开始处理段落 [ID={paragraph.id}, 标题='{paragraph.title}', 序号={chapter_number}, 索引={index}]")
                
                # 获取子标题
                sub_titles = get_sub_paragraph_titles(paragraph)
                logger.info(f"段落 [ID={paragraph.id}] 包含 {len(sub_titles)} 个子主题")
                
                # 为1级段落生成内容
                count_style = paragraph.count_style or "medium"
                
                # 使用全局RAG上下文生成内容
                logger.info(f"调用_generate_paragraph_content生成段落内容 [ID={paragraph.id}]")
                content = self._generate_paragraph_content(
                    article_title=full_content["title"], 
                    paragraph=paragraph, 
                    sub_titles=sub_titles, 
                    count_style=count_style,
                    rag_context=rag_context,
                    outline_content=outline_content,
                    user_prompt=user_prompt
                )
                
                # 清理标题中的编号
                clean_title = clean_numbering_from_title(paragraph.title)
                logger.info(f"清理后的标题: '{clean_title}' [原标题: '{paragraph.title}']")
                
                # 返回章节标题和内容
                # 使用二级标题(##)作为章节标题，因为一级标题(#)已用于文章标题
                # 不添加"第X章"等层级编号，保持纯标题
                chapter_title = f"\n## {clean_title}\n"
                
                content_length = len(content)
                logger.info(f"段落处理完成 [ID={paragraph.id}, 内容长度={content_length}字符]")
                
                return {
                    "index": item["index"],
                    "title": chapter_title,
                    "content": f"\n{content}\n"
                }
            
            # 使用线程池并发生成内容
            logger.info(f"开始并发生成段落内容，最大并发数: {MAX_CONCURRENT_GENERATIONS}, 总段落数: {len(paragraphs_to_generate)}")
            results = []
            start_time = time.time()
            
            with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT_GENERATIONS) as executor:
                # 创建future到段落的映射
                future_to_paragraph = {
                    executor.submit(generate_paragraph_worker, item): item 
                    for item in paragraphs_to_generate
                }
                logger.info(f"已提交 {len(future_to_paragraph)} 个段落生成任务到线程池")
                
                completed_count = 0
                for future in concurrent.futures.as_completed(future_to_paragraph):
                    item = future_to_paragraph[future]
                    completed_count += 1
                    
                    try:
                        # 记录任务完成进度
                        progress = (completed_count / len(paragraphs_to_generate)) * 100
                        elapsed_time = time.time() - start_time
                        logger.info(f"段落生成进度: {completed_count}/{len(paragraphs_to_generate)} ({progress:.1f}%), 已用时间: {elapsed_time:.1f}秒")
                        
                        result = future.result()
                        results.append(result)
                        logger.info(f"完成段落生成: {item['paragraph'].title} [ID={item['paragraph'].id}]")
                    except Exception as e:
                        logger.error(f"生成段落内容时出错 [ID={item['paragraph'].id}, 标题='{item['paragraph'].title}']: {str(e)}")
                        # 添加错误信息作为内容，使用二级标题(##)保持一致性
                        # 清理标题中的编号
                        clean_title = clean_numbering_from_title(item['paragraph'].title)
                        results.append({
                            "index": item["index"],
                            "title": f"\n## {clean_title}\n",
                            "content": f"\n生成内容失败: {str(e)}\n"
                        })
            
            total_time = time.time() - start_time
            logger.info(f"所有段落生成完成，总用时: {total_time:.1f}秒，平均每段用时: {total_time/len(paragraphs_to_generate):.1f}秒")
            
            # 按原始顺序排序结果
            results.sort(key=lambda x: x["index"])
            
            # 将结果添加到markdown内容中
            for result in results:
                markdown_content.append(result["content"])
            
            # 合并所有内容
            final_content = ''.join(markdown_content)
            
            # 设置内容
            full_content["content"] = final_content
            full_content["markdown"] = final_content
            full_content["html"] = markdown.markdown(final_content, extensions=['extra'])
            logger.info("Markdown转HTML完成")
            
            # 添加大纲结构
            full_content["outline_structure"] = outline_structure
            
            logger.info("全文生成完成")
            return full_content
            
        except Exception as e:
            logger.error(f"生成全文内容时出错: {str(e)}")
            raise

    def _generate_paragraph_content(self, article_title: str, paragraph: SubParagraph, sub_titles: List[str], count_style: str, rag_context: str = "", outline_content: str = "", user_prompt: str = "") -> str:
        """生成段落内容"""
        # 记录开始生成段落内容
        logger.info(f"开始生成段落内容 [段落ID={paragraph.id}, 标题='{paragraph.title}', 字数范围={count_style}]")
        
        # 根据count_style确定字数范围
        word_count_range = {
            "short": "800-1200",
            "medium": "1500-2000",
            "long": "2500-3000"
        }.get(count_style, "1500-2000")
        
        # 清理标题中的编号
        clean_title = clean_numbering_from_title(paragraph.title)
        
        # 格式化子主题列表
        sub_topics = "\n".join([f"  - {clean_numbering_from_title(title)}" for title in sub_titles])
        logger.info(f"段落包含 {len(sub_titles)} 个子主题")
        
        # 使用常量模板
        template = PARAGRAPH_GENERATION_TEMPLATE.format(
            article_title=article_title,
            outline_content=outline_content,
            paragraph_title=clean_title,
            paragraph_description=paragraph.description or "无",
            sub_topics=sub_topics,
            rag_context=rag_context,
            word_count_range=word_count_range,
            user_prompt=user_prompt
        )
        
        # 记录提示词长度和内容
        prompt_length = len(template)
        logger.info(f"生成的提示词长度: {prompt_length} 字符")
        logger.info(f"提示词内容 [段落ID={paragraph.id}]:\n{'-'*80}\n{template}\n{'-'*80}")
        
        try:
            # 创建提示
            prompt_template = ChatPromptTemplate.from_template(template)
            
            # 创建链
            chain = prompt_template | self.llm
            
            # 记录开始调用LLM
            logger.info(f"开始调用LLM生成段落内容 [段落ID={paragraph.id}]")
            
            # 执行链
            result = chain.invoke({})
            
            # 记录LLM响应
            response_length = len(result.content) if hasattr(result, 'content') else 0
            logger.info(f"LLM响应完成 [段落ID={paragraph.id}], 响应长度: {response_length} 字符")
            logger.info(f"LLM响应内容 [段落ID={paragraph.id}]:\n{'-'*80}\n{result.content}\n{'-'*80}")
            
            # 检查生成的内容中是否包含子标题
            content = result.content
            heading_count = content.count('###')
            if heading_count > 0:
                logger.info(f"生成内容包含 {heading_count} 个子标题(###) [段落ID={paragraph.id}]")
            else:
                logger.info(f"生成内容未包含子标题(###) [段落ID={paragraph.id}]")
            
            # 直接返回LLM的原始响应内容，不进行过滤
            return content
            
        except Exception as e:
            logger.error(f"生成段落内容时出错 [段落ID={paragraph.id}]: {str(e)}")
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
        
        try:
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
            
            # 生成内容
            full_content = {
                "title": "",
                "content": "",
                "markdown": "",
                "html": "",
                "outline_structure": []
            }
            
            # 创建提示
            prompt_template = ChatPromptTemplate.from_template(DIRECT_CONTENT_GENERATION_TEMPLATE)
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
            
            # 设置内容
            full_content["title"] = title
            full_content["content"] = content.content
            full_content["markdown"] = content.content
            full_content["html"] = markdown.markdown(content.content, extensions=['extra'])
            
            logger.info("直接生成内容完成")
            return full_content
            
        except Exception as e:
            logger.error(f"直接生成内容时出错: {str(e)}")
            raise
