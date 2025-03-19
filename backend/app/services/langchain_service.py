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
import uuid

from app.utils.outline import build_paragraph_key, build_paragraph_data
from app.models.outline import SubParagraph, Outline
from app.rag.rag_api import rag_api
from app.models.document import Document
from app.models.task import Task, TaskStatus
from app.utils.web_search import baidu_search

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
    
    def __init__(self, readable_model_name: Optional[str] = None, use_rag: bool = True, use_web: bool = True):
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
        # if self.use_rag:
        #     rag_prompt = f"关于主题：{prompt}，请提供参考内容"
        #     rag_context = self._get_rag_context(
        #         question=rag_prompt,
        #         user_id=user_id,
        #         kb_ids=kb_ids,
        #         context_msg="生成大纲"
        #     )
        
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
            3. 对于方案类文档基本大的框架都是：方案背景（政策背景、行业/技术背景、如果有还可以更多经济背景，但一般起码要有政策背景）、现状与需求分析、建设目标（小篇幅的一般就只有一个建设目标，如果篇幅大的话可能会有总体目标、分阶段小目标等等）、建设方案（包含方案概述、方案技术架构或系统架构及描述、技术原理、方案或系统功能、方案或系统组成、方案清单、）、方案效益、方案总结等等（包含但不限于上述几点内容，根据项目不同会有不同），有时候还需要加上方案依据、方案设计原则等等，你可以在深入理解用户需求的情况下根据方案类型来确定大纲
            
            【大纲结构规范】
            1. 严格禁止在标题或层级标题中使用任何形式的编号，包括但不限于：
               - 不要使用"第一章"、"第二章"等章节编号
               - 不要使用"（一）"、"（二）"等中文编号
               - 不要使用"1."、"2."等数字编号
               - 不要使用"一、"、"二、"等中文序号
               - 不要使用"1、"、"2、"等数字序号
               - 不要使用"①"、"②"等特殊符号编号
            2. 标题，描述中不能包含参考资料的应用的文件名称
            3. 确保每个主题只在适当的层级出现一次，避免标题重复
            4. 使用具体的标题，避免过于宽泛或重复的标题
            5. 保持清晰的层级关系，相关主题应该放在一起
            6. 每个主题应该有明确的范围，避免内容重叠
            
            【避免常见问题】
            1. 避免在不同层级重复相同的标题
               - 错误示例: "监测系统" 作为一级标题，然后 "监测系统" 又作为其下的二级标题
               - 正确示例: "监测系统概述" 作为一级标题，"监测系统组件" 作为二级标题
            2. 避免过于宽泛的标题
               - 错误示例: "监测" 作为标题
               - 正确示例: "地质灾害监测系统" 作为具体标题
            3. 避免内容重叠
               - 错误示例: "数据分析" 和 "数据处理" 作为并列标题但内容高度重叠
               - 正确示例: "数据采集与预处理" 和 "数据分析与可视化" 作为内容明确区分的标题
            
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
                
                # 验证大纲结构，检查是否有重复标题
                self._validate_and_fix_outline(result)
                
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
                        
                        # 验证大纲结构，检查是否有重复标题
                        self._validate_and_fix_outline(parsed_json)
                        
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
                # 如果没有描述，添加一个基于标题的简单描述
                if not para.get("description"):
                    para["description"] = f"关于{para.get('title', '此主题')}的详细内容"
                
                # 递归处理子段落
                children = para.get("children", [])
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
                    
                    # 添加描述（如果有）
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
                
        # 创建进度更新函数
        def update_task_progress(progress: int, detail: str):
            """更新任务进度"""
            if not task_id:
                return
                
            try:
                task = db_session.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.process = progress
                    task.process_detail_info = detail
                    db_session.commit()
                    logger.info(f"更新任务进度 [task_id={task_id}, progress={progress}%, detail={detail}]")
            except Exception as e:
                logger.error(f"更新任务进度失败: {str(e)}")
        
        # 获取大纲
        outline = db_session.query(Outline).filter(Outline.id == outline_id).first()
        if not outline:
            raise ValueError(f"未找到ID为{outline_id}的大纲")
        
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
        
        # 获取RAG上下文
        rag_context = ""
        if kb_ids:
            logger.info(f"获取RAG上下文 [kb_ids={kb_ids}]")
            # 更新任务进度到20%，RAG检索完成
            update_task_progress(20, "RAG检索完成")
            
            # 新增：通过LLM生成相关问题
            question_generation_prompt = f"""
            深入理解<EOF>和</EOF>之间的原始需求，整理出5个问题，以便从RAG知识库中查询相关参考内容，仅输出问题：
            <EOF>
            {user_prompt}
            </EOF>
            """
            
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
                
                logger.info(f"生成了 {len(filtered_questions)} 个问题用于RAG查询: {filtered_questions}")
                
                # 依次从RAG中查询每个问题
                combined_rag_context = ""
                for i, question in enumerate(filtered_questions):
                    logger.info(f"开始查询问题 {i+1}/{len(filtered_questions)}: {question}")
                    
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
                
                # 使用组合的RAG上下文
                if combined_rag_context.strip():
                    rag_context = combined_rag_context
                    logger.info(f"已组合多个问题的RAG上下文，总长度: {len(rag_context)} 字符")
                else:
                    # 如果所有问题都没有返回结果，使用默认方式查询
                    logger.warning("所有生成的问题查询结果为空，使用默认方式查询RAG")
                    rag_context = self._get_rag_context(
                        question=f"生成关于{outline.title}的文章",
                        user_id=user_id,
                        kb_ids=kb_ids,
                        context_msg=user_prompt
                    )

                # 新增：通过百度搜索获取更多信息
                if self.use_web:
                    for question in filtered_questions:
                        logger.info(f"开始通过百度搜索获取问题相关信息: {question}")
                        search_results = baidu_search(question)
                        if search_results:
                            search_summary = self._summarize_search_results(question, search_results)
                            rag_context += f"\n--- 百度搜索结果: {question} ---\n{search_summary}\n\n"
                            logger.info(f"已将搜索结果添加到RAG上下文中")
            except Exception as e:
                logger.error(f"生成问题或查询RAG时出错: {str(e)}")
                # 出错时使用默认方式查询
                rag_context = self._get_rag_context(
                    question=f"生成关于{outline.title}的文章",
                    user_id=user_id,
                    kb_ids=kb_ids,
                    context_msg=user_prompt
                )
            
            logger.info(f"RAG上下文长度: {len(rag_context)} 字符")
        else:
            # 没有RAG检索，直接设置为20%
            update_task_progress(20, "准备生成内容")
        
        # 生成文章标题
        # article_title = self._generate_article_title(
        #     user_prompt=user_prompt,
        #     outline_title=outline.title,
        #     outline_content=outline_content
        # )
        article_title = outline.title
        logger.info(f"生成文章标题: {article_title}")
        
        # 更新任务进度到25%，标题生成完毕
        update_task_progress(25, "标题生成完毕")
        
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
            "max_total_length": 100000,  # 内容总长度限制
            "max_chapter_length": 5000,  # 单个章节长度限制
            "duplicate_titles": set(),  # 记录重复的标题
            "generated_titles": set(),  # 记录已生成的标题
            "doc_id": doc_id,  # 文档ID，用于更新HTML内容
            "task_id": task_id,  # 任务ID，用于更新进度
            "total_paragraphs": len(all_paragraphs),  # 段落总数
            "generated_paragraph_count": 0  # 已生成段落数
        }
        
        logger.info(f"开始生成段落内容，共 {len(root_paragraphs)} 个顶级段落")
        
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
            progress = 25 + int((global_context["generated_paragraph_count"] / global_context["total_paragraphs"]) * 75)
            progress = min(99, progress)  # 确保不超过99%，留给最后的完成步骤
            update_task_progress(
                progress,
                f"已生成 {global_context['generated_paragraph_count']}/{global_context['total_paragraphs']} 个段落"
            )
        
        # 合并所有内容
        final_content = "\n".join(markdown_content)
        
        # 记录生成的内容长度
        logger.info(f"生成内容完成，总长度: {len(final_content)} 字符")
        
        # 记录重复标题情况
        if global_context["duplicate_titles"]:
            logger.warning(f"检测到 {len(global_context['duplicate_titles'])} 个重复标题: {', '.join(global_context['duplicate_titles'])}")
        
        # 记录章节摘要数量
        logger.info(f"生成了 {len(global_context['chapter_summaries'])} 个章节摘要")
        
        # 记录已生成段落数量
        logger.info(f"生成了 {len(global_context['generated_contents'])} 个段落内容")
        
        # 最终进度100%
        update_task_progress(100, "内容生成完成")
        
        # 如果优化失败，返回原始内容
        html_content = markdown.markdown(final_content)
        
        # 更新最终完整的文档HTML内容
        if doc_id:
            try:
                document = db_session.query(Document).filter(Document.doc_id == doc_id).first()
                if document:
                    document.content = html_content
                    db_session.commit()
                    logger.info(f"更新文档最终完整HTML内容 [doc_id={doc_id}]")
            except Exception as e:
                logger.error(f"更新文档最终HTML内容时出错: {str(e)}")
        
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
3. 直接输出段落内容，不要包含标题、解释或标记，也不要使用“本章”“本节”等指代词，直接陈述内容。

## 限制:
- 只生成与公文撰写相关的内容，拒绝回答与公文无关的话题。
- 所输出的内容必须符合技能 1 中规定的要求，不能偏离框架要求。
- 生成的是正式的公文，不要使用“我们”这种口语表达的句式。
- 内容后面不要进行总结，避免出现“总之”“总而言之”这样的总结性概括。

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
        
        # 创建进度更新函数
        def update_task_progress(progress: int, detail: str):
            """更新任务进度"""
            if not task_id:
                return
                
            try:
                db_session = next(get_db())
                task = db_session.query(Task).filter(Task.id == task_id).first()
                if task:
                    task.process = progress
                    task.process_detail_info = detail
                    db_session.commit()
                    logger.info(f"更新任务进度 [task_id={task_id}, progress={progress}%, detail={detail}]")
            except Exception as e:
                logger.error(f"更新任务进度失败: {str(e)}")
        
        # 初始进度
        update_task_progress(10, "准备生成文章")
        
        # 处理参考文件内容
        file_context = ""
        if file_contents and len(file_contents) > 0:
            file_context = "\n\n".join(file_contents)
            logger.info(f"参考文件内容长度: {len(file_context)} 字符")
        
        # 获取RAG上下文
        rag_context = ""
        if kb_ids:
            logger.info(f"获取RAG上下文 [kb_ids={kb_ids}]")
            # 更新任务进度到20%，RAG检索完成
            update_task_progress(20, "RAG检索完成")
            rag_context = self._get_rag_context(
                question=prompt,
                user_id=user_id,
                kb_ids=kb_ids,
                context_msg=prompt
            )
            logger.info(f"RAG上下文长度: {len(rag_context)} 字符")
        else:
            # 没有RAG检索，直接设置为20%
            update_task_progress(20, "准备生成内容")
        
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
                    logger.info(f"更新文档初始HTML [doc_id={doc_id}]")
            except Exception as e:
                logger.error(f"更新文档初始HTML时出错: {str(e)}")
                if 'db_session' in locals():
                    db_session.close()
        
        try:
            # 构建提示模板
            template = DIRECT_CONTENT_GENERATION_TEMPLATE.format(
                prompt=prompt,
                file_context=file_context,
                rag_context=rag_context
            )
            
            logger.info("开始生成内容")
            # 更新任务进度到30%，开始生成内容
            update_task_progress(30, "开始生成文章内容")
            
            # 开始生成
            result = self.llm.invoke(template)
            content = result.content
            
            # 更新任务进度到80%，内容生成完毕
            update_task_progress(80, "文章内容生成完毕")
            
            # 提取标题
            title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
            title = title_match.group(1) if title_match else "生成的文章"
            
            # 将markdown转换为HTML
            html_content = markdown.markdown(content)
            
            # 更新任务进度到90%，正在优化格式
            update_task_progress(90, "正在优化格式")
            
            # 更新文档最终HTML内容（如果提供了文档ID）
            if doc_id:
                try:
                    db_session = next(get_db())
                    document = db_session.query(Document).filter(Document.doc_id == doc_id).first()
                    if document:
                        document.title = title
                        document.content = html_content
                        document.updated_at = func.now()
                        db_session.commit()
                        logger.info(f"更新文档最终HTML内容 [doc_id={doc_id}]")
                except Exception as e:
                    logger.error(f"更新文档最终HTML内容时出错: {str(e)}")
                finally:
                    if 'db_session' in locals():
                        db_session.close()
            
            # 最终进度100%
            update_task_progress(100, "内容生成完成")
            
            # 返回结果
            return {
                "title": title,
                "markdown": content,
                "html": html_content
            }
            
        except Exception as e:
            logger.error(f"直接生成内容出错: {str(e)}")
            
            # 更新任务状态为失败
            if task_id:
                try:
                    db_session = next(get_db())
                    task = db_session.query(Task).filter(Task.id == task_id).first()
                    if task:
                        task.status = TaskStatus.FAILED
                        task.error = str(e)
                        db_session.commit()
                except Exception as err:
                    logger.error(f"更新任务失败状态出错: {str(err)}")
                    
            # 返回错误结果
            raise ValueError(f"生成内容失败: {str(e)}")

