from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from typing import List, Dict, Any, Optional, Tuple, Callable, Union
from app.config import settings
import logging
import re
import markdown
import concurrent.futures
import json
import time
import uuid
from datetime import datetime
import traceback
import random
import math
from concurrent.futures import ThreadPoolExecutor
import html

from fastapi import HTTPException
import numpy as np
from langchain.vectorstores.chroma import Chroma
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.schema.output_parser import OutputParserException
from langchain.schema.runnable import RunnableConfig
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain.schema import HumanMessage, SystemMessage

from app.utils.outline import build_paragraph_key, build_paragraph_data
from app.models.outline import SubParagraph, Outline
from app.rag.rag_api import rag_api
from app.models.document import Document
from app.models.task import Task, TaskStatus
from app.utils.web_search import baidu_search
from app.config import settings

logger = logging.getLogger(__name__)

def update_task_progress(task_id: Optional[str], db_session, progress: int, detail: str, log: str = ""):
    """更新任务进度"""
    if not task_id:
        return
        
    try:
        task = db_session.query(Task).filter(Task.id == task_id).first()
        if task:
            task.process = progress
            task.process_detail_info = detail
            
            # 构建日志内容
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [进度: {progress}%] {detail}"
            
            # 如果有额外的日志信息，添加到日志条目中
            if log:
                log_entry += f"\n详情: {log}"
                
            # 将日志追加到task.log中
            if task.log:
                task.log = task.log + "\n" + log_entry
            else:
                task.log = log_entry
                
            db_session.commit()
            logger.info(f"更新任务进度 [task_id={task_id}, progress={progress}%, detail={detail}]")
    except Exception as e:
        logger.error(f"更新任务进度失败: {str(e)}")

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
- 行文风格要求正式，不要出现『我们』、『总之』这样的口水化内容
- 按照需求文档的类型组织合理的大纲，比如方案就要有方案的格式，标书就要有标书的格式

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
- 行文风格要求正式，不要出现『我们』、『总之』这样的口水化内容

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

# 全文优化提示词模板常量
FULL_CONTENT_GENERATION_TEMPLATE = """
你是一个专业的文档编辑助手。你的任务是对多个独立生成的章节内容拼接成的文档进行整体优化，确保文档的连贯性、一致性和流畅性。

【用户需求】
{prompt}

【需要优化的全文内容】
{final_content}

请遵循以下步骤：
1. 仔细分析提供的所有章节内容和大纲结构
2. 检查并优化章节之间的过渡和衔接
4. 确保整体文档的风格和语调一致
5. 检查并修正可能的重复内容或逻辑矛盾
6. 行文风格正式，尽量不要出现我们、总之这样较口水化的词语

衔接优化要求：
- 检查并优化章节之间的过渡，确保内容流畅自然
- 添加必要的过渡句，使章节之间的连接更加平滑
- 确保前后章节的内容没有明显的风格差异或逻辑断层
- 修正可能的重复内容，确保信息不会冗余
- 确保文档的整体逻辑结构清晰，论述连贯

格式要求：
- 使用Markdown格式输出完整文档
- 为文档添加适当的标题和小标题
- 确保标题层级结构清晰，符合大纲结构
- 保持段落格式的一致性

请直接输出优化后的完整文档内容，使用Markdown格式。
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
    清理标题中的编号格式，包括中英文数字、特殊符号等
    
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
        r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*',                      # ①②③等
        r'^[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]\s*',                      # 罗马数字
        r'^[IVXivx]+[.、]\s*',                      # 罗马数字后跟标点
        r'^[A-Za-z][.、]\s*',                       # 字母编号
        r'^[【\[［][^】\]］]*[】\]］]\s*',           # 各种方括号
        r'^第\s*\d+\s*[章节]\s*',                   # 第1章、第1节
        r'^\d+\.\d+\.*\s*',                        # 1.1、1.1.1等
        r'^[零一二三四五六七八九十]+[、.．]\s*',        # 中文数字编号
        r'^\d+(\.\d+)*[.、．]\s*',                  # 匹配多级数字编号：1.1、1.1.1、2.3.4.5等
        r'^(\d+[.-])+\d+\s*',                      # 匹配带连字符的多级编号：1-1、1-1-1等
        r'^[一二三四五六七八九十](\.\d+)+[.、．]\s*',   # 中文数字开头的多级编号：一.1、一.1.1等
        r'^第[零一二三四五六七八九十]+[条款项目]\s*',    # 第一条、第二款等
        r'^\d+[.、．][一二三四五六七八九十]+\s*',      # 数字加中文编号：1.一、2.二等
        r'^[（(]\d+[）)][（(][一二三四五六七八九十]+[）)]\s*',  # (1)(一)等嵌套编号
        r'^\d+\s*[）)]\s*',                        # 1)、2)等
        r'^[a-zA-Z](\.\d+)+[.、．]\s*',             # 字母开头的多级编号：A.1、B.1.1等
        r'^\d+(?:\.\d+)*[\s.、．]+',                 # 匹配如 9.1、9.1.2、9.1.1.1 等多级数字编号
    ]
    
    result = title
    for pattern in patterns:
        result = re.sub(pattern, '', result)
    
    return result.strip()

class OutlineGenerator:
    """使用LangChain调用大模型生成结构化大纲"""
    
    def __init__(self, readable_model_name: Optional[str] = None, use_rag: bool = True, use_web: bool = False):
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

        # 是否使用 WEB 搜索
        self.use_web = use_web
        
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
        context_msg: str = "",
        networking: bool = False,
        rerank: bool = False
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
                model=self.model,
                networking=networking,
                rerank=rerank
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

    def _get_rag_context(self, question: str, user_id: Optional[str], kb_ids: Optional[List[str]], context_msg: str = "", networking: bool = False, rerank: bool = False) -> str:
        """
        获取RAG上下文的通用方法
        
        Args:
            question: 问题内容
            user_id: 用户ID
            kb_ids: 知识库ID列表
            context_msg: 上下文信息，用于日志记录
            networking: 开启web搜索
            rerank: 开启精排
            
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
                context_msg=context_msg,
                networking=networking,
                rerank=rerank
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

    def generate_outline(self, prompt: str, file_contents: List[str] = None, user_id: str = None, kb_ids: List[str] = None, task_id: Optional[str] = None, db_session = None) -> Dict[str, Any]:
        """
        生成结构化大纲
        
        Args:
            prompt: 用户提供的写作提示
            file_contents: 用户上传的文件内容列表
            user_id: 用户ID，用于RAG搜索（如果启用）
            kb_ids: 知识库ID列表，用于RAG搜索（如果启用）
            task_id: 任务ID，用于更新任务进度
            db_session: 数据库会话，用于更新任务进度
            
        Returns:
            Dict: 包含大纲结构的字典
        """
        logger.info(f"开始生成大纲 [prompt_length={len(prompt)}, use_rag={self.use_rag}]")
        
        # 更新任务进度 - 开始
        update_task_progress(task_id, db_session, 10, "开始生成大纲", f"提示词长度: {len(prompt)}字")

        # 使用LLM提取用户需求
        user_requirements = self._extract_requirements_with_llm(prompt)
        required_level = user_requirements.get("required_level", 2)  # 默认为2级
        word_count = user_requirements.get("word_count")
        page_count = user_requirements.get("page_count")
        if not word_count and page_count:
            word_count = page_count * settings.WRITING_PER_PAGE_WORD_COUNT
            logger.info(f"根据页数({page_count}页)计算字数要求: {word_count}字")
        predefined_chapters = user_requirements.get("predefined_chapters", [])
        logger.info(f"要求层级：{required_level} 级")
        
        # 处理文件内容
        file_context = ""
        if file_contents and len(file_contents) > 0:
            file_context = "参考以下文件内容:\n" + "\n".join(file_contents)
            logger.info(f"使用参考文件内容 [files_count={len(file_contents)}]")
        else:
            file_context = "没有提供参考文件内容。"
            logger.info("无参考文件内容")
        
        # 更新任务进度 - 处理参考资料
        update_task_progress(task_id, db_session, 20, "处理参考资料", f"参考文件数量: {len(file_contents) if file_contents else 0}")
        
        # 获取RAG搜索结果（如果启用）
        update_task_progress(task_id, db_session, 25, "正在检索RAG知识库")
        rag_context = ""
        # if self.use_rag:
        #     rag_prompt = f"关于主题：{prompt}，请提供参考内容"
        #     rag_context = self._get_rag_context(
        #         question=rag_prompt,
        #         user_id=user_id,
        #         kb_ids=kb_ids,
        #         context_msg="生成大纲"
        #     )

        update_task_progress(task_id, db_session, 30, "检索RAG知识库完成", f"")
        
        # 更新任务进度 - 准备大纲生成
        update_task_progress(task_id, db_session, 35, "开始生成大纲", "构建提示模板")
        
        try:
            first_outline = self.generate_outline_new(prompt, required_level, task_id=task_id, db_session=db_session)
            if task_id and db_session:
                update_task_progress(task_id, db_session, 90, "已生成大纲及描述，正在检验大纲章节")
            
            # 处理子章节
            complete_outline = self._parse_outline_to_json(first_outline, prompt)
            
            # 验证和优化大纲结构
            self._validate_and_fix_outline(complete_outline)
            self._optimize_outline_structure(complete_outline)

            # 根据字数要求，重新分配大纲中各章节和段落的字数
            if word_count:
                self._distribute_word_outline(complete_outline, word_count)

            
            # 更新任务进度 - 完成
            update_task_progress(task_id, db_session, 100, "大纲生成完成", f"大纲包含{len(complete_outline['sub_paragraphs'])}个一级标题")
            
            return complete_outline
        except Exception as e:
            logger.error(f"生成大纲时出错: {str(e)}")
            # 更新任务进度 - 失败
            update_task_progress(task_id, db_session, 100, "大纲生成失败", f"错误信息: {str(e)}")
            
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
        
    def _extract_requirements_with_llm(self, prompt: str) -> Dict[str, Any]:
        """使用LLM提取用户需求，包括大纲层级数、字数、页数和预定义章节"""
        template = """
        你是一个专业的写作助手，请仔细分析用户的写作需求，提取关键要求信息。
        
        【用户需求】
        {prompt}
        
        请分析提取以下信息：
        1. 大纲层级数要求：用户是否指定了大纲需要多少级（如三级大纲、四级目录等）
        2. 字数要求：用户是否指定了文章总字数
        3. 页数要求：用户是否指定了文章总页数
        4. 预定义章节：用户是否已明确定义了一级大纲或主要章节
        
        注意：
        - 如果用户没有明确指定大纲层级数，默认为2级
        - 仔细辨别用户提供的一级大纲/章节列表，通常会以列表形式出现
        - 有些用户会使用"一级标题包括"、"主要章节有"等表述方式定义章节结构
        
        【返回格式】
        以JSON格式返回分析结果，格式如下：
        {{
          "required_level": 数字(1-4),
          "word_count": 数字或null,
          "page_count": 数字或null,
          "predefined_chapters": ["章节1", "章节2", ...] 或 []
        }}
        
        仅返回JSON格式内容，不要有其他文字说明。
        """
        
        input_variables = {
            "prompt": prompt
        }
        
        try:
            # 调用LLM
            response = self.llm.invoke(
                template.format(**input_variables),
                temperature=0.2,  # 使用较低温度以获得更确定性的结果
            )
            
            # 解析JSON响应
            try:
                requirements = json.loads(response.content)
                # 验证返回值的合法性
                requirements["required_level"] = int(requirements.get("required_level", 3))
                if requirements["required_level"] < 1 or requirements["required_level"] > 4:
                    requirements["required_level"] = 3  # 如果不在合理范围内，使用默认值
                
                if "word_count" in requirements and requirements["word_count"] is not None:
                    requirements["word_count"] = int(requirements["word_count"])
                
                if "page_count" in requirements and requirements["page_count"] is not None:
                    requirements["page_count"] = int(requirements["page_count"])
                
                if "predefined_chapters" not in requirements:
                    requirements["predefined_chapters"] = []
                    
                return requirements
            except (json.JSONDecodeError, ValueError, TypeError):
                # 如果解析失败，返回默认值
                logger.error(f"Failed to parse requirements from LLM response: {response}")
                return {
                    "required_level": 3,
                    "word_count": None,
                    "page_count": None,
                    "predefined_chapters": []
                }
        except Exception as e:
            logger.error(f"Error calling LLM for requirement extraction: {str(e)}")
            # 出错时返回默认值
            return {
                "required_level": 3,
                "word_count": None,
                "page_count": None,
                "predefined_chapters": []
            }
        
    def _generate_first_level_outline(self, prompt: str, file_context: str, rag_context: str, required_level: int, word_count: Optional[int], page_count: Optional[int], predefined_chapters: List[str] = None) -> Dict[str, Any]:
        """生成一级大纲结构"""
        # 检查是否有预定义章节
        if predefined_chapters and len(predefined_chapters) > 0:
            # 用户已定义一级大纲，构建初始结构
            outline_data = {
                "title": "待定标题",  # 后续更新
                "sub_paragraphs": []
            }
            
            for chapter_title in predefined_chapters:
                outline_data["sub_paragraphs"].append({
                    "title": chapter_title,
                    "description": "",  # 待LLM补充
                    "count_style": "medium",  # 默认值，待LLM调整
                    "level": 1,
                    "children": []
                })
                
            # 调用LLM补充一级大纲的描述和篇幅风格
            return self._enhance_first_level_outline(outline_data, prompt, file_context, rag_context)
        else:
            # 用户未定义一级大纲，完全由LLM生成
            template = """
            你是一个专业的写作助手，请根据用户的写作需求生成一个一级大纲结构。
            
            【用户需求】
            {prompt}
            
            【参考文件】
            {file_context}
            
            【参考资料】
            {rag_context}
            
            【大纲要求】
            请只生成一级大纲(即文章的主要章节)，不要生成子章节:
            1. 文章标题
            2. 多个一级段落，每个段落包含:
               - 标题(不要使用任何编号)
               - 简短描述
               - 篇幅风格(short/medium/long)
            
            【格式要求】
            1. 大纲总层级将需要达到{required_level}级
            2. {word_count_req}
            3. {page_count_req}
            4. 严格禁止在标题中使用任何形式的编号
            
            【返回格式】
            以JSON格式返回，格式如下:
            {{
                "title": "文章标题",
                "sub_paragraphs": [
                    {{
                        "title": "一级段落标题1",
                        "description": "段落描述1",
                        "count_style": "medium",
                        "level": 1,
                        "children": []
                    }},
                    ...
                ]
            }}
            """
            
            word_count_req = f"文章总字数约为{word_count}字" if word_count else ""
            page_count_req = f"文章总页数约为{page_count}页" if page_count else ""
            
            # 构建提示
            input_variables = {
                "prompt": prompt,
                "file_context": file_context,
                "rag_context": rag_context,
                "required_level": required_level,
                "word_count_req": word_count_req,
                "page_count_req": page_count_req
            }

            try:
                # 调用LLM
                response = self.llm.invoke(
                    template.format(**input_variables),
                    temperature=0.5,
                )

                content = response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()

                return json.loads(content)
            except Exception as e:
                logger.error(f"Error calling LLM for outline enhancement: {str(e)}")
                return {}


    def _enhance_first_level_outline(self, outline_data: Dict[str, Any], prompt: str, file_context: str, rag_context: str) -> Dict[str, Any]:
        """为预定义的一级大纲补充描述和篇幅风格"""
        template = """
        你是一个专业的写作助手，用户已经定义了文章的一级大纲结构，请为每个章节补充恰当的描述和篇幅风格。
        
        【用户需求】
        {prompt}
        
        【参考文件】
        {file_context}
        
        【参考资料】
        {rag_context}
        
        【已定义的大纲结构】
        {outline_structure}
        
        请为每个章节添加:
        1. 简短的描述，说明该章节将要讨论的内容
        2. 篇幅风格(short/medium/long)，根据章节内容的复杂程度和重要性确定
        3. 并为整篇文章生成一个合适的标题
        
        【返回格式】
        以JSON格式返回完整的一级大纲，格式如下:
        {{
            "title": "文章标题",
            "sub_paragraphs": [
                {{
                    "title": "一级段落标题1",
                    "description": "段落描述1",
                    "count_style": "medium",
                    "level": 1,
                    "children": []
                }},
                ...
            ]
        }}
        """
        
        # 构建大纲结构描述
        outline_structure = "文章章节列表:\n"
        for i, chapter in enumerate(outline_data["sub_paragraphs"]):
            outline_structure += f"{i+1}. {chapter['title']}\n"
        
        input_variables = {
            "prompt": prompt,
            "file_context": file_context,
            "rag_context": rag_context,
            "outline_structure": outline_structure
        }
        
        try:
            # 调用LLM
            response = self.llm.invoke(
                template.format(**input_variables),
                temperature=0.5,
            )
            
            # 解析JSON响应
            try:
                content = response.content
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                enhanced_outline = json.loads(content)
                # 保留原标题，只更新描述和篇幅风格
                if "sub_paragraphs" in enhanced_outline and len(enhanced_outline["sub_paragraphs"]) > 0:
                    for i, chapter in enumerate(enhanced_outline["sub_paragraphs"]):
                        if i < len(outline_data["sub_paragraphs"]):
                            # 保留原有标题，更新描述和篇幅风格
                            original_title = outline_data["sub_paragraphs"][i]["title"]
                            outline_data["sub_paragraphs"][i]["description"] = chapter.get("description", "")
                            outline_data["sub_paragraphs"][i]["count_style"] = chapter.get("count_style", "medium")
                
                # 更新文章标题
                if "title" in enhanced_outline and enhanced_outline["title"]:
                    outline_data["title"] = enhanced_outline["title"]
                    
                return outline_data
            except json.JSONDecodeError:
                logger.error(f"Failed to parse enhanced outline from LLM response: {response}")
                return outline_data
        except Exception as e:
            logger.error(f"Error calling LLM for outline enhancement: {str(e)}")
            return outline_data
        
    def _expand_outline_with_subchapters(self, outline_data: Dict[str, Any], prompt: str, file_context: str, rag_context: str, required_level: int, word_count: Optional[int], page_count: Optional[int], task_id: Optional[str], db_session) -> Dict[str, Any]:
        """为大纲中的每个一级章节生成所有子章节"""
        first_level_chapters = outline_data["sub_paragraphs"]
        chapter_count = len(first_level_chapters)

        # 根据字数或页数要求决定生成的子章节数量
        children_num = "2-3"
        if (word_count and word_count >= 80000 and word_count < 150000) or (page_count and page_count >= 100 and page_count < 200):
            children_num = "4-5"
        elif (word_count and word_count >= 150000) or (page_count and page_count >= 200):
            children_num = "6-7"

        logger.info(f"字数要求：{word_count}，页数要求：{page_count}，子章节数量：{children_num}")
        
        # 使用并行处理框架
        try:
            import concurrent.futures
            use_parallel = True
        except ImportError:
            use_parallel = False
            logger.warning("concurrent.futures module not available, falling back to sequential processing")
        
        # 防止并发数据库会话访问的锁
        from threading import Lock
        db_session_lock = Lock()

        # 创建子章节生成任务函数
        def generate_chapter_task(index, chapter):
            if task_id and db_session:
                with db_session_lock:
                    try:
                        progress = 40 + int(50 * (index / chapter_count))
                        update_task_progress(task_id, db_session, progress, f"正在生成第{index+1}/{chapter_count}个章节的子章节...")
                    except Exception as e:
                        logger.error(f"更新任务进度失败: {str(e)}")
            
            # 计算本章节字数/页数参考值（按比例分配总量）
            chapter_word_count = int(word_count / chapter_count) if word_count else None
            chapter_page_count = max(1, int(page_count / chapter_count)) if page_count else None
            
            # 递归生成子章节
            subchapters = self._generate_subchapters_recursively(
                prompt, 
                chapter["title"],
                chapter["description"],
                file_context,
                rag_context,
                required_level,
                current_level=1,  # 当前是一级章节
                chapter_word_count=chapter_word_count,
                chapter_page_count=chapter_page_count,
                task_id=task_id,  # 传递task_id用于日志记录
                chapter_index=index,
                total_chapters=chapter_count,
                children_num=children_num
            )
            
            return index, subchapters
        
        # 处理所有一级章节
        if use_parallel and chapter_count > 1:
            # 并行处理
            results = {}
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, chapter_count)) as executor:
                # 提交所有任务
                future_to_index = {
                    executor.submit(generate_chapter_task, i, chapter): i 
                    for i, chapter in enumerate(first_level_chapters)
                }
                
                # 收集结果
                for future in concurrent.futures.as_completed(future_to_index):
                    try:
                        index, subchapters = future.result()
                        results[index] = subchapters
                    except Exception as e:
                        logger.error(f"Error in chapter generation task: {str(e)}")
                        # 发生错误时使用备用子章节
                        index = future_to_index[future]
                        results[index] = self._create_default_subchapters(first_level_chapters[index]["title"])
            
            # 将结果按原始顺序组织回大纲
            for i in range(chapter_count):
                if i in results:
                    first_level_chapters[i]["children"] = results[i]
                else:
                    # 如果某个任务没有返回结果，使用备用章节
                    first_level_chapters[i]["children"] = self._create_default_subchapters(first_level_chapters[i]["title"])

            # 生成完成后，在主线程中更新总进度
            if task_id and db_session:
                try:
                    update_task_progress(task_id, db_session, 90, "子章节生成完成，正在优化大纲结构...")
                except Exception as e:
                    logger.error(f"更新任务进度失败: {str(e)}")
        else:
            # 顺序处理
            for i, chapter in enumerate(first_level_chapters):
                # 直接更新进度，不需要锁
                if task_id and db_session:
                    try:
                        progress = 40 + int(50 * (i / chapter_count))
                        update_task_progress(task_id, db_session, progress, f"正在生成第{i+1}/{chapter_count}个章节的子章节...")
                    except Exception as e:
                        logger.error(f"更新任务进度失败: {str(e)}")

            # 递归生成子章节
                subchapters = self._generate_subchapters_recursively(
                    prompt, 
                    chapter["title"],
                    chapter["description"],
                    file_context,
                    rag_context,
                    required_level,
                    current_level=1,
                    chapter_word_count=int(word_count / chapter_count) if word_count else None,
                    chapter_page_count=max(1, int(page_count / chapter_count)) if page_count else None,
                    task_id=task_id,
                    chapter_index=i,
                    total_chapters=chapter_count,
                    children_num=children_num
                )
                
                chapter["children"] = subchapters
        
        return outline_data
    
    def _generate_subchapters_recursively(
        self, 
        prompt: str,
        chapter_title: str,
        chapter_description: str,
        file_context: str, 
        rag_context: str, 
        required_level: int, 
        current_level: int = 1,
        chapter_word_count: Optional[int] = None, 
        chapter_page_count: Optional[int] = None,
        task_id: Optional[str] = None,
        chapter_index: int = 0,
        total_chapters: int = 1,
        children_num: str = "2-3"
    ) -> List[Dict[str, Any]]:
        """递归生成章节的子章节"""
        # 记录日志但不更新数据库
        if task_id:
            logger.info(f"生成章节 [{chapter_index+1}/{total_chapters}] '{chapter_title}' 的第{current_level+1}级子章节")

        # 如果已经达到要求的最大层级深度，则无需继续生成子章节
        if current_level >= required_level:
            return []
        
        # 计算下一级层级
        next_level = current_level + 1
        
        # 构建提示模板
        template = """
        你是一个专业的写作助手，请为特定章节生成直接子章节。
        
        【章节信息】
        标题: {chapter_title}
        描述: {chapter_description}
        当前层级: {current_level}级
        需创建: {next_level}级子章节
        总体要求层级深度: {required_level}级
        
        【用户需求】
        {prompt}
        
        【参考信息】
        {context}
        
        【任务要求】
        1. 仅创建下一级({next_level}级)的子章节，不要生成更深层级
        2. 生成{children_num}个子章节，请结合字数、页数要求灵活分配
        3. 每个子章节必须有明确具体的标题和简短描述
        4. 标题必须有实质性内容，与父章节紧密相关
        5. 标题不得包含编号，不要使用"详细内容"等无意义词语
        
        【返回格式】
        仅返回以下JSON格式:
        [
          {{
            "title": "具体明确的子章节标题1",
            "description": "具体的子章节描述1"
          }},
          {{
            "title": "具体明确的子章节标题2",
            "description": "具体的子章节描述2"
          }},
          // 更多子章节...
        ]
        
        不要有任何额外说明，只返回JSON数组。
        """
        
        # 合并文件和RAG上下文
        combined_context = ""
        if file_context:
            combined_context += "文件参考：" + file_context[:500] + "\n\n"
        if rag_context:
            combined_context += "知识库参考：" + rag_context[:500]
        
        input_variables = {
            "chapter_title": chapter_title,
            "chapter_description": chapter_description,
            "current_level": current_level,
            "next_level": next_level,
            "required_level": required_level,
            "prompt": prompt,
            "context": combined_context,
            "children_num": children_num
        }
        
        try:
            # 调用LLM
            response = self.llm.invoke(
                template.format(**input_variables),
                temperature=0.7,
                max_tokens=2500
            )
            
            # 尝试提取和解析JSON
            try:
                # 尝试找到并提取JSON部分
                content = response.content
                json_match = re.search(r'(\[.*\])', content.replace('\n', ' '), re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                
                subchapters_raw = json.loads(content)
                
                # 验证和处理子章节
                if not isinstance(subchapters_raw, list) or len(subchapters_raw) == 0:
                    # 如果不是列表或为空，使用备用生成
                    return []
                
                # 转换为标准格式并递归处理更深层级
                standard_subchapters = []
                
                # 限制子章节数量
                max_subchapters = min(len(subchapters_raw), 7)  # 最多7个子章节
                
                for i in range(max_subchapters):
                    subchapter = subchapters_raw[i]
                    
                    # 验证子章节格式
                    if not isinstance(subchapter, dict) or "title" not in subchapter:
                        continue
                    
                    # 整理子章节数据
                    subchapter_title = subchapter.get("title", f"子章节{i+1}")
                    subchapter_description = subchapter.get("description", "")
                    
                    # 跳过无意义的标题
                    if "详细内容" in subchapter_title or len(subchapter_title) < 3:
                        continue
                    
                    # 创建子章节对象
                    subchapter_obj = {
                        "title": subchapter_title,
                        "description": subchapter_description,
                        "level": current_level + 1,
                        "children": []
                    }
                    
                    # 如果当前层级还没达到要求的深度，递归生成更深层级的子章节
                    if next_level < required_level:
                        # 计算更深层级子章节的字数/页数（按比例分配）
                        sub_word_count = int(chapter_word_count / max_subchapters) if chapter_word_count else None
                        sub_page_count = max(1, int(chapter_page_count / max_subchapters)) if chapter_page_count else None
                        
                        # 递归生成更深层级子章节
                        deeper_subchapters = self._generate_subchapters_recursively(
                            prompt,
                            subchapter_title,
                            subchapter_description,
                            file_context,
                            rag_context,
                            required_level,
                            next_level,
                            sub_word_count,
                            sub_page_count,
                            task_id,
                            chapter_index,
                            total_chapters,
                            children_num
                        )
                        
                        subchapter_obj["children"] = deeper_subchapters
                    
                    standard_subchapters.append(subchapter_obj)
                
                # 确保至少有一些子章节
                if standard_subchapters:
                    return standard_subchapters
                
            except Exception as e:
                logger.error(f"Error parsing subchapters: {str(e)}")
                # 解析失败，使用备用生成
        
        except Exception as e:
            logger.error(f"Error calling LLM for subchapters: {str(e)}")
            # 调用失败，使用备用生成
        
        # 所有尝试失败后，使用备用生成方案
        return []
        
    def _generate_subchapters(self, prompt: str, parent_chapter: Dict[str, Any], chapter_context: str, file_context: str, rag_context: str, required_level: int, current_level: int, chapter_word_count: Optional[int], chapter_page_count: Optional[int]) -> List[Dict[str, Any]]:
        """生成指定章节的子章节"""
        # 如果已经达到要求的层级深度，则不需要继续生成
        if current_level >= required_level:
            return []
            
        template = """
        你是一个专业的写作助手，请根据用户的写作需求为特定章节生成结构化子章节。
        
        【用户需求】
        {prompt}
        
        【章节信息】
        {chapter_context}
        
        【参考文件】
        {file_context}
        
        【参考资料】
        {rag_context}
        
        【子章节要求】
        1. 为上述章节创建{next_level}级子章节
        2. 大纲总层级需要达到{required_level}级
        3. 当前章节深度为{current_level}级，子章节为{next_level}级
        4. {word_count_req}
        5. {page_count_req}
        6. 每个子章节包含:
           - 标题(不要使用任何编号)
           - 简短描述
           - 如果还未达到要求的层级深度，请确保章节结构可以进一步展开
        
        【格式要求】
        1. 严格禁止在标题中使用任何形式的编号
        2. 确保子章节标题与父章节相关且不重复
        3. 每个子章节内容应该是父章节的合理细分
        
        【返回格式】
        以JSON数组格式返回子章节列表，格式如下:
        [
            {{
                "title": "子章节标题1",
                "description": "子章节描述1",
                "level": {current_level} + 1
                "children": []
            }},
            ...
        ]
        """
        
        next_level = current_level + 1
        word_count_req = f"本章节总字数约为{chapter_word_count}字" if chapter_word_count else ""
        page_count_req = f"本章节总页数约为{chapter_page_count}页" if chapter_page_count else ""
        
        # 构建提示
        input_variables = {
            "prompt": prompt,
            "chapter_context": chapter_context,
            "file_context": file_context,
            "rag_context": rag_context,
            "current_level": current_level,
            "next_level": next_level,
            "required_level": required_level,
            "word_count_req": word_count_req,
            "page_count_req": page_count_req
        }

        result = self.llm.invoke(template.format(**input_variables))
        content = result.content
        # 处理可能的markdown代码块
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()
        
        if not content:
            logger.warning(f"Empty content after processing LLM response: {result.content}")
            return []
        subchapters = json.loads(content)
        
        if next_level < required_level:
            subchapter_count = len(subchapters)
            for i, subchapter in enumerate(subchapters):
                # 为每个子章节计算相应的字数/页数
                subchapter_word_count = int(chapter_word_count / subchapter_count) if chapter_word_count else None
                subchapter_page_count = max(1, int(chapter_page_count / subchapter_count)) if chapter_page_count else None
                
                # 构建子章节上下文
                subchapter_context = f"{chapter_context} 这是其中的第{i+1}个子章节，标题为: {subchapter['title']}，描述为: {subchapter['description']}。"
                
                # 递归生成更深层级的子章节
                sub_subchapters = self._generate_subchapters(
                    prompt,
                    subchapter,
                    subchapter_context,
                    file_context,
                    rag_context,
                    required_level,
                    next_level,
                    subchapter_word_count,
                    subchapter_page_count
                )
                
                subchapter["children"] = sub_subchapters
                
        return subchapters

    def _distribute_word_outline(self, outline_data: Dict[str, Any], word_count: int) -> None:
        """
        根据总体字数，计算每个段落的预估字数
        
        Args:
            outline_data: 大纲数据
            word_count: 总字数
        """
        logger.info(f"开始分配大纲字数，总字数: {word_count}字")
        
        # 从配置文件获取每个段落生成的最大字数
        WRITING_MAX_WORD_COUNT_PER_GENERATION = settings.WRITING_MAX_WORD_COUNT_PER_GENERATION
        logger.info(f"每个段落的最大生成字数: {WRITING_MAX_WORD_COUNT_PER_GENERATION}")
        
        if not outline_data or "sub_paragraphs" not in outline_data or not outline_data["sub_paragraphs"]:
            logger.warning("大纲为空或没有段落，无法分配字数")
            return
            
        # 计算当前大纲段落数量和能够生成的最大字数
        def count_paragraphs(paragraphs):
            count = len(paragraphs)
            for para in paragraphs:
                if "children" in para and para["children"]:
                    count += count_paragraphs(para["children"])
            return count
            
        total_paragraphs = count_paragraphs(outline_data["sub_paragraphs"])
        max_possible_words = total_paragraphs * WRITING_MAX_WORD_COUNT_PER_GENERATION
        
        logger.info(f"当前大纲有 {total_paragraphs} 个段落，最多可生成 {max_possible_words} 字")
        
        # 如果当前段落数不足以满足字数要求，需要添加更多段落
        if max_possible_words < word_count:
            logger.info(f"当前段落数不足以满足 {word_count} 字的要求，需要添加更多段落")
            
            # 计算需要添加的段落数
#             additional_paragraphs_needed = (word_count - max_possible_words + WRITING_MAX_WORD_COUNT_PER_GENERATION - 1) // WRITING_MAX_WORD_COUNT_PER_GENERATION
#             logger.info(f"需要额外添加 {additional_paragraphs_needed} 个段落")
            
#             # 找出最深层级的段落，并为其添加子段落
#             def add_paragraphs_to_deep_nodes(paragraphs, depth=1, to_add=0):
#                 if to_add <= 0:
#                     return 0
                
#                 # 如果当前层级有段落且没有子段落，则添加子段落
#                 leaf_nodes = [p for p in paragraphs if "children" not in p or not p["children"]]
                
#                 # 如果没有叶子节点，递归检查每个段落的子节点
#                 if not leaf_nodes:
#                     remaining = to_add
#                     for para in paragraphs:
#                         if "children" in para and para["children"]:
#                             added = add_paragraphs_to_deep_nodes(para["children"], depth+1, remaining)
#                             remaining -= added
#                             if remaining <= 0:
#                                 break
#                     return to_add - remaining
                
#                 # 为每个叶子节点添加子段落，直到达到所需数量
#                 added_count = 0
#                 for leaf in leaf_nodes:
#                     if added_count >= to_add:
#                         break
                    
#                     # 确保有children字段
#                     if "children" not in leaf:
#                         leaf["children"] = []
                    
#                     # 使用大模型生成子段落标题和描述
#                     parent_title = leaf.get("title", "无标题")
#                     parent_description = leaf.get("description", "")
                    
#                     # 构建提示词
#                     prompt = f"""
# 根据以下父段落的信息，为其生成一个合适的子段落标题和描述。生成的内容应该与父段落自然衔接并进一步扩展其主题。

# 父段落标题: {parent_title}
# 父段落描述: {parent_description}

# 请提供一个格式为JSON的响应，包含:
# {{
#     "title": "子段落标题",
#     "description": "子段落详细描述"
# }}
# """
                    
#                     try:
#                         # 调用大模型生成子段落信息
#                         logger.info(f"通过大模型为段落 '{parent_title}' 生成子段落")
#                         response = self.llm.invoke(prompt)
                        
#                         # 解析响应
#                         import json
#                         import re
                        
#                         # 尝试提取JSON部分
#                         json_match = re.search(r'(\{.*?\})', response.content.replace('\n', ' '), re.DOTALL)
#                         if json_match:
#                             result = json.loads(json_match.group(1))
                            
#                             # 创建子段落
#                             new_para = {
#                                 "title": result.get("title", f"{parent_title} - 补充内容"),
#                                 "description": result.get("description", "详细展开父段落内容"),
#                                 "level": leaf.get("level", 1) + 1,
#                                 "count_style": "medium"
#                             }
#                         else:
#                             # 如果无法解析JSON，使用默认值
#                             new_para = {
#                                 "title": f"{parent_title} - 补充内容 {len(leaf['children'])+1}",
#                                 "description": f"根据父段落内容补充详细说明",
#                                 "level": leaf.get("level", 1) + 1,
#                                 "count_style": "medium"
#                             }
#                     except Exception as e:
#                         logger.error(f"生成子段落时出错: {str(e)}")
#                         # 出错时使用默认值
#                         new_para = {
#                             "title": f"{parent_title} - 补充内容 {len(leaf['children'])+1}",
#                             "description": f"根据父段落内容补充详细说明",
#                             "level": leaf.get("level", 1) + 1,
#                             "count_style": "medium"
#                         }
                    
#                     leaf["children"].append(new_para)
#                     added_count += 1
                    
#                     logger.info(f"为段落 '{leaf.get('title', '无标题')}' 添加子段落: '{new_para['title']}'")
                
#                 return added_count
            
#             # 添加段落
#             added = add_paragraphs_to_deep_nodes(outline_data["sub_paragraphs"], to_add=additional_paragraphs_needed)
#             logger.info(f"成功添加了 {added} 个段落")
            
#             # 重新计算段落总数
#             total_paragraphs = count_paragraphs(outline_data["sub_paragraphs"])
#             max_possible_words = total_paragraphs * WRITING_MAX_WORD_COUNT_PER_GENERATION
#             logger.info(f"调整后大纲有 {total_paragraphs} 个段落，最多可生成 {max_possible_words} 字")
            
        # 获取一级段落列表
        top_level_paragraphs = outline_data["sub_paragraphs"]
        
        # 第一步：创建权重映射并计算段落权重
        def calculate_weight(paragraph):
            # 默认权重为1
            weight = 1
            
            # 根据篇幅风格调整权重
            count_style = paragraph.get("count_style", "medium").lower()
            if count_style == "short":
                weight = 0.5
            elif count_style == "medium":
                weight = 1
            elif count_style == "long":
                weight = 2
                
            # 如果段落有子段落，考虑子段落的复杂度
            children = paragraph.get("children", [])
            if children:
                # 子段落数量会增加权重
                child_factor = 1 + 0.1 * len(children)
                weight *= child_factor
                
            return weight
        
        # 为每个一级段落计算权重
        total_weight = 0
        for para in top_level_paragraphs:
            para["_weight"] = calculate_weight(para)
            total_weight += para["_weight"]
        
        # 第二步：根据权重比例分配总字数
        for para in top_level_paragraphs:
            # 计算该段落应分配的字数
            para_weight = para["_weight"]
            weight_ratio = para_weight / total_weight if total_weight > 0 else 1 / len(top_level_paragraphs)
            para_word_count = int(word_count * weight_ratio)
            
            # 设置段落字数
            para["expected_word_count"] = para_word_count
            
            logger.info(f"一级段落 '{para.get('title', '无标题')}' 分配 {para_word_count} 字")
            
            # 递归分配子段落字数
            children = para.get("children", [])
            if children:
                self._distribute_word_count_to_children(children, para_word_count)
                
        # 第三步：确保分配的总字数等于预期总字数（处理舍入误差）
        allocated_words = sum(p.get("expected_word_count", 0) for p in top_level_paragraphs)
        
        # 如果存在差异，调整权重最大的段落
        if allocated_words != word_count:
            diff = word_count - allocated_words
            # 找到权重最大的段落
            max_weight_para = max(top_level_paragraphs, key=lambda p: p.get("_weight", 0))
            # 调整字数
            max_weight_para["expected_word_count"] += diff
            logger.info(f"调整段落 '{max_weight_para.get('title', '无标题')}' 字数 {diff} 字以匹配总字数")
        
        # 第四步：确保每个段落的字数不超过最大限制
        def limit_paragraph_word_count(paragraphs):
            for para in paragraphs:
                # 限制字数在最大生成字数以内
                if para.get("expected_word_count", 0) > WRITING_MAX_WORD_COUNT_PER_GENERATION:
                    logger.info(f"段落 '{para.get('title', '无标题')}' 字数 {para.get('expected_word_count')} 超过限制，调整为 {WRITING_MAX_WORD_COUNT_PER_GENERATION}")
                    para["expected_word_count"] = WRITING_MAX_WORD_COUNT_PER_GENERATION
                
                # 递归处理子段落
                if "children" in para and para["children"]:
                    limit_paragraph_word_count(para["children"])
        
        limit_paragraph_word_count(outline_data["sub_paragraphs"])
        
        # 清理临时权重数据
        for para in top_level_paragraphs:
            if "_weight" in para:
                del para["_weight"]
                
        logger.info("字数分配完成")
    
    def _distribute_word_count_to_children(self, children: List[Dict[str, Any]], parent_word_count: int) -> None:
        """
        递归地为子段落分配字数
        
        Args:
            children: 子段落列表
            parent_word_count: 父段落字数
        """
        if not children or parent_word_count <= 0:
            return
            
        # 计算每个子段落的权重
        total_weight = 0
        for child in children:
            # 默认每个子段落权重相同
            child["_weight"] = 1
            
            # 考虑子段落的深度
            if child.get("children", []):
                # 有子段落的段落权重略高
                child["_weight"] *= 1.2
                
            total_weight += child["_weight"]
        
        # 根据权重分配字数
        remaining_words = parent_word_count
        for i, child in enumerate(children):
            # 最后一个子段落分配所有剩余字数，确保总和等于父段落字数
            if i == len(children) - 1:
                child["expected_word_count"] = remaining_words
            else:
                weight_ratio = child["_weight"] / total_weight if total_weight > 0 else 1 / len(children)
                child_word_count = int(parent_word_count * weight_ratio)
                child["expected_word_count"] = child_word_count
                remaining_words -= child_word_count
            
            # 递归处理子段落的子段落
            if child.get("children", []):
                self._distribute_word_count_to_children(child["children"], child["expected_word_count"])
            
            # 清理临时权重数据
            if "_weight" in child:
                del child["_weight"]

    def _validate_and_fix_outline(self, outline_data: Dict[str, Any]) -> None:
        """
        验证大纲结构，检查是否有重复标题，并尝试修复问题
        
        Args:
            outline_data: 大纲数据
        """
        logger.info("开始验证大纲结构")
        
        # 收集所有标题及其路径
        all_titles = {}  # 标题 -> [路径列表]
        duplicate_titles = set()
        
        def check_duplicates(paragraphs, parent_path="", level=1):
            for para in paragraphs:
                title = para.get("title", "").strip()
                full_path = f"{parent_path}/{title}" if parent_path else title
                
                # 记录标题及其路径
                if title in all_titles:
                    all_titles[title].append({"path": full_path, "level": level, "para": para})
                    duplicate_titles.add(title)
                else:
                    all_titles[title] = [{"path": full_path, "level": level, "para": para}]
                
                # 递归检查子段落
                children = para.get("children", [])
                if children:
                    check_duplicates(children, full_path, level + 1)
        
        # 检查重复标题
        check_duplicates(outline_data.get("sub_paragraphs", []))
        
        if duplicate_titles:
            logger.warning(f"检测到{len(duplicate_titles)}个重复标题: {duplicate_titles}")
            
            # 尝试修复重复标题
            for title in duplicate_titles:
                occurrences = all_titles[title]
                logger.info(f"处理重复标题 '{title}' ({len(occurrences)}次出现)")
                
                # 按层级排序，保持较高层级的标题不变，修改较低层级的标题
                occurrences.sort(key=lambda x: x["level"])
                
                # 保留第一个出现的标题不变
                for i in range(1, len(occurrences)):
                    para = occurrences[i]["para"]
                    level = occurrences[i]["level"]
                    path = occurrences[i]["path"]
                    
                    # 获取父路径的最后一部分作为上下文
                    parent_context = path.split('/')[-2] if '/' in path else ""
                    
                    # 根据上下文和层级选择合适的修改方式
                    if parent_context and not title.startswith(parent_context):
                        # 使用父标题作为上下文
                        new_title = f"{title}（{parent_context}相关）"
                    else:
                        # 根据层级添加修饰词
                        modifiers = ["概述", "详情", "分析", "实施", "评估", "方法", "技术", "应用", "原理", "框架"]
                        modifier = modifiers[min(level-1, len(modifiers)-1)]
                        
                        # 避免重复添加相同的修饰词
                        if not title.endswith(modifier):
                            new_title = f"{title}{modifier}"
                        else:
                            # 如果已经有相同的修饰词，尝试使用不同的修饰词
                            alt_modifiers = [m for m in modifiers if m != modifier]
                            if alt_modifiers:
                                new_title = f"{title.replace(modifier, '')}{alt_modifiers[0]}"
                            else:
                                # 最后的备选方案
                                new_title = f"{title} ({level}级)"
                    
                    logger.info(f"修改重复标题: '{title}' -> '{new_title}' [路径: {path}, 层级: {level}]")
                    para["title"] = new_title
            
            # 再次检查是否还有重复标题
            all_titles_after_fix = set()
            duplicate_after_fix = set()
            
            def check_duplicates_after_fix(paragraphs):
                for para in paragraphs:
                    title = para.get("title", "").strip()
                    
                    if title in all_titles_after_fix:
                        duplicate_after_fix.add(title)
                    else:
                        all_titles_after_fix.add(title)
                    
                    # 递归检查子段落
                    children = para.get("children", [])
                    if children:
                        check_duplicates_after_fix(children)
            
            check_duplicates_after_fix(outline_data.get("sub_paragraphs", []))
            
            if duplicate_after_fix:
                logger.warning(f"修复后仍有{len(duplicate_after_fix)}个重复标题: {duplicate_after_fix}")
                # 对于仍然重复的标题，添加唯一标识符
                def add_unique_identifier(paragraphs):
                    for para in paragraphs:
                        title = para.get("title", "").strip()
                        if title in duplicate_after_fix:
                            # 添加唯一标识符
                            para["title"] = f"{title} ({uuid.uuid4().hex[:4]})"
                        
                        # 递归处理子段落
                        children = para.get("children", [])
                        if children:
                            add_unique_identifier(children)
                
                add_unique_identifier(outline_data.get("sub_paragraphs", []))
                logger.info("已为剩余重复标题添加唯一标识符")
            else:
                logger.info("所有重复标题已成功修复")
        else:
            logger.info("未检测到重复标题")
        
        # 检查并修复空标题
        def fix_empty_titles(paragraphs, parent_title=""):
            for para in paragraphs:
                title = para.get("title", "").strip()
                if not title:
                    # 为空标题生成一个基于父标题的新标题
                    if parent_title:
                        new_title = f"{parent_title}子项"
                    else:
                        new_title = "未命名段落"
                    
                    logger.warning(f"检测到空标题，已修改为: '{new_title}'")
                    para["title"] = new_title
                
                # 递归处理子段落
                children = para.get("children", [])
                if children:
                    fix_empty_titles(children, title)
        
        # 修复空标题
        fix_empty_titles(outline_data.get("sub_paragraphs", []))
        
        # 验证目录层级深度
        max_level_found = 1
        
        def verify_depth(paragraphs, current_level=1):
            nonlocal max_level_found
            max_level_found = max(max_level_found, current_level)
            
            for para in paragraphs:
                children = para.get("children", [])
                if children:
                    verify_depth(children, current_level + 1)
        
        verify_depth(outline_data.get("sub_paragraphs", []))
        logger.info(f"大纲中发现的最大层级: {max_level_found}级")
        
        # 无法在这里访问prompt参数，只记录最大层级即可
        
    def _extract_required_level_from_prompt(self, prompt: str) -> int:
        """
        通过 LLM 提取用户提示中的目录层级要求和字数要求
        
        Args:
            prompt: 用户提示
            
        Returns:
            dict: 包含层级要求和字数要求的字典，如 {"level": 3, "word_count": 2000}
        """
        if not prompt:
            return {"level": 2, "word_count": None}
            
        # 构建提示词让 LLM 分析用户需求
        analysis_prompt = f"""
        请分析以下用户提示，提取出关于文章大纲结构的具体要求：
        1. 大纲层级要求（默认为2级，如有明确要求请指出具体层级数字）
        2. 文章总字数要求（如有明确要求请提供具体数字）
        3. 文章页数要求（如有明确要求请提供具体数字）
        
        仅返回 JSON 格式结果，包含 level（整数）、word_count（整数或 null）和 page_count（整数或 null）字段。
        
        用户提示: {prompt}
        """
        
        try:
            # 调用 LLM 获取分析结果
            response = self.llm.invoke(analysis_prompt)
            
            # 尝试解析结果为 JSON
            import json
            import re
            
            response_text = response.content if hasattr(response, 'content') else str(response)
            # 尝试从响应中提取 JSON 部分
            json_match = re.search(r'(\{.*?\})', response_text.replace('\n', ' '), re.DOTALL)
            if json_match:
                result = json.loads(json_match.group(1))
            else:
                # 如果找不到 JSON，采用保守的默认值
                result = {"level": 2, "word_count": None, "page_count": None}
                
            # 确保结果包含必要的字段
            if "level" not in result:
                result["level"] = 2
            if "word_count" not in result:
                result["word_count"] = None
            if "page_count" not in result:
                result["page_count"] = None
                
            # 如果有页数要求但没有字数要求，则将页数转换为字数（每页800字）
            if result["page_count"] and (result["word_count"] is None or result["word_count"] == 0):
                try:
                    page_count = float(result["page_count"])
                    result["word_count"] = int(page_count * 800)
                    logger.info(f"基于页数要求({page_count}页)换算字数要求为{result['word_count']}字")
                except (ValueError, TypeError):
                    logger.warning(f"页数转换失败: {result['page_count']}")
                    
            logger.info(f"从用户提示中提取的要求: 层级={result['level']}, 字数={result['word_count']}")
            return result
            
        except Exception as e:
            logger.error(f"提取用户要求时出错: {str(e)}")
            # 出错时返回默认值
            return {"level": 2, "word_count": None}

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
            # 在保存前进行最终的大纲结构优化
            self._optimize_outline_structure(outline_data)
            
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
            
    def _optimize_outline_structure(self, outline_data: Dict[str, Any]) -> None:
        """
        优化大纲结构，确保层级合理，内容不重复
        
        Args:
            outline_data: 大纲数据
        """
        logger.info("开始优化大纲结构")
        
        # 检查一级段落数量，如果太多可能需要合并
        sub_paragraphs = outline_data.get("sub_paragraphs", [])
        if len(sub_paragraphs) > 10:
            logger.warning(f"一级段落数量过多 ({len(sub_paragraphs)}个)，考虑合并相似段落")
            
            # 这里可以实现合并逻辑，但需要复杂的相似度计算
            # 简单起见，我们只记录警告，不实际合并
        
        # 确保每个段落都有描述
        def ensure_descriptions(paragraphs):
            for para in paragraphs:
                children = para.get("children", [])
                
                # 如果段落有子标题，将描述设为空字符串
                if children and len(children) > 0:
                    para["description"] = ""
                # 如果没有子标题且没有描述，添加一个基于标题的简单描述
                elif not para.get("description"):
                    para["description"] = f"关于{para.get('title', '此主题')}的详细内容"
                
                # 递归处理子段落
                if children:
                    ensure_descriptions(children)
        
        # 确保所有段落都有描述
        ensure_descriptions(sub_paragraphs)
        
        # 检查层级深度，避免过深的层级结构
        def check_depth(paragraphs, current_depth=1, max_depth=4):
            for para in paragraphs:
                children = para.get("children", [])
                
                # 如果层级太深，将子段落提升或合并
                if current_depth >= max_depth and children:
                    logger.warning(f"段落 '{para.get('title')}' 层级过深，考虑简化结构")
                    
                    # 简单处理：如果子段落太多，只保留前几个
                    if len(children) > 3:
                        logger.info(f"段落 '{para.get('title')}' 子段落过多，保留前3个")
                        para["children"] = children[:3]
                
                # 递归检查子段落
                if children:
                    check_depth(children, current_depth + 1, max_depth)
        
        # 检查层级深度
        check_depth(sub_paragraphs)
        
        # 确保段落标题不包含编号
        def clean_titles(paragraphs):
            for para in paragraphs:
                if "title" in para:
                    para["title"] = clean_numbering_from_title(para["title"])
                
                # 递归处理子段落
                children = para.get("children", [])
                if children:
                    clean_titles(children)
        
        # 清理标题中的编号
        clean_titles(sub_paragraphs)
        
        logger.info("大纲结构优化完成")

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
            
            # 对根段落按照 sort_index 排序
            root_paragraphs.sort(key=lambda p: p.sort_index if p.sort_index is not None else p.id)
            
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
                    
                    # 添加描述（如果有且没有子标题）
                    if p.description: 
                        # 将描述用括号括起来，避免层级结构歧义
                        result.append(f"({p.description})")
                    
                    # 递归处理子段落
                    if hasattr(p, 'children') and p.children:
                        # 确保子段落按 sort_index 排序
                        sorted_children = sorted(p.children, key=lambda x: x.sort_index if x.sort_index is not None else x.id)
                        result.extend(build_outline_text(sorted_children, level + 1))
                return result
            
            # 构建大纲文本
            outline_text = build_outline_text(root_paragraphs)
            outline_content += "\n".join(outline_text)
            
            logger.info(f"大纲内容构建完成 [outline_id={outline.id}, content_length={len(outline_content)}]")
            logger.info(f"{outline_content}")
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

    def generate_full_content(self, outline_id: str, db_session, user_id: Optional[str] = None, kb_ids: Optional[List[str]] = None, user_prompt: str = "", doc_id: str = None) -> Dict[str, Any]:
        """
        生成完整的文章内容
        
        Args:
            outline_id: 大纲ID
            db_session: 数据库会话
            user_id: 用户ID
            kb_ids: 知识库ID列表
            user_prompt: 用户提示
            doc_id: 文档ID
            
        Returns:
            Dict: 生成的内容
        """
        logger.info(f"开始生成完整内容 [outline_id={outline_id}]")
        
        # 获取任务ID用于更新任务进度
        task_id = None
        if doc_id:
            # 查找相关任务ID
            task = db_session.query(Task).filter(
                Task._params.like(f'%"doc_id": "{doc_id}"%'),
                Task.status == TaskStatus.PROCESSING
            ).first()
            if task:
                task_id = task.id
                logger.info(f"找到关联的任务ID: {task_id}")
                
        # 初始化任务进度
        update_task_progress(task_id, db_session, 5, "开始生成文章", f"大纲ID: {outline_id}, 用户ID: {user_id}")
        
        # 获取大纲
        outline = db_session.query(Outline).filter(Outline.id == outline_id).first()
        if not outline:
            raise ValueError(f"未找到ID为{outline_id}的大纲")
        
        update_task_progress(task_id, db_session, 8, "获取大纲信息", f"大纲标题: {outline.title}")
        
        # 获取大纲内容
        outline_content= self._build_outline_content(outline, outline.sub_paragraphs)
        
        # 获取所有段落
        all_paragraphs = db_session.query(SubParagraph).filter(
            SubParagraph.outline_id == outline_id
        ).all()
        
        # 构建段落字典
        paragraphs_dict = {p.id: p for p in all_paragraphs}
        
        # 构建父子关系
        for p in all_paragraphs:
            if hasattr(p, 'children'):
                continue  # 已经有children属性
            
            # 添加children属性
            p.children = [
                paragraphs_dict[child.id] 
                for child in all_paragraphs 
                if child.parent_id == p.id
            ]
        
        # 获取顶级段落
        root_paragraphs = [p for p in all_paragraphs if p.parent_id is None]
        
        # 按 sort_index 排序
        root_paragraphs.sort(key=lambda p: p.sort_index if p.sort_index is not None else p.id)
        
        update_task_progress(task_id, db_session, 10, "解析大纲结构", f"找到 {len(all_paragraphs)} 个段落，{len(root_paragraphs)} 个顶级段落")
        
        # 从用户提示中提取字数要求
        requirements = self._extract_required_level_from_prompt(user_prompt)
        word_count = requirements.get("word_count")
        
        # 如果用户指定了字数，则进行分配
        if word_count:
            update_task_progress(task_id, db_session, 11, "开始分配字数", f"用户要求总字数: {word_count}字")
            logger.info(f"从用户提示中提取到字数要求: {word_count}字，开始分配字数到大纲...")
            
            # 转换大纲和段落为JSON格式，以便使用_distribute_word_outline方法
            outline_data = {
                "title": outline.title,
                "sub_paragraphs": []
            }
            
            # 递归构建段落树
            def build_paragraph_tree(paragraphs):
                result = []
                for p in paragraphs:
                    para_data = {
                        "id": p.id,
                        "title": p.title,
                        "description": p.description,
                        "level": p.level,
                        "count_style": p.count_style.value if p.count_style else "medium"
                    }
                    
                    if hasattr(p, 'children') and p.children:
                        para_data["children"] = build_paragraph_tree(sorted(p.children, key=lambda x: x.sort_index if x.sort_index is not None else x.id))
                        
                    result.append(para_data)
                return result
            
            # 构建JSON格式的大纲数据
            outline_data["sub_paragraphs"] = build_paragraph_tree(root_paragraphs)
            
            # 分配字数
            self._distribute_word_outline(outline_data, word_count)
            
            # 将分配好的字数更新到段落中
            def update_word_counts(json_paragraphs, db_paragraphs_dict):
                for json_para in json_paragraphs:
                    if "id" in json_para and json_para["id"] in db_paragraphs_dict:
                        db_para = db_paragraphs_dict[json_para["id"]]
                        if "expected_word_count" in json_para:
                            db_para.expected_word_count = json_para["expected_word_count"]
                            logger.info(f"更新段落 '{db_para.title}' 的预期字数为 {db_para.expected_word_count} 字")
                    
                    # 递归处理子段落
                    if "children" in json_para and json_para["children"]:
                        update_word_counts(json_para["children"], db_paragraphs_dict)
            
            # 将字数分配结果更新到数据库中的段落
            update_word_counts(outline_data["sub_paragraphs"], paragraphs_dict)
            
            # 提交更改
            db_session.commit()
            update_task_progress(task_id, db_session, 12, "字数分配完成", f"已为 {len(all_paragraphs)} 个段落分配字数")
        
        # 获取RAG上下文
        rag_context = ""
        if kb_ids:
            logger.info(f"获取RAG上下文 [kb_ids={kb_ids}]")
            # 更新任务进度到12%，开始RAG检索
            
            # 新增：通过LLM生成相关问题
            question_generation_prompt = f"""
            深入理解<EOF>和</EOF>之间的原始需求，整理出5个问题，以便从RAG知识库中查询相关参考内容，仅输出问题：
            <EOF>
            {user_prompt}
            </EOF>
            """
            update_task_progress(task_id, db_session, 15 if word_count else 12, "开始RAG检索", f"使用知识库: {kb_ids}")
            
            logger.info("开始生成用于RAG查询的问题")
            try:
                # 调用LLM生成相关问题
                question_response = self.llm.invoke(question_generation_prompt)
                generated_questions = question_response.content.strip().split('\n')
                
                # 过滤掉可能包含的序号或空行
                filtered_questions = []
                for q in generated_questions:
                    # 移除序号如"1. ", "1）", "问题1："等
                    cleaned_q = re.sub(r'^[\d\.\)、：\s]+', '', q.strip())
                    cleaned_q = re.sub(r'^问题[\d\s]*[:：]?', '', cleaned_q)
                    if cleaned_q:
                        filtered_questions.append(cleaned_q)
                
                log_msg = f"生成了 {len(filtered_questions)} 个问题用于RAG查询: {filtered_questions}"
                logger.info(log_msg)
                update_task_progress(task_id, db_session, 15, "生成RAG查询问题", log_msg)
                
                # 依次从RAG中查询每个问题
                combined_rag_context = ""
                for i, question in enumerate(filtered_questions):
                    progress = 15 + int((i / len(filtered_questions)) * 10)
                    logger.info(f"开始查询问题 {i+1}/{len(filtered_questions)}: {question}")
                    update_task_progress(task_id, db_session, progress, f"RAG查询问题 {i+1}/{len(filtered_questions)}", f"问题: {question}")
                    
                    # 查询RAG获取上下文
                    question_context = self._get_rag_context(
                        question=question,
                        user_id=user_id,
                        kb_ids=kb_ids,
                        context_msg=f"查询问题 {i+1}: {question}"
                    )
                    
                    # 如果查询结果不为空，添加到组合上下文中
                    if question_context.strip():
                        combined_rag_context += f"\n--- 问题 {i+1}: {question} ---\n{question_context}\n\n"
                        update_task_progress(task_id, db_session, progress, f"获取问题 {i+1} RAG结果", f"获取到上下文长度: {len(question_context)} 字符")
                    else:
                        update_task_progress(task_id, db_session, progress, f"获取问题 {i+1} RAG结果", "未获取到相关上下文")
                
                # 使用组合的RAG上下文
                if combined_rag_context.strip():
                    rag_context = combined_rag_context
                    rag_log = f"已组合多个问题的RAG上下文，总长度: {len(rag_context)} 字符"
                    logger.info(rag_log)
                    update_task_progress(task_id, db_session, 25, "RAG检索完成", rag_log)
                else:
                    # 如果所有问题都没有返回结果，使用默认方式查询
                    logger.warning("所有生成的问题查询结果为空，使用默认方式查询RAG")
                    update_task_progress(task_id, db_session, 25, "使用默认方式查询RAG", "生成的问题查询结果为空")
                    rag_context = self._get_rag_context(
                        question=f"生成关于{outline.title}的文章",
                        user_id=user_id,
                        kb_ids=kb_ids,
                        context_msg=user_prompt
                    )
                    update_task_progress(task_id, db_session, 27, "默认RAG查询完成", f"获取上下文长度: {len(rag_context)} 字符")

                # 新增：通过百度搜索获取更多信息
                if self.use_web:
                    update_task_progress(task_id, db_session, 28, "开始Web搜索", "通过百度搜索补充信息")
                    web_search_results = []
                    for i, question in enumerate(filtered_questions[:2]):  # 只对前两个问题进行搜索
                        logger.info(f"开始通过百度搜索获取问题相关信息: {question}")
                        update_task_progress(task_id, db_session, 29, f"搜索问题 {i+1}", f"问题: {question}")
                        
                        search_results = baidu_search(question)
                        if search_results:
                            search_summary = self._summarize_search_results(question, search_results)
                            rag_context += f"\n--- 百度搜索结果: {question} ---\n{search_summary}\n\n"
                            web_search_results.append(f"问题 {i+1}: {len(search_summary)} 字符")
                            logger.info(f"已将搜索结果添加到RAG上下文中")
                    
                    if web_search_results:
                        update_task_progress(task_id, db_session, 30, "Web搜索完成", f"获取搜索结果: {', '.join(web_search_results)}")
            except Exception as e:
                error_msg = f"生成问题或查询RAG时出错: {str(e)}"
                logger.error(error_msg)
                update_task_progress(task_id, db_session, 30, "RAG查询过程出错", error_msg)
                # 出错时使用默认方式查询
                rag_context = self._get_rag_context(
                    question=f"生成关于{outline.title}的文章",
                    user_id=user_id,
                    kb_ids=kb_ids,
                    context_msg=user_prompt
                )
                update_task_progress(task_id, db_session, 32, "使用替代方式完成RAG查询", f"获取上下文长度: {len(rag_context)} 字符")
            
            logger.info(f"RAG上下文长度: {len(rag_context)} 字符")
        else:
            # 没有RAG检索
            update_task_progress(task_id, db_session, 30, "准备生成内容", "不使用RAG检索")
        
        # 生成文章标题
        # article_title = self._generate_article_title(
        #     user_prompt=user_prompt,
        #     outline_title=outline.title,
        #     outline_content=outline_content
        # )
        article_title = outline.title
        logger.info(f"生成文章标题: {article_title}")
        
        # 更新任务进度到35%，标题生成完毕
        update_task_progress(task_id, db_session, 35, "标题生成完毕", f"文章标题: {article_title}")
        
        # 存储生成的内容
        markdown_content = []
        
        # 添加文章标题
        markdown_content.append(f"# {article_title}\n")
        
        # 更新文档标题和初始HTML（如果提供了文档ID）
        if doc_id:
            try:
                document = db_session.query(Document).filter(Document.doc_id == doc_id).first()
                if document:
                    document.title = article_title
                    initial_html = markdown.markdown(f"# {article_title}\n\n*文档生成中...*")
                    document.content = initial_html
                    db_session.commit()
                    logger.info(f"更新文档标题和初始HTML [doc_id={doc_id}]")
            except Exception as e:
                logger.error(f"更新文档标题时出错: {str(e)}")
        
        # 初始化全局上下文对象，用于在段落间传递信息
        global_context = {
            "previous_content_summary": "",  # 前一段落的内容摘要
            "chapter_summaries": {},  # 已生成章节的摘要，格式为 {章节标题: 摘要内容}
            "generated_contents": {},  # 已生成段落的内容，格式为 {段落ID: {title: 标题, content: 内容}}
            "total_content_length": len(f"# {article_title}\n"),  # 当前已生成内容的总长度
            "max_total_length": 200000,  # 内容总长度限制
            "max_chapter_length": 10000,  # 单个章节长度限制
            "duplicate_titles": set(),  # 记录重复的标题
            "generated_titles": set(),  # 记录已生成的标题
            "doc_id": doc_id,  # 文档ID，用于更新HTML内容
            "task_id": task_id,  # 任务ID，用于更新进度
            "total_paragraphs": len(all_paragraphs),  # 段落总数
            "generated_paragraph_count": 0  # 已生成段落数
        }
        
        logger.info(f"开始生成段落内容，共 {len(root_paragraphs)} 个顶级段落")
        update_task_progress(task_id, db_session, 40, "开始生成段落内容", f"共 {len(root_paragraphs)} 个顶级段落, {len(all_paragraphs)} 个总段落")
        
        # 顺序生成每个顶级段落的内容
        for i, paragraph in enumerate(root_paragraphs):
            logger.info(f"处理顶级段落 [{i+1}/{len(root_paragraphs)}] [ID={paragraph.id}, 标题='{paragraph.title}']")
            
            # 检查总内容长度是否超过限制
            if global_context["total_content_length"] >= global_context["max_total_length"]:
                logger.warning(f"内容总长度已达到限制({global_context['total_content_length']}字符)，停止生成")
                break
            
            # 生成段落内容
            self._generate_paragraph_with_context(
                paragraph,
                global_context,
                markdown_content,
                article_title,
                rag_context,
                outline_content,
                user_prompt,
                is_root=True,
                parent_content="",
                chapter_index=i,
                total_chapters=len(root_paragraphs),
                db_session=db_session
            )
            
            # 计算并更新当前进度
            # 进度范围从40%到95%，留5%给最后的处理
            progress = 40 + int((global_context["generated_paragraph_count"] / global_context["total_paragraphs"]) * 55)
            progress = min(95, progress)  # 确保不超过95%，留给最后的完成步骤
            update_task_progress(task_id, db_session, progress, f"已生成 {global_context['generated_paragraph_count']}/{global_context['total_paragraphs']} 个段落", 
                                f"生成段落ID: {paragraph.id}, 标题: {paragraph.title}, 当前总内容长度: {global_context['total_content_length']} 字符")
        
        # 合并所有内容
        final_content = "\n".join(markdown_content)
        
        # 记录生成的内容长度
        logger.info(f"生成内容完成，总长度: {len(final_content)} 字符")
        
        # 记录重复标题情况
        duplicate_log = ""
        if global_context["duplicate_titles"]:
            duplicate_log = f"检测到 {len(global_context['duplicate_titles'])} 个重复标题: {', '.join(global_context['duplicate_titles'])}"
            logger.warning(duplicate_log)
        
        # 记录章节摘要数量
        summary_log = f"生成了 {len(global_context['chapter_summaries'])} 个章节摘要, {len(global_context['generated_contents'])} 个段落内容, 总长度: {len(final_content)} 字符"
        logger.info(summary_log)
        
        # 将markdown转换为HTML
        html_content = markdown.markdown(final_content)
        
        # 更新文档HTML内容
        html_log = ""
        if doc_id:
            try:
                document = db_session.query(Document).filter(Document.doc_id == doc_id).first()
                if document:
                    document.content = html_content
                    db_session.commit()
                    html_log = f"更新文档最终完整HTML内容 [doc_id={doc_id}]"
                    logger.info(html_log)
            except Exception as e:
                html_log = f"更新文档最终HTML内容时出错: {str(e)}"
                logger.error(html_log)
        
        # 最终进度100%
        final_log = f"{summary_log}\n{duplicate_log}\n{html_log}".strip()
        update_task_progress(task_id, db_session, 100, "内容生成完成", final_log)
        
        # 如果优化失败，返回原始内容
        # 这里不需要再次转换HTML，因为已经在上面转换过了
        # html_content = markdown.markdown(final_content)
        
        # 更新最终完整的文档HTML内容 - 这部分代码是重复的，可以删除
        # if doc_id:
        #     try:
        #         document = db_session.query(Document).filter(Document.doc_id == doc_id).first()
        #         if document:
        #             document.content = html_content
        #             db_session.commit()
        #             logger.info(f"更新文档最终完整HTML内容 [doc_id={doc_id}]")
        #     except Exception as e:
        #         logger.error(f"更新文档最终HTML内容时出错: {str(e)}")
        
        return {
            "title": article_title,
            "markdown": final_content,
            "html": html_content
        }
    
    def _summarize_search_results(self, question: str, search_results: str) -> str:
        """
        总结百度搜索结果
        
        Args:
            search_results: 百度搜索返回的结果
            
        Returns:
            str: 总结后的搜索结果
        """
        logger.info("开始总结搜索结果")
        
        # 创建总结提示
        summary_prompt = f"""
        请理解问题，根据参考资料进行总结：
        问题：{question}

        参考资料：
        {search_results}

        请直接输出总结，不要包含其他内容。
        """
        
        try:
            # 调用LLM生成总结
            summary_result = self.llm.invoke(summary_prompt)
            summary_content = summary_result.content.strip()
            
            logger.info("搜索结果总结完成")
            return summary_content
        except Exception as e:
            logger.error(f"总结搜索结果时出错: {str(e)}")
            return "搜索结果总结失败。"

    def _generate_paragraph_with_context(
        self,
        paragraph,
        global_context,
        markdown_content,
        article_title,
        rag_context,
        outline_content,
        user_prompt,
        is_root=False,
        parent_content="",
        chapter_index=0,
        total_chapters=1,
        db_session=None
    ):
        """
        生成段落内容，并递归生成子段落内容
        
        Args:
            paragraph: 段落对象
            global_context: 全局上下文对象，用于在段落间传递信息
            markdown_content: 已生成的markdown内容列表
            article_title: 文章标题
            rag_context: RAG上下文
            outline_content: 大纲内容
            user_prompt: 用户提示
            is_root: 是否为顶级段落
            parent_content: 父段落内容
            chapter_index: 章节索引
            total_chapters: 总章节数
            db_session: 数据库会话，用于更新文档
        """
        # 检查是否已经生成过该段落内容
        if paragraph.id in global_context["generated_contents"]:
            logger.warning(f"段落 '{paragraph.title}' (ID={paragraph.id}) 已经生成过内容，跳过")
            return
            
        # 获取段落标题
        title = paragraph.title
        
        # 检查标题是否已经存在于已生成的内容中
        if title in global_context.get("generated_titles", set()):
            logger.warning(f"检测到重复标题: '{title}'，添加唯一标识符")
            # 为重复标题添加唯一标识符
            # 确保paragraph.id是字符串类型
            paragraph_id_str = str(paragraph.id)
            # 安全地获取ID的最后4个字符
            unique_suffix = paragraph_id_str[-4:] if len(paragraph_id_str) >= 4 else paragraph_id_str
            title = f"{title} ({unique_suffix})"
            global_context["duplicate_titles"].add(paragraph.title)
        else:
            # 记录已生成的标题
            if "generated_titles" not in global_context:
                global_context["generated_titles"] = set()
            global_context["generated_titles"].add(title)
        
        # 获取段落级别
        level = paragraph.level
        
        # 获取段落描述
        description = paragraph.description or ""
        
        # 获取子段落标题
        sub_titles = get_sub_paragraph_titles(paragraph)
        
        # 获取计数风格
        count_style = paragraph.count_style or "medium"
        
        # 构建上下文信息
        context_info = {
            "previous_content_summary": global_context["previous_content_summary"],
            "chapter_summaries": global_context["chapter_summaries"],
            "chapter_position": {
                "index": chapter_index,
                "total": total_chapters,
                "level": level
            },
            "parent_content": parent_content,
            "already_generated_titles": list(global_context.get("generated_titles", set())),
            "duplicate_warning": "请确保生成的内容与已生成的章节不重复，特别是避免与以下章节内容重复: " + 
                               ", ".join([f"'{title}'" for title in list(global_context.get("generated_titles", set()))[-5:]])
        }
        
        # 计算当前段落的最大长度
        max_length = global_context["max_chapter_length"]
        if level == 1:
            # 一级标题段落长度可以更长
            max_length = min(global_context["max_chapter_length"] * 1.5, 7500)
        elif level == 2:
            # 二级标题段落长度适中
            max_length = min(global_context["max_chapter_length"], 5000)
        else:
            # 更深层级的段落长度更短
            max_length = min(global_context["max_chapter_length"] * 0.7, 3500)
        
        # 检查总内容长度是否超过限制
        if global_context["total_content_length"] >= global_context["max_total_length"]:
            logger.warning(f"内容总长度已达到限制({global_context['total_content_length']}字符)，停止生成")
            return
        
        # 生成段落内容
        logger.info(f"生成段落内容 [标题='{title}', 级别={level}, ID={paragraph.id}]")

        if description:
            content = self._generate_paragraph_content_with_context(
                article_title=article_title,
                paragraph=paragraph,
                sub_titles=sub_titles,
                count_style=count_style,
                rag_context=rag_context,
                outline_content=outline_content,
                user_prompt=user_prompt,
                context_info=context_info,
                max_length=max_length
            )
            
            # 检查生成的内容与已有内容的相似度
            content_too_similar = False
            similar_content = None
            similar_title = None
            
            for pid, content_info in global_context["generated_contents"].items():
                if pid != paragraph.id:  # 不与自己比较
                    existing_content = content_info.get("content", "")
                    existing_title = content_info.get("title", "")
                    
                    # 计算内容相似度
                    similarity = self._paragraph_similarity(content, existing_content)
                    
                    if similarity > 0.7:  # 相似度阈值
                        content_too_similar = True
                        similar_content = existing_content
                        similar_title = existing_title
                        logger.warning(f"生成的内容与已有内容 '{existing_title}' 相似度过高 ({similarity:.2f})，尝试重新生成")
                        break
            
            # 如果内容相似度过高，尝试重新生成
            if content_too_similar and similar_title:
                # 更新上下文，明确指出需要避免与哪个章节重复
                context_info["duplicate_warning"] = f"请确保生成的内容与已生成的章节不重复，特别是避免与 '{similar_title}' 章节内容重复。生成的内容必须是独特的，不能包含与其他章节相同的段落或观点。"
                
                # 重新生成内容
                logger.info(f"重新生成段落内容 [标题='{title}', 级别={level}, ID={paragraph.id}]")
                content = self._generate_paragraph_content_with_context(
                    article_title=article_title,
                    paragraph=paragraph,
                    sub_titles=sub_titles,
                    count_style=count_style,
                    rag_context=rag_context,
                    outline_content=outline_content,
                    user_prompt=user_prompt,
                    context_info=context_info,
                    max_length=max_length
                )

        else:
            content = ""
            
        # 提取内容摘要
        content_summary = self._extract_content_summary(content)
        
        # 更新全局上下文
        global_context["previous_content_summary"] = content_summary
        global_context["chapter_summaries"][title] = content_summary
        global_context["generated_contents"][paragraph.id] = {
            "title": title,
            "content": content,
            "summary": content_summary
        }
        
        # 增加已生成段落计数
        global_context["generated_paragraph_count"] += 1
        
        # 更新总内容长度
        global_context["total_content_length"] += len(content) + 100  # 100是标题和额外格式的估计长度
        
        # 根据段落级别添加标题，一级标题使用##，二级标题使用###，依此类推
        header = "#" * (level + 1)  # 增加一个#，使一级标题变为##
        markdown_content.append(f"{header} {title}\n\n{content}\n")
        
        # 更新文档的HTML内容（如果提供了文档ID）
        doc_id = global_context.get("doc_id")
        if doc_id and db_session:
            try:
                # 合并到目前为止生成的内容
                current_content = "\n".join(markdown_content)
                current_html = markdown.markdown(current_content)
                
                # 更新文档HTML内容
                document = db_session.query(Document).filter(Document.doc_id == doc_id).first()
                if document:
                    document.content = current_html
                    db_session.commit()
                    logger.info(f"更新文档HTML内容 [doc_id={doc_id}, 段落='{title}']")
            except Exception as e:
                logger.error(f"更新文档HTML内容时出错: {str(e)}")
        
        # 递归处理子段落
        if hasattr(paragraph, 'children') and paragraph.children:
            children = sorted(paragraph.children, key=lambda p: p.sort_index if p.sort_index is not None else p.id)
            for child in children:
                # 递归生成子段落
                self._generate_paragraph_with_context(
                    child,
                    global_context,
                    markdown_content,
                    article_title,
                    rag_context,
                    outline_content,
                    user_prompt,
                    is_root=False,
                    parent_content=content,
                    db_session=db_session
                )

    def _generate_paragraph_content_with_context(
        self, 
        article_title: str, 
        paragraph: SubParagraph, 
        sub_titles: List[str], 
        count_style: str, 
        rag_context: str = "", 
        outline_content: str = "", 
        user_prompt: str = "",
        context_info: dict = {},
        max_length: int = 3000
    ) -> str:
        """生成段落内容，包含上下文信息"""
        # 记录开始生成段落内容
        logger.info(f"开始生成段落内容 [段落ID={paragraph.id}, 标题='{paragraph.title}', 字数范围={count_style}]")
        
        # 根据count_style确定字数范围
        word_count_range = {
            "short": "300-500",
            "medium": "500-1000",
            "long": "1000-1500"
        }.get(count_style, "500-1000")
        
        # 清理标题中的编号
        clean_title = clean_numbering_from_title(paragraph.title)
        
        # 格式化子主题列表
        sub_topics = "\n".join([f"  - {clean_numbering_from_title(title)}" for title in sub_titles])
        logger.info(f"段落包含 {len(sub_titles)} 个子主题")
        
        # 获取段落描述
        description = paragraph.description or ""
        
        # 获取段落级别
        level = paragraph.level
        
        # 获取章节位置信息
        chapter_position = context_info.get("chapter_position", {})
        chapter_index = chapter_position.get("index", 0)
        total_chapters = chapter_position.get("total", 1)
        
        # 获取父段落内容
        parent_content = context_info.get("parent_content", "")
        
        # 获取已生成章节的摘要
        chapter_summaries = context_info.get("chapter_summaries", {})
        
        # 获取前一段落的内容摘要
        previous_content_summary = context_info.get("previous_content_summary", "")
        
        # 获取已生成的标题列表
        already_generated_titles = context_info.get("already_generated_titles", [])
        
        # 获取重复警告
        duplicate_warning = context_info.get("duplicate_warning", "")
        
        # 构建章节摘要字符串
        chapter_summaries_str = ""
        if chapter_summaries:
            chapter_summaries_str = "已生成的章节摘要：\n"
            for ch_title, ch_summary in list(chapter_summaries.items())[-5:]:  # 只取最近5个章节
                chapter_summaries_str += f"- {ch_title}: {ch_summary}\n"
        
        # 构建已生成标题字符串
        already_generated_titles_str = ""
        if already_generated_titles:
            already_generated_titles_str = "已生成的章节标题：" + ", ".join(already_generated_titles[-10:])  # 只取最近10个标题
        
        # 构建章节位置字符串
        chapter_position_str = ""
        if level == 1:
            chapter_position_str = f"这是第{chapter_index + 1}章，共{total_chapters}章。"
        elif level == 2:
            # 使用章节索引和段落ID生成节号
            paragraph_id_str = str(paragraph.id)
            section_num = f"{chapter_index + 1}.{paragraph_id_str[-2:]}" if len(paragraph_id_str) >= 2 else f"{chapter_index + 1}.1"
            chapter_position_str = f"这是{section_num}节。"
        elif level == 3:
            # 使用章节索引和段落ID生成小节号
            paragraph_id_str = str(paragraph.id)
            section_num = f"{chapter_index + 1}.{paragraph_id_str[-2:]}" if len(paragraph_id_str) >= 2 else f"{chapter_index + 1}.1"
            subsection_num = paragraph_id_str[-1] if len(paragraph_id_str) >= 1 else "1"
            chapter_position_str = f"这是{section_num}.{subsection_num}小节。"
        
        # 构建提示模板
        template = f"""
# 角色
你是一位专业的公文撰写精灵，擅长撰写各类公文，能够根据提供的详细信息，生成符合要求的公文段落内容。

## 技能
### 技能 1: 生成公文段落
1. 根据接收到的【文章标题】【当前段落标题】【段落描述】【段落级别】【字数范围】【章节位置】【父段落内容】【前一段落摘要】【子主题列表】【用户需求】等信息，生成该段落的详细内容。
2. 生成的内容要紧扣段落标题和描述，与文章整体主题保持一致，与父段落内容保持连贯，不重复已生成章节的内容，涵盖子主题（如果有），长度控制在指定字数范围左右，内容专业、准确、有深度。
3. 直接输出段落内容，不要包含标题、解释或标记，也不要使用"本章""本节"等指代词，直接陈述内容。

## 限制:
- 只生成与公文撰写相关的内容，拒绝回答与公文无关的话题。
- 所输出的内容必须符合技能 1 中规定的要求，不能偏离框架要求。
- 生成的是正式的公文，不要使用"我们"这种口语表达的句式。
- 内容后面不要进行总结，避免出现"总之""总而言之"这样的总结性概括。
- 重要：只生成简单的段落文本，不要使用任何标题格式（如一、二、三或1.1、1.2等）。即使段落标题暗示这可能是一个规划或大纲，也只生成普通段落，而非含有多级标题的完整文档结构。
- 重要：不要在生成的内容中包含任何目录、标题编号或分级结构。生成的内容应该是连贯的段落文本，而不是多级结构的文档。
- 重要：即使是对于规划、方案等文档类型，也只生成该段落应有的内容部分，不要生成整个规划的完整结构和全部内容。

【文章标题】
{article_title}

【当前段落标题】
{clean_title}

【段落描述】
{description}

【段落级别】
{level}级标题

【字数范围】
{word_count_range}字

【章节位置】
{chapter_position_str}

【父段落内容】
{parent_content}

【前一段落摘要】
{previous_content_summary}

{chapter_summaries_str}

{already_generated_titles_str}

{duplicate_warning}

【子主题列表】
{sub_topics}

【参考资料】
{rag_context}

【用户需求】
{user_prompt}

【特别说明】
此处需要生成的是"当前段落标题"下的连贯文本内容，不要再重复或包含当前段落的标题。
不要生成包含多级标题（如一、二、三或1.1、1.2等）的完整文档结构。
例如，如果标题是"越西县智慧交通科技治超建设规划"，不要生成一个包含"一、建设背景"、"二、现状与需求"等结构的完整规划文档，而是只生成关于这个规划的单个段落描述。
"""
        
        try:
            # 直接调用LLM，不使用ChatPromptTemplate
            logger.info(f"开始调用LLM生成段落内容 [段落ID={paragraph.id}]")
            result = self.llm.invoke(template)
            
            # 获取生成的内容
            content = result.content

            # 替换特定短语
            replacements = {
                "我们将": "",
                "我们": "",
                "总之，": "",
                "总而言之，": "",
                "综上所述，": ""
            }
            
            for old, new in replacements.items():
                content = content.replace(old, new)
            
            # 检查并删除内容中的标题结构（如一、二、三或1.1、1.2等）
            title_patterns = [
                r'^[一二三四五六七八九十]+、.*?[\r\n]',  # 匹配中文数字标题，如"一、建设背景"
                r'^（[一二三四五六七八九十]+）.*?[\r\n]',  # 匹配中文数字标题，如"（一）建设背景"
                r'^\d+\..*?[\r\n]',  # 匹配数字标题，如"1. 建设背景"
                r'^\d+\.\d+.*?[\r\n]',  # 匹配数字标题，如"1.1 建设背景"
                r'^\([\d]+\).*?[\r\n]'  # 匹配数字标题，如"(1) 建设背景"
            ]
            
            # 检查是否包含标题结构
            contains_titles = False
            for pattern in title_patterns:
                if re.search(pattern, content, re.MULTILINE):
                    contains_titles = True
                    break
            
            # 如果检测到标题结构，尝试重新生成或进行修复
            if contains_titles:
                logger.warning(f"检测到段落内容包含标题结构，进行修复 [段落ID={paragraph.id}]")
                
                # 修改提示模板，更明确地强调不要生成标题结构
                more_explicit_template = template + """
【警告】
检测到你可能会生成包含标题结构的内容。请记住：
1. 不要生成任何形式的标题（如一、二、三或1.1、1.2等）
2. 不要将内容分成多个部分或章节
3. 只生成连贯的段落文本
4. 不要包含任何标题、编号或分级结构

即使你认为这种类型的内容通常应该有标题结构，在这里也请只生成纯文本段落。
"""
                
                # 重新生成内容
                result = self.llm.invoke(more_explicit_template)
                content = result.content
                
                # 检查重新生成的内容是否仍包含标题结构
                still_contains_titles = False
                for pattern in title_patterns:
                    if re.search(pattern, content, re.MULTILINE):
                        still_contains_titles = True
                        break
                
                # 如果仍然包含标题结构，进行强制清理
                if still_contains_titles:
                    logger.warning(f"重新生成的内容仍包含标题结构，进行强制清理 [段落ID={paragraph.id}]")
                    
                    # 移除所有标题行
                    for pattern in title_patterns:
                        content = re.sub(pattern, '', content, flags=re.MULTILINE)
                    
                    # 重新清理不必要的空行
                    content = re.sub(r'\n{3,}', '\n\n', content)
                    content = content.strip()
            
            # 记录生成完成
            logger.info(f"段落内容生成完成 [段落ID={paragraph.id}, 内容长度={len(content)}字符]")
            
            # 限制内容长度
            if len(content) > max_length:
                logger.warning(f"生成的内容超过最大长度限制，进行截断 [原长度={len(content)}, 最大长度={max_length}]")
                content = content[:max_length]
            
            return content
            
        except Exception as e:
            logger.error(f"生成段落内容时出错 [段落ID={paragraph.id}]: {str(e)}")
            # 出错时返回简短内容
            return f"内容生成失败: {str(e)}"

    def _calculate_title_retention(self, original_titles, optimized_titles=None):
        """
        计算标题保留率
        
        Args:
            original_titles: 原始标题列表
            optimized_titles: 优化后的标题列表，如果为None则计算原始标题中的唯一标题比例
            
        Returns:
            float: 标题保留率（0-1之间）
        """
        if not original_titles:
            return 1.0
            
        if optimized_titles is None:
            # 计算原始标题中的唯一标题比例
            unique_titles = set(original_titles)
            return len(unique_titles) / len(original_titles)
        else:
            # 计算优化后保留的原始标题比例
            retained_count = 0
            for title in original_titles:
                # 使用相似度比较，而不是精确匹配
                if any(self._title_similarity(title, opt_title) > 0.8 for opt_title in optimized_titles):
                    retained_count += 1
            
            return retained_count / len(original_titles)
            
    def _title_similarity(self, title1, title2):
        """
        计算两个标题的相似度
        
        Args:
            title1: 第一个标题
            title2: 第二个标题
            
        Returns:
            float: 相似度（0-1之间）
        """
        # 清理标题
        title1 = clean_numbering_from_title(title1).lower()
        title2 = clean_numbering_from_title(title2).lower()
        
        # 如果标题完全相同
        if title1 == title2:
            return 1.0
            
        # 如果一个标题包含另一个标题
        if title1 in title2 or title2 in title1:
            return 0.9
            
        # 计算词集合的Jaccard相似度
        words1 = set(title1.split())
        words2 = set(title2.split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
            
    def _calculate_repetition_score(self, content):
        """
        计算内容的重复度分数
        
        Args:
            content: 文档内容
            
        Returns:
            float: 重复度分数（0-1之间，越高表示重复度越高）
        """
        # 将内容分割成段落
        paragraphs = [p for p in content.split('\n\n') if p.strip() and not p.strip().startswith('#')]
        
        if len(paragraphs) <= 1:
            return 0.0
            
        # 计算段落间的相似度
        similarity_sum = 0
        comparison_count = 0
        
        # 限制比较的段落数，避免计算量过大
        max_paragraphs = min(len(paragraphs), 20)
        sample_paragraphs = paragraphs[:max_paragraphs]
        
        for i in range(len(sample_paragraphs)):
            for j in range(i+1, len(sample_paragraphs)):
                similarity = self._paragraph_similarity(sample_paragraphs[i], sample_paragraphs[j])
                similarity_sum += similarity
                comparison_count += 1
                
        if comparison_count == 0:
            return 0.0
            
        # 返回平均相似度作为重复度分数
        return similarity_sum / comparison_count
        
    def _paragraph_similarity(self, para1, para2):
        """
        计算两个段落之间的相似度
        
        Args:
            para1: 第一个段落
            para2: 第二个段落
            
        Returns:
            float: 相似度分数，范围0-1
        """
        # 如果段落太短，不计算相似度
        if len(para1) < 50 or len(para2) < 50:
            return 0.0
            
        # 将段落分成句子
        sentences1 = re.split(r'[。！？.!?]', para1)
        sentences2 = re.split(r'[。！？.!?]', para2)
        
        # 过滤空句子
        sentences1 = [s.strip() for s in sentences1 if s.strip()]
        sentences2 = [s.strip() for s in sentences2 if s.strip()]
        
        # 如果没有有效句子，返回0
        if not sentences1 or not sentences2:
            return 0.0
        
        # 计算句子间的相似度
        similarity_scores = []
        for s1 in sentences1:
            for s2 in sentences2:
                if len(s1) > 10 and len(s2) > 10:  # 只比较长度足够的句子
                    similarity_scores.append(self._sentence_similarity(s1, s2))
        
        # 如果没有有效的相似度分数，返回0
        if not similarity_scores:
            return 0.0
            
        # 返回最高的相似度分数
        return max(similarity_scores)

    def _sentence_similarity(self, s1, s2):
        """
        计算两个句子的相似度
        
        Args:
            s1: 第一个句子
            s2: 第二个句子
            
        Returns:
            float: 相似度（0-1之间）
        """
        # 如果句子完全相同
        if s1 == s2:
            return 1.0
            
        # 如果一个句子包含另一个句子
        if s1 in s2 or s2 in s1:
            return 0.9
            
        # 计算词集合的Jaccard相似度
        words1 = set(s1.split())
        words2 = set(s2.split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)

    def _extract_content_summary(self, content: str, max_length: int = 500) -> str:
        """
        从段落内容中提取摘要，用于下一个段落的上下文
        
        Args:
            content: 段落内容
            max_length: 摘要最大长度
            
        Returns:
            str: 内容摘要
        """
        # 如果内容较短，直接返回
        if len(content) <= max_length:
            return content
            
        # 简单的摘要提取：取前半部分和后半部分
        first_part = content[:max_length//2]
        last_part = content[-max_length//2:]
        
        return f"{first_part}...\n[中间内容省略]...\n{last_part}"

    def _full_content_optimize(self, user_prompt: str, final_content: str) -> str:
        """
        优化全文内容，处理可能的重复标题和内容
        
        Args:
            user_prompt: 用户提示
            final_content: 生成的全文内容
            
        Returns:
            str: 优化后的内容
        """
        logger.info("开始分析文档结构和内容...")
        
        # 提取文档中的标题及其结构
        title_pattern = re.compile(r'^(#+)\s+(.+)$', re.MULTILINE)
        titles = [(len(match.group(1)), match.group(2)) for match in title_pattern.finditer(final_content)]
        
        # 分析文档结构，查找重复标题
        title_counts = {}
        duplicate_titles = []
        
        for level, title in titles:
            title_counts[title] = title_counts.get(title, 0) + 1
            if title_counts[title] > 1:
                duplicate_titles.append(title)
        
        if duplicate_titles:
            logger.warning(f"发现重复标题: {duplicate_titles}")
        
        # 提取文档中的重要术语（引号中的内容和专有名词）
        term_pattern = re.compile(r'[""「」\'](.*?)[\""「」\']|[A-Z][a-z]*(?:\s+[A-Z][a-z]*)*')
        terms = [match.group(0) for match in term_pattern.finditer(final_content)]
        # 去重并限制数量
        important_terms = list(set(terms))[:20]
        
        # 计算标题保留率
        title_retention = self._calculate_title_retention(
            [title for _, title in titles]
        )
        
        # 计算内容重复度
        repetition_score = self._calculate_repetition_score(final_content)
        
        # 根据重复度评分给出描述
        if repetition_score < 0.1:
            repetition_description = "内容重复度较低，整体内容质量良好"
        elif repetition_score < 0.2:
            repetition_description = "存在一定程度的内容重复，需要适当优化"
        else:
            repetition_description = "内容重复度较高，需要大幅优化减少重复内容"
        
        # 分析段落相似度，找出高度相似的段落
        paragraphs = re.split(r'\n\n+', final_content)
        similar_paragraphs = []
        
        for i in range(len(paragraphs)):
            for j in range(i+1, len(paragraphs)):
                if len(paragraphs[i]) > 50 and len(paragraphs[j]) > 50:  # 只比较较长的段落
                    similarity = self._paragraph_similarity(paragraphs[i], paragraphs[j])
                    if similarity > 0.7:  # 相似度阈值
                        similar_paragraphs.append((i+1, j+1, similarity))
        
        # 构建优化提示
        optimization_prompt = f"""
请优化以下文档内容，使其更加连贯、一致，并消除重复内容。

用户需求: {user_prompt}

文档结构分析:
- 总标题数: {len(titles)}
- 标题保留率: {title_retention:.2f}
- {"存在重复标题: " + ", ".join(duplicate_titles) if duplicate_titles else "无重复标题"}

重要术语:
{", ".join(important_terms)}

内容重复度分析:
- 重复度评分: {repetition_score:.2f}
- {repetition_description}

{f"高度相似段落位置 (段落索引, 相似度): {similar_paragraphs}" if similar_paragraphs else "未发现高度相似的段落"}

优化要求:
1. 必须严格保持原有的文档结构和主要内容
2. 消除重复的内容，但不要过度精简
3. 确保各部分之间的逻辑连贯性
4. 保持专业术语的一致性
5. 优化段落之间的过渡
6. 确保内容完整，不遗漏重要信息
7. 每个章节的内容必须保持丰富，不要将任何章节精简为只有几句话
8. 后面章节的内容丰富度应与前面章节相当

【内容丰富度要求】
- 不要过度精简内容，每个章节都应保持足够的内容量
- 对于每个章节，至少保留原文80%的内容量
- 特别是后面的章节，不要因为前面已有类似内容就大幅精简
- 即使内容有些重复，也要确保每个章节都有足够的实质内容

【标题格式要求】
- 必须严格保持Markdown标题格式
- 只有文章总标题用一级标题，章节标题统一从二级标题开始
- 一级标题使用"# 标题"格式
- 二级标题使用"## 标题"格式
- 三级标题使用"### 标题"格式
- 四级标题使用"#### 标题"格式
- 标题与内容之间必须有空行
- 严格按照原文档的标题结构和层级，不要改变、删除或合并任何标题

以下是需要优化的文档内容:

{final_content}

请直接输出优化后的完整文档内容，使用Markdown格式，确保所有标题都保持正确的Markdown格式，并且每个章节都有足够丰富的内容。
"""
        
        # 调用语言模型进行优化
        logger.info("调用语言模型优化内容...")
        try:
            response = self.llm.invoke(optimization_prompt)
            optimized_content = response.content
            
            # 验证优化后的内容是否保留了标题格式
            original_title_count = len(re.findall(r'^#+\s+.+$', final_content, re.MULTILINE))
            optimized_title_count = len(re.findall(r'^#+\s+.+$', optimized_content, re.MULTILINE))
            
            # 检查内容长度，确保没有过度精简
            original_length = len(final_content)
            optimized_length = len(optimized_content)
            length_ratio = optimized_length / original_length if original_length > 0 else 0
            
            logger.info(f"内容长度比较: 原始={original_length}, 优化后={optimized_length}, 比例={length_ratio:.2f}")
            
            # 如果优化后的内容长度小于原始内容的70%，可能过度精简
            if length_ratio < 0.7:
                logger.warning(f"优化后的内容长度减少过多 [原始={original_length}, 优化后={optimized_length}, 比例={length_ratio:.2f}]")
                
                # 如果标题数量也减少，直接使用原始内容
                if optimized_title_count < original_title_count * 0.9:
                    logger.warning("优化后标题数量也减少，使用原始内容")
                    return final_content
                
                # 尝试重新优化，强调保持内容丰富度
                try:
                    # 构建更强调保持内容量的提示
                    retry_prompt = f"""
请重新优化以下文档内容，之前的优化过度精简了内容。

优化要求:
1. 必须保持原文档的所有内容要点，不要过度精简
2. 每个章节的内容量应至少保持原文的90%
3. 可以改善表达方式，但不要删除实质内容
4. 严格保持原有的标题结构和格式
5. 确保后面章节的内容与前面章节一样丰富

原始文档:
{final_content}

请输出优化后的完整文档，确保内容丰富度和完整性。
"""
                    logger.info("尝试重新优化，强调保持内容丰富度")
                    retry_response = self.llm.invoke(retry_prompt)
                    retry_content = retry_response.content
                    
                    # 检查重试后的内容长度
                    retry_length = len(retry_content)
                    retry_ratio = retry_length / original_length
                    retry_title_count = len(re.findall(r'^#+\s+.+$', retry_content, re.MULTILINE))
                    
                    logger.info(f"重试优化结果: 长度={retry_length}, 比例={retry_ratio:.2f}, 标题数={retry_title_count}")
                    
                    # 如果重试后的内容更接近原始长度，且标题数量合理，使用重试结果
                    if retry_ratio > length_ratio and retry_ratio > 0.8 and retry_title_count >= optimized_title_count:
                        logger.info("使用重试优化结果")
                        return retry_content
                    else:
                        logger.warning("重试优化效果不理想，使用原始内容")
                        return final_content
                        
                except Exception as e:
                    logger.error(f"重试优化失败: {str(e)}")
                    return final_content
            
            # 如果优化后的标题数量明显减少，可能丢失了标题格式
            if optimized_title_count < original_title_count * 0.8:
                logger.warning(f"优化后的标题数量减少过多 [原始={original_title_count}, 优化后={optimized_title_count}]，使用原始内容")
                # 如果优化后标题数量明显减少，可能是标题格式丢失，使用原始内容
                optimized_content = final_content
                logger.info("由于标题格式问题，使用原始未优化内容")
            
            logger.info("内容优化完成")
            return optimized_content
        except Exception as e:
            logger.error(f"内容优化失败: {str(e)}")
            # 如果优化失败，返回原始内容
            return final_content

    def generate_content_directly(self, prompt: str, file_contents: List[str], user_id: Optional[str] = None, kb_ids: Optional[List[str]] = None, doc_id: str = None) -> Dict[str, Any]:
        """
        直接生成文章内容，不需要先生成大纲
        
        Args:
            prompt: 用户提示
            file_contents: 参考文件内容
            user_id: 用户ID
            kb_ids: 知识库ID列表
            doc_id: 文档ID
            
        Returns:
            Dict: 生成的内容
        """
        start_time = time.time()
        logger.info(f"开始直接生成内容 [prompt={prompt}]")
        
        # 获取任务ID用于更新任务进度
        task_id = None
        if doc_id:
            # 查找相关任务ID
            from sqlalchemy.orm import Session
            from sqlalchemy.sql import func
            from app.database import get_db
            
            try:
                db_session = next(get_db())
                task = db_session.query(Task).filter(
                    Task._params.like(f'%"doc_id": "{doc_id}"%'),
                    Task.status == TaskStatus.PROCESSING
                ).first()
                if task:
                    task_id = task.id
                    logger.info(f"找到关联的任务ID: {task_id}")
            except Exception as e:
                logger.error(f"查找任务ID出错: {str(e)}")
                
        # 初始进度
        start_log = f"开始任务，提示词: '{prompt[:100]}{'...' if len(prompt) > 100 else ''}', 用户ID: {user_id}, 文档ID: {doc_id}"
        update_task_progress(task_id, db_session, 5, "准备生成文章", start_log)
        
        # 处理参考文件内容
        file_context = ""
        if file_contents and len(file_contents) > 0:
            file_log = f"处理 {len(file_contents)} 个参考文件，总长度: "
            file_context = "\n\n".join(file_contents)
            file_log += f"{len(file_context)} 字符"
            logger.info(f"参考文件内容长度: {len(file_context)} 字符")
            update_task_progress(task_id, db_session, 8, "处理参考文件", file_log)
        
        # 获取RAG上下文
        rag_context = ""
        if kb_ids:
            logger.info(f"获取RAG上下文 [kb_ids={kb_ids}]")
            # 更新任务进度到12%，开始RAG检索
            
            # 新增：通过LLM生成相关问题
            question_generation_prompt = f"""
            深入理解<EOF>和</EOF>之间的原始需求，整理出5个问题，以便从RAG知识库中查询相关参考内容，仅输出问题：
            <EOF>
            {prompt}
            </EOF>
            """
            update_task_progress(task_id, db_session, 12, "开始RAG检索", f"使用知识库: {kb_ids}")
            
            logger.info("开始生成用于RAG查询的问题")
            try:
                # 调用LLM生成相关问题
                question_response = self.llm.invoke(question_generation_prompt)
                generated_questions = question_response.content.strip().split('\n')
                
                # 过滤掉可能包含的序号或空行
                filtered_questions = []
                for q in generated_questions:
                    # 移除序号如"1. ", "1）", "问题1："等
                    cleaned_q = re.sub(r'^[\d\.\)、：\s]+', '', q.strip())
                    cleaned_q = re.sub(r'^问题[\d\s]*[:：]?', '', cleaned_q)
                    if cleaned_q:
                        filtered_questions.append(cleaned_q)
                
                log_msg = f"生成了 {len(filtered_questions)} 个问题用于RAG查询: {filtered_questions}"
                logger.info(log_msg)
                update_task_progress(task_id, db_session, 15, "生成RAG查询问题", log_msg)
                
                # 依次从RAG中查询每个问题
                combined_rag_context = ""
                for i, question in enumerate(filtered_questions):
                    progress = 15 + int((i / len(filtered_questions)) * 10)
                    logger.info(f"开始查询问题 {i+1}/{len(filtered_questions)}: {question}")
                    update_task_progress(task_id, db_session, progress, f"RAG查询问题 {i+1}/{len(filtered_questions)}", f"问题: {question}")
                    
                    # 查询RAG获取上下文
                    question_context = self._get_rag_context(
                        question=question,
                        user_id=user_id,
                        kb_ids=kb_ids,
                        context_msg=f"查询问题 {i+1}: {question}"
                    )
                    
                    # 如果查询结果不为空，添加到组合上下文中
                    if question_context.strip():
                        combined_rag_context += f"\n--- 问题 {i+1}: {question} ---\n{question_context}\n\n"
                        update_task_progress(task_id, db_session, progress, f"获取问题 {i+1} RAG结果", f"获取到上下文长度: {len(question_context)} 字符")
                    else:
                        update_task_progress(task_id, db_session, progress, f"获取问题 {i+1} RAG结果", "未获取到相关上下文")
                
                # 使用组合的RAG上下文
                if combined_rag_context.strip():
                    rag_context = combined_rag_context
                    rag_log = f"已组合多个问题的RAG上下文，总长度: {len(rag_context)} 字符"
                    logger.info(rag_log)
                    update_task_progress(task_id, db_session, 25, "RAG检索完成", rag_log)
                else:
                    # 如果所有问题都没有返回结果，使用默认方式查询
                    logger.warning("所有生成的问题查询结果为空，使用默认方式查询RAG")
                    update_task_progress(task_id, db_session, 25, "使用默认方式查询RAG", "生成的问题查询结果为空")
                    rag_context = self._get_rag_context(
                        question=f"生成关于{prompt}的文章",
                        user_id=user_id,
                        kb_ids=kb_ids,
                        context_msg=user_prompt
                    )
                    update_task_progress(task_id, db_session, 27, "默认RAG查询完成", f"获取上下文长度: {len(rag_context)} 字符")

                # 新增：通过百度搜索获取更多信息
                if self.use_web:
                    update_task_progress(task_id, db_session, 28, "开始Web搜索", "通过百度搜索补充信息")
                    web_search_results = []
                    for i, question in enumerate(filtered_questions[:2]):  # 只对前两个问题进行搜索
                        logger.info(f"开始通过百度搜索获取问题相关信息: {question}")
                        update_task_progress(task_id, db_session, 29, f"搜索问题 {i+1}", f"问题: {question}")
                        
                        search_results = baidu_search(question)
                        if search_results:
                            search_summary = self._summarize_search_results(question, search_results)
                            rag_context += f"\n--- 百度搜索结果: {question} ---\n{search_summary}\n\n"
                            web_search_results.append(f"问题 {i+1}: {len(search_summary)} 字符")
                            logger.info(f"已将搜索结果添加到RAG上下文中")
                    
                    if web_search_results:
                        update_task_progress(task_id, db_session, 30, "Web搜索完成", f"获取搜索结果: {', '.join(web_search_results)}")
            except Exception as e:
                error_msg = f"生成问题或查询RAG时出错: {str(e)}"
                logger.error(error_msg)
                update_task_progress(task_id, db_session, 30, "RAG查询过程出错", error_msg)
                # 出错时使用默认方式查询
                rag_context = self._get_rag_context(
                    question=f"生成关于{prompt}的文章",
                    user_id=user_id,
                    kb_ids=kb_ids,
                    context_msg=user_prompt
                )
                update_task_progress(task_id, db_session, 32, "使用替代方式完成RAG查询", f"获取上下文长度: {len(rag_context)} 字符")
            
            logger.info(f"RAG上下文长度: {len(rag_context)} 字符")
        else:
            # 没有RAG检索
            update_task_progress(task_id, db_session, 30, "准备生成内容", "不使用RAG检索")
        
        # 更新文档标题和初始HTML（如果提供了文档ID）
        if doc_id:
            from sqlalchemy.orm import Session
            from sqlalchemy.sql import func
            from app.database import get_db
            
            try:
                db_session = next(get_db())
                document = db_session.query(Document).filter(Document.doc_id == doc_id).first()
                if document:
                    initial_title = "文章生成中..."
                    document.title = initial_title
                    initial_html = markdown.markdown(f"# {initial_title}\n\n*内容生成中，请稍候...*")
                    document.content = initial_html
                    document.updated_at = func.now()
                    db_session.commit()
                    doc_log = f"更新文档初始HTML [doc_id={doc_id}]"
                    logger.info(doc_log)
                    update_task_progress(task_id, db_session, 30, "文档初始化完成", doc_log)
            except Exception as e:
                doc_error = f"更新文档初始HTML时出错: {str(e)}"
                logger.error(doc_error)
                update_task_progress(task_id, db_session, 30, "文档初始化失败", doc_error)
                if 'db_session' in locals():
                    db_session.close()
        
        try:
            # 构建提示模板
            template = DIRECT_CONTENT_GENERATION_TEMPLATE.format(
                prompt=prompt,
                file_context=file_context,
                rag_context=rag_context
            )
            
            template_log = f"准备生成内容，提示模板长度: {len(template)} 字符"
            logger.info(template_log)
            update_task_progress(task_id, db_session, 35, "准备生成内容", template_log)
            
            # 开始生成
            llm_start_time = time.time()
            update_task_progress(task_id, db_session, 40, "开始生成文章内容", "调用LLM生成内容...")
            
            try:
                result = self.llm.invoke(template)
                content = result.content
                
                llm_time = time.time() - llm_start_time
                llm_log = f"LLM生成完成，用时: {llm_time:.2f}秒, 生成内容长度: {len(content)} 字符"
                logger.info(llm_log)
                update_task_progress(task_id, db_session, 85, "文章内容生成完毕", llm_log)
            except Exception as e:
                llm_error = f"LLM调用失败: {str(e)}"
                logger.error(llm_error)
                update_task_progress(task_id, db_session, 85, "LLM调用失败", f"{llm_error}\n{traceback.format_exc()}")
                raise
            
            # 提取标题
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else "生成的文章"
            
            # 初始化html_content变量
            html_content = ""
            
            # 将markdown转换为HTML
            html_time_start = time.time()
            try:
                html_content = markdown.markdown(content)
                html_time = time.time() - html_time_start
                html_log = f"Markdown转HTML完成，用时: {html_time:.2f}秒, 提取标题: '{title}', HTML长度: {len(html_content)} 字符"
                logger.info(html_log)
                update_task_progress(task_id, db_session, 90, "正在优化格式", html_log)
            except Exception as e:
                html_error = f"Markdown转HTML失败: {str(e)}"
                logger.error(html_error)
                update_task_progress(task_id, db_session, 90, "格式转换失败", html_error)
                # 在异常情况下，使用原始内容
                html_content = f"<pre>{content}</pre>"
            
            # 更新文档最终HTML内容（如果提供了文档ID）
            doc_update_log = ""
            if doc_id:
                try:
                    db_session = next(get_db())
                    document = db_session.query(Document).filter(Document.doc_id == doc_id).first()
                    if document:
                        document.title = title
                        document.content = html_content
                        document.updated_at = func.now()
                        db_session.commit()
                        doc_update_log = f"更新文档最终HTML内容成功 [doc_id={doc_id}, 标题='{title}']"
                        logger.info(doc_update_log)
                except Exception as e:
                    doc_update_log = f"更新文档最终HTML内容时出错: {str(e)}"
                    logger.error(doc_update_log)
                finally:
                    if 'db_session' in locals():
                        db_session.close()
            
            # 计算总耗时
            total_time = time.time() - start_time
            
            # 最终进度100%
            final_log = f"标题: '{title}'\nMarkdown长度: {len(content)} 字符\nHTML长度: {len(html_content)} 字符\n总耗时: {total_time:.2f}秒"
            if doc_update_log:
                final_log += f"\n{doc_update_log}"
                
            update_task_progress(task_id, db_session, 100, "内容生成完成", final_log)
            
            # 返回结果
            return {
                "title": title,
                "markdown": content,
                "html": html_content
            }
            
        except Exception as e:
            error_msg = f"直接生成内容出错: {str(e)}"
            logger.error(error_msg)
            
            # 更新任务状态为失败
            if task_id:
                try:
                    db_session = next(get_db())
                    task = db_session.query(Task).filter(Task.id == task_id).first()
                    if task:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        # 添加错误信息到日志
                        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        total_time = time.time() - start_time
                        error_log = f"[{timestamp}] [错误] {str(e)}\n耗时: {total_time:.2f}秒\n{traceback.format_exc()}"
                        if task.log:
                            task.log = task.log + "\n" + error_log
                        else:
                            task.log = error_log
                        db_session.commit()
                except Exception as err:
                    logger.error(f"更新任务失败状态出错: {str(err)}")
                    
            # 返回错误结果
            raise ValueError(f"生成内容失败: {str(e)}")

    def _get_max_outline_level(self, outline_data: Dict[str, Any]) -> int:
        """
        获取大纲中的最大层级深度
        
        Args:
            outline_data: 大纲数据
            
        Returns:
            int: 最大层级深度
        """
        max_level = 1
        
        def traverse_depth(paragraphs, current_level=1):
            nonlocal max_level
            max_level = max(max_level, current_level)
            
            for para in paragraphs:
                children = para.get("children", [])
                if children:
                    traverse_depth(children, current_level + 1)
        
        sub_paragraphs = outline_data.get("sub_paragraphs", [])
        traverse_depth(sub_paragraphs)
        return max_level
    
    def _check_outline_levels(self, outline_text, required_levels):
        """检查大纲的层级数是否符合要求"""
        if not outline_text:
            return False
            
        max_level = 0
        for line in outline_text.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # 计算缩进层级
            indent_level = len(line) - len(line.lstrip())
            level = indent_level // 4  # 假设每级缩进是4个空格
            
            # 检查标题格式
            content = line.lstrip()
            if content.startswith(("一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、")):
                level = 0
            elif re.match(r'^\d+\.\d+$', content.split()[0]):  # 匹配 1.1, 1.2 等
                level = 1
            elif re.match(r'^\d+\.\d+\.\d+$', content.split()[0]):  # 匹配 1.1.1, 1.1.2 等
                level = 2
            elif re.match(r'^\d+\.\d+\.\d+\.\d+$', content.split()[0]):  # 匹配 1.1.1.1, 1.1.1.2 等
                level = 3
                
            max_level = max(max_level, level)
        
        return max_level + 1 == required_levels
    
    def generate_outline_new(self, topic, levels=3, show_result=False, task_id: Optional[str] = None, db_session = None):
        """生成大纲"""        
        # 构建提示词
        system_prompt = """你是一个专业的大纲生成助手。你需要根据用户给出的主题，生成一个结构清晰的大纲。
请确保大纲：
1. 第一行必须是文章标题，不要带"大纲"字样
2. 结构清晰，层次分明
3. 逻辑性强，各部分衔接自然
4. 内容全面，覆盖主题的各个方面
5. 每个最底层的子章节都必须包含详细的描述
6. 使用统一的格式和编号系统
7. 严格按照指定的层级深度生成大纲
8. 每个章节的子章节数量必须不同，不要使用固定数量
9. 根据主题的实际内容需求，灵活调整每个章节的子章节数量
10. 避免机械地固定章节数量，保持内容的自然性
11. 确保每个章节的子章节数量都不同，体现内容的差异性
"""

        # 根据层级深度构建示例格式
        format_examples = {
            1: """G212线关头坝大桥桥梁结构监测系统建设施工组织设计
一、一级标题1
二、一级标题2
三、一级标题3
四、一级标题4
五、一级标题5""",
            2: """G212线关头坝大桥桥梁结构监测系统建设施工组织设计
一、一级标题1
    1.1 二级标题1
        描述：这里是描述1
    1.2 二级标题2
        描述：这里是描述2
二、一级标题2
    2.1 二级标题1
        描述：这里是描述1
    2.2 二级标题2
        描述：这里是描述2
    2.3 二级标题3
        描述：这里是描述3""",
            3: """G212线关头坝大桥桥梁结构监测系统建设施工组织设计
一、一级标题1
    1.1 二级标题1
        1.1.1 三级标题1
            描述：这里是描述1
        1.1.2 三级标题2
            描述：这里是描述2
    1.2 二级标题2
        1.2.1 三级标题1
            描述：这里是描述1
        1.2.2 三级标题2
            描述：这里是描述2
二、一级标题2
    2.1 二级标题1
        2.1.1 三级标题1
            描述：这里是描述1
        2.1.2 三级标题2
            描述：这里是描述2""",
            4: """G212线关头坝大桥桥梁结构监测系统建设施工组织设计
一、一级标题1
    1.1 二级标题1
        1.1.1 三级标题1
            1.1.1.1 四级标题1
                描述：这里是描述1
            1.1.1.2 四级标题2
                描述：这里是描述2
        1.1.2 三级标题2
            1.1.2.1 四级标题1
                描述：这里是描述1
            1.1.2.2 四级标题2
                描述：这里是描述2
    1.2 二级标题2
        1.2.1 三级标题1
            1.2.1.1 四级标题1
                描述：这里是描述1
            1.2.1.2 四级标题2
                描述：这里是描述2
            1.2.1.3 四级标题3
                描述：这里是描述3
            1.2.1.4 四级标题4
                描述：这里是描述4
二、一级标题2
    2.1 二级标题1
        2.1.1 三级标题1
            2.1.1.1 四级标题1
                描述：这里是描述1
            2.1.1.2 四级标题2
                描述：这里是描述2
            2.1.1.3 四级标题3
                描述：这里是描述3
    2.2 二级标题2
        2.2.1 三级标题1
            2.2.1.1 四级标题1
                描述：这里是描述1
            2.2.1.2 四级标题2
                描述：这里是描述2"""
        }
        
        format_example = format_examples.get(levels, format_examples[levels])

        # 如果是3级或4级大纲，分两步生成
        if levels in [3, 4]:
            max_retries = 3  # 最大重试次数
            retry_count = 0
            
            while retry_count < max_retries:
                # 第一步：生成完整大纲结构（不含描述）
                structure_prompt = f"""请为主题"{topic}"生成一个完整的{levels}级大纲结构。
使用以下格式：
{format_example}

要求：
1. 只生成大纲结构，不要包含描述内容
2. 确保层级结构清晰，逻辑合理
3. 根据主题的实际内容需求，灵活调整每个章节的子章节数量
4. 确保每个章节的内容都与主题相关
5. 确保大纲结构自然，不要机械地固定章节数量
6. 每个层级都必须使用正确的标题格式：
   - 一级标题使用中文数字（如：一、二、三、四、五、六、七、八、九、十等）
   - 二级标题使用"1.1、1.2、"等数字格式
   - 三级标题使用"1.1.1、1.1.2、"等数字格式
   - 四级标题使用"1.1.1.1、1.1.1.2、"等数字格式
7. 确保每个层级的缩进正确（每级缩进4个空格）
8. 确保大纲结构完整，包含所有必要的章节
9. 必须严格按照{levels}级层级生成，不要少层级

只返回大纲结构，不要包含额外的说明。"""

                messages = f"System: {system_prompt}\n\nUser: {structure_prompt}"
                
                # 调用LLM生成大纲结构
                structure_outline = self.llm.invoke(messages).content
                update_task_progress(task_id, db_session, 50, f"已生成 {levels} 级大纲，开始补充章节描述...")
                
                if not structure_outline:
                    retry_count += 1
                    continue
                
                # 检查大纲层级是否符合要求
                if self._check_outline_levels(structure_outline, levels):
                    break
                else:
                    logger.info(f"生成的大纲层级不符合要求，正在尝试重新生成...")
                    update_task_progress(task_id, db_session, 55, "生成的大纲层级不符合要求，正在尝试重新生成...")
                    retry_count += 1
                    time.sleep(1)  # 添加短暂延迟
            
            # 第二步：分批补充描述
            sections = self._split_outline_into_sections(structure_outline)
            all_sections = []
            batch_size = 4  # 每批处理4个章节
            
            for i in range(0, len(sections), batch_size):
                update_task_progress(task_id, db_session, 60 + i + 5, f"正在补充【{i+1}:{i+batch_size}】章节描述...")
                batch = sections[i:i + batch_size]
                batch_text = "\n".join(batch)
                
                # 构建补充描述的提示词
                description_prompt = f"""请为以下大纲章节补充详细的描述内容。原始主题是："{topic}"

{batch_text}

要求：
1. 为每个最底层的子章节添加详细的描述
2. 描述内容必须以"描述："开头
3. 描述要具体、专业、有实质性内容，包含：
   - 具体的工作内容和方法
   - 关键的技术参数和标准
   - 重要的注意事项和要求
   - 相关的规范和标准引用
4. 保持原有的层级结构和编号格式不变
5. 只添加描述内容，不要修改或添加新的章节
6. 确保描述内容与原始主题"{topic}"密切相关
7. 描述要符合专业文档的要求，使用准确的专业术语
8. 描述要具有可执行性，能够作为后续生成详细文档的指导
9. 描述要包含必要的技术细节，但不要过于冗长
10. 描述要突出重要性和关键点，便于后续展开

只返回补充描述后的大纲内容，不要包含额外的说明。"""

                messages = f"System: {system_prompt}\n\nUser: {description_prompt}"
                
                # 调用LLM补充描述
                batch_with_descriptions = self.llm.invoke(messages).content
                
                if batch_with_descriptions:
                    all_sections.append(batch_with_descriptions)
                
                # 添加短暂延迟，避免API限制
                if i < len(sections) - batch_size:  # 如果不是最后一批
                    time.sleep(1)
            
            # 合并所有章节
            outline = '\n'.join(all_sections)
                
            return outline
        else:
            # 非3级或4级大纲，直接生成
            user_prompt = f"""请为主题"{topic}"大纲，要求大纲层级为{levels}级。
使用以下格式：
{format_example}

要求：
1. 每个最底层的子章节必须有描述
2. 确保层级结构清晰，逻辑合理
3. 根据主题的实际内容需求，灵活调整每个章节的子章节数量
4. 确保每个章节的内容都与主题相关
5. 确保大纲结构自然，不要机械地固定章节数量
6. 每个层级都必须使用正确的标题格式：
   - 一级标题使用"一、二、三、"等中文数字
   - 二级标题使用"1.1、1.2、"等数字格式
   - 三级标题使用"1.1.1、1.1.2、"等数字格式
   - 四级标题使用"1.1.1.1、1.1.1.2、"等数字格式
7. 描述内容必须以"描述："开头，描述要具体、专业、有实质性内容，包含：
   - 具体的工作内容和方法
   - 关键的技术参数和标准
   - 重要的注意事项和要求
   - 相关的规范和标准引用
8. 确保每个层级的缩进正确（每级缩进4个空格）
9. 描述要具有可执行性，能够作为后续生成详细文档的指导
10. 描述要包含必要的技术细节，但不要过于冗长
11. 描述要突出重要性和关键点，便于后续展开

只返回大纲内容，不要包含额外的说明。"""

            messages = f"System: {system_prompt}\n\nUser: {user_prompt}"
            
            # 调用LLM生成大纲
            outline = self.llm.invoke(messages).content
                
            return outline
    
    def _parse_outline_to_json(self, outline_text, topic):
        """将大纲文本解析为指定的JSON结构"""
        try:
            # 按行分割大纲文本
            lines = outline_text.strip().split('\n')
            
            # 获取第一行作为文章标题
            article_title = lines[0].strip() if lines else topic
            
            # 初始化结果
            result = {
                "title": article_title,
                "sub_paragraphs": []
            }
            
            # 用于跟踪当前处理的节点
            current_nodes = {-1: result}  # 使用字典来跟踪不同层级的节点
            last_level = -1
            
            # 处理每一行（跳过第一行，因为已经用作标题）
            for line in lines[1:]:
                line = line.strip()
                if not line:
                    continue
                    
                # 计算当前行的缩进级别
                indent_level = len(line) - len(line.lstrip())
                level = indent_level // 4  # 假设每级缩进是4个空格
                
                # 提取标题和描述
                content = line.lstrip()
                
                # 检查是否是描述行
                if content.startswith("描述："):
                    if last_level >= 0 and last_level in current_nodes:
                        current_nodes[last_level]["description"] = content[3:].strip()
                    continue
                
                # 检查是否是标题行
                is_title = False
                if content.startswith(("一、", "二、", "三、", "四、", "五、", "六、", "七、", "八、", "九、", "十、")):
                    is_title = True
                    level = 0
                elif re.match(r'^\d+\.\d+$', content.split()[0]):  # 匹配 1.1, 1.2 等
                    is_title = True
                    level = 1
                elif re.match(r'^\d+\.\d+\.\d+$', content.split()[0]):  # 匹配 1.1.1, 1.1.2 等
                    is_title = True
                    level = 2
                elif re.match(r'^\d+\.\d+\.\d+\.\d+$', content.split()[0]):  # 匹配 1.1.1.1, 1.1.1.2 等
                    is_title = True
                    level = 3
                
                if not is_title:
                    # 如果不是标题，则作为描述
                    if last_level >= 0 and last_level in current_nodes:
                        current_nodes[last_level]["description"] = content.strip()
                    continue
                
                # 创建新节点
                new_node = {
                    "title": content,
                    "description": "",
                    "count_style": "medium",
                    "level": level + 1,
                    "children": []
                }
                
                # 根据层级关系构建树结构
                if level == 0:
                    # 一级标题
                    result["sub_paragraphs"].append(new_node)
                    current_nodes = {-1: result, 0: new_node}
                else:
                    # 找到父节点
                    parent_level = level - 1
                    if parent_level in current_nodes:
                        parent = current_nodes[parent_level]
                        if "children" not in parent:
                            parent["children"] = []
                        parent["children"].append(new_node)
                        current_nodes[level] = new_node
                        
                        # 清理更深层级的节点
                        keys_to_remove = [k for k in current_nodes.keys() if k > level]
                        for k in keys_to_remove:
                            del current_nodes[k]
                
                last_level = level
            
            return result
            
        except Exception as e:
            logger.error(f"错误: 大纲解析失败: {e}")
            return None
    
    def _split_outline_into_sections(self, outline):
        """将大纲文本分割成章节"""
        sections = []
        current_section = []
        
        for line in outline.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            # 检查是否是一级标题（以"一、"、"二、"等开头）
            if re.match(r'^[一二三四五六七八九十]+、', line):
                if current_section:
                    sections.append('\n'.join(current_section))
                current_section = [line]
            else:
                current_section.append(line)
        
        if current_section:
            sections.append('\n'.join(current_section))
        
        return sections

