# -*- coding: utf-8 -*-
from io import BytesIO
from typing import Optional, List
from bs4 import BeautifulSoup
from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_PARAGRAPH_ALIGNMENT
from docx.oxml.ns import qn
from docx.enum.style import WD_STYLE_TYPE
import re

def add_numbering_to_headers(html_text):
    # 使用 BeautifulSoup 解析 HTML 内容
    soup = BeautifulSoup(html_text, 'html.parser')
    
    # 中文一、二、三等
    chinese_numbers = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十",
                       "十一", "十二", "十三", "十四", "十五", "十六", "十七", "十八", "十九", "二十",
                       "二十一", "二十二", "二十三", "二十四", "二十五", "二十六", "二十七", "二十八", "二十九", "三十",
                       "三十一", "三十二", "三十三", "三十四", "三十五", "三十六", "三十七", "三十八", "三十九", "四十",
                       "四十一", "四十二", "四十三", "四十四", "四十五", "四十六", "四十七", "四十八", "四十九", "五十"]
    
    # 获取中文数字，处理超出范围的情况
    def get_chinese_number(index):
        if index < len(chinese_numbers):
            return chinese_numbers[index]
        else:
            # 超出预定义范围，使用数字代替
            return str(index + 1)
    
    # 去除标题中已有的序号
    def remove_existing_numbering(text):
        # 去除中文序号，如"一、"、"二、"等
        text = re.sub(r'^[一二三四五六七八九十]+、\s*', '', text)
        # 去除数字序号，如"1."、"2."等
        text = re.sub(r'^\d+\.\d*\s*', '', text)
        return text
    
    # 检查标题文本是否包含数字序号模式
    def extract_numbering_pattern(text):
        # 匹配如 "2.1" 或 "2.1.1" 的模式
        match = re.match(r'^(\d+\.\d+(\.\d+)*)[\s\.]+', text)
        if match:
            return match.group(1)
        return None
    
    # 检查标题是否已经有明显的标题格式（如"一、标题"或"第一章 标题"）
    def is_already_formatted_title(text):
        # 检查是否以中文数字加顿号开头，如"一、"、"二、"等
        if re.match(r'^[一二三四五六七八九十]+、', text):
            return True
        # 检查是否包含"第X章"、"第X节"等格式
        if re.search(r'第[一二三四五六七八九十百千万亿]+[章节篇部分]', text):
            return True
        # 检查是否以数字序号开头，如"1."、"1.1"等，且后面跟着明显的标题内容
        if re.match(r'^\d+(\.\d+)*\s+.+', text):
            return True
        return False
    
    # 收集所有标题并按文档顺序排序
    headers = []
    
    # 获取所有标签，用于后续排序
    all_tags = list(soup.find_all())
    
    # 首先处理常规标题标签
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        # 获取原始文本
        original_text = tag.get_text().strip()
        level = int(tag.name[1])
        
        # 一级标题不添加序号，直接保留原始文本
        if level == 1:
            headers.append((tag, level, original_text, original_text, True))
        else:
            # 去除标题中已有的序号
            clean_text = remove_existing_numbering(original_text)
            headers.append((tag, level, clean_text, original_text, False))
    
    # 然后处理带有strong标签的段落标题
    for p_tag in soup.find_all('p'):
        strong_tags = p_tag.find_all(['strong', 'b'])
        if strong_tags and len(strong_tags) == 1 and strong_tags[0].get_text().strip() == p_tag.get_text().strip():
            # 这是一个带有strong标签的标题段落
            original_text = p_tag.get_text().strip()
            
            # 检查标题文本是否包含数字序号模式（如"2.1"）
            numbering_pattern = extract_numbering_pattern(original_text)
            
            # 如果标题包含数字序号模式，则根据模式确定级别
            if numbering_pattern:
                # 计算点的数量来确定级别（如"2.1"有1个点，所以是2级标题）
                dots_count = numbering_pattern.count('.')
                level = dots_count + 1
                # 确保级别在合理范围内
                level = max(2, min(level, 6))
            else:
                # 如果没有明确的序号模式，则使用默认逻辑
                # 默认作为三级标题处理
                level = 3
            
            # 去除标题中已有的序号
            clean_text = remove_existing_numbering(original_text)
            
            # 将其添加到headers列表中
            headers.append((p_tag, level, clean_text, original_text, False))
    
    # 按文档顺序排序headers
    # 使用标签在文档中的位置进行排序
    headers.sort(key=lambda x: all_tags.index(x[0]) if x[0] in all_tags else float('inf'))
    
    # 创建标题层级结构
    header_hierarchy = {}
    parent_indices = {}  # 记录每个级别的当前父标题索引
    
    # 按文档顺序处理标题
    for i, (tag, level, text, original_text, is_formatted) in enumerate(headers):
        # 更新当前级别的父标题索引
        parent_indices[level] = i
        # 清除所有更高级别的父标题索引
        for l in range(level + 1, 7):
            if l in parent_indices:
                del parent_indices[l]
        
        # 将标题添加到层级结构中
        if level == 1:
            # 一级标题没有父标题
            if level not in header_hierarchy:
                header_hierarchy[level] = []
            header_hierarchy[level].append((i, None, tag, text, original_text, is_formatted))
        else:
            # 查找父标题
            parent_level = level - 1
            while parent_level > 0:
                if parent_level in parent_indices:
                    parent_index = parent_indices[parent_level]
                    break
                parent_level -= 1
            else:
                # 如果没有找到父标题，使用虚拟父标题
                parent_index = -1
            
            # 将标题添加到层级结构中
            if level not in header_hierarchy:
                header_hierarchy[level] = []
            header_hierarchy[level].append((i, parent_index, tag, text, original_text, is_formatted))
    
    # 处理每个级别的标题
    for level in sorted(header_hierarchy.keys()):
        # 按父标题分组
        by_parent = {}
        for i, parent_index, tag, text, original_text, is_formatted in header_hierarchy[level]:
            if parent_index not in by_parent:
                by_parent[parent_index] = []
            by_parent[parent_index].append((i, tag, text, original_text, is_formatted))
        
        # 为每组分配编号
        for parent_index, items in by_parent.items():
            for sub_i, (i, tag, text, original_text, is_formatted) in enumerate(items):
                # 如果标题已经有格式或是一级标题，则保留原始文本
                if is_formatted:
                    tag.clear()
                    tag.append(original_text)
                    continue
                
                # 根据级别生成编号
                if level == 2:
                    # 二级标题使用中文编号
                    numbering = f'{get_chinese_number(sub_i)}、'
                else:
                    # 其他级别使用数字编号
                    # 查找父标题的编号前缀
                    parent_prefix = ""
                    if parent_index != -1:
                        # 提取父标题的编号（如果有数字编号）
                        for p_level in range(level-1, 0, -1):
                            if p_level in header_hierarchy:
                                for p_i, p_parent, p_tag, p_text, p_original_text, p_is_formatted in header_hierarchy[p_level]:
                                    if p_i == parent_index:
                                        # 如果父标题已经有格式，尝试从中提取数字部分
                                        if p_is_formatted:
                                            p_tag_text = p_original_text
                                        else:
                                            p_tag_text = p_tag.get_text().strip()
                                        
                                        match = re.match(r'^(\d+\.\d+).*', p_tag_text)
                                        if match:
                                            parent_prefix = match.group(1)
                                        else:
                                            # 如果父标题没有数字编号，查找其在同级别中的索引
                                            p_sub_i = 0
                                            for p_sub_index, (p_sub_i_temp, p_sub_parent, p_sub_tag, p_sub_text, p_sub_original, p_sub_is_formatted) in enumerate(header_hierarchy[p_level]):
                                                if p_sub_tag == p_tag:
                                                    p_sub_i = p_sub_index
                                                    break
                                            
                                            # 如果父标题是二级，使用数字表示
                                            if p_level == 2:
                                                parent_prefix = str(p_sub_i + 1)
                                        break
                    
                    # 生成编号
                    if parent_prefix:
                        numbering = f'{parent_prefix}.{sub_i + 1} '
                    else:
                        numbering = f'{sub_i + 1}.{sub_i + 1} '
                
                # 清除标题中已有的内容
                tag.clear()
                
                # 在标题文本前插入序号
                tag.append(f"{numbering}{text}")
    
    # 返回处理后的 HTML
    return str(soup)

def fix_document_numbering(doc):
    """
    修复文档中的标题编号问题，确保标题层级正确：
    - 形如"二、"的标题为二级标题
    - 形如"2.3"的标题为三级标题
    - 形如"9.2.1"的标题为四级标题
    
    Args:
        doc: 要修复的文档对象
    
    Returns:
        修复的标题数量
    """
    # 记录修复的标题数量
    fixed_count = 0
    
    # 遍历所有段落
    for para in doc.paragraphs:
        # 获取标题文本
        text = para.text.strip()
        
        # 检查是否是形如"9.2.1"的四级标题
        four_level_match = re.match(r'^(\d+)\.(\d+)\.(\d+)[\s\.]*(.*)$', text)
        if four_level_match:
            # 这是一个形如"9.2.1"的四级标题
            section, subsection, subsubsection, title_text = four_level_match.groups()
            
            # 清除段落内容
            para.clear()
            
            # 添加标题文本
            run = para.add_run(f"{section}.{subsection}.{subsubsection} {title_text}")
            
            # 设置字体
            font = run.font
            font.size = Pt(12)  # 四级标题字体大小
            font.color.rgb = RGBColor(0, 64, 128)  # 统一颜色（蓝色）
            run.bold = True  # 统一加粗
            
            # 设置对齐方式
            para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            
            # 确保使用相同的标题样式
            para.style = 'Heading 4'  # 使用四级标题样式
            
            # 确保没有缩进
            para.paragraph_format.left_indent = Pt(0)
            para.paragraph_format.first_line_indent = Pt(0)
            
            fixed_count += 1
            continue
        
        # 检查是否是形如"2.3"或"3.1"的三级标题
        three_level_match = re.match(r'^(\d+)\.(\d+)[\s\.]*(.*)$', text)
        
        # 也检查中文标题格式，如"二.三"
        if not three_level_match:
            # 尝试匹配中文数字格式
            chinese_match = re.match(r'^([一二三四五六七八九十]+)[\.．。]([一二三四五六七八九十]+)[\s\.]*(.*)$', text)
            if chinese_match:
                # 处理中文标题
                section, subsection, title_text = chinese_match.groups()
                # 清除段落内容
                para.clear()
                
                # 添加标题文本
                run = para.add_run(f"{section}.{subsection} {title_text}")
                
                # 设置字体
                font = run.font
                font.size = Pt(13)  # 三级标题字体大小
                font.color.rgb = RGBColor(0, 64, 128)  # 统一颜色（蓝色）
                run.bold = True  # 统一加粗
                
                # 设置对齐方式
                para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                
                # 确保使用相同的标题样式
                para.style = 'Heading 3'  # 使用三级标题样式
                
                # 确保没有缩进
                para.paragraph_format.left_indent = Pt(0)
                para.paragraph_format.first_line_indent = Pt(0)
                
                fixed_count += 1
                continue
        
        # 检查是否是段落中的标题文本
        if not three_level_match and len(text) > 0:
            # 先尝试匹配四级标题模式
            paragraph_four_level_match = re.search(r'(\d+)\.(\d+)\.(\d+)\s+(.*?)(?:\s|$)', text)
            if paragraph_four_level_match:
                # 这是一个包含四级标题模式的段落
                section, subsection, subsubsection, title_text = paragraph_four_level_match.groups()
                
                # 如果这个段落看起来像是一个标题（比如它很短，或者只包含这个标题模式）
                if len(text) < 50 or paragraph_four_level_match.group(0).strip() == text:
                    # 清除段落内容
                    para.clear()
                    
                    # 添加标题文本
                    run = para.add_run(f"{section}.{subsection}.{subsubsection} {title_text}")
                    
                    # 设置字体
                    font = run.font
                    font.size = Pt(12)  # 四级标题字体大小
                    font.color.rgb = RGBColor(0, 64, 128)  # 统一颜色（蓝色）
                    run.bold = True  # 统一加粗
                    
                    # 设置对齐方式
                    para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                    
                    # 确保使用相同的标题样式
                    para.style = 'Heading 4'  # 使用四级标题样式
                    
                    # 确保没有缩进
                    para.paragraph_format.left_indent = Pt(0)
                    para.paragraph_format.first_line_indent = Pt(0)
                    
                    fixed_count += 1
                    continue
            
            # 再尝试匹配三级标题模式
            paragraph_three_level_match = re.search(r'(\d+)\.(\d+)\s+(.*?)(?:\s|$)', text)
            if paragraph_three_level_match:
                # 这是一个包含三级标题模式的段落
                section, subsection, title_text = paragraph_three_level_match.groups()
                
                # 如果这个段落看起来像是一个标题（比如它很短，或者只包含这个标题模式）
                if len(text) < 50 or paragraph_three_level_match.group(0).strip() == text:
                    # 清除段落内容
                    para.clear()
                    
                    # 添加标题文本
                    run = para.add_run(f"{section}.{subsection} {title_text}")
                    
                    # 设置字体
                    font = run.font
                    font.size = Pt(13)  # 三级标题字体大小
                    font.color.rgb = RGBColor(0, 64, 128)  # 统一颜色（蓝色）
                    run.bold = True  # 统一加粗
                    
                    # 设置对齐方式
                    para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                    
                    # 确保使用相同的标题样式
                    para.style = 'Heading 3'  # 使用三级标题样式
                    
                    # 确保没有缩进
                    para.paragraph_format.left_indent = Pt(0)
                    para.paragraph_format.first_line_indent = Pt(0)
                    
                    fixed_count += 1
                    continue
        
        if three_level_match:
            # 这是一个形如"2.3"或"3.1"的三级标题
            section, subsection, title_text = three_level_match.groups()
            
            # 清除段落内容
            para.clear()
            
            # 添加标题文本
            run = para.add_run(f"{section}.{subsection} {title_text}")
            
            # 设置字体
            font = run.font
            font.size = Pt(13)  # 三级标题字体大小
            font.color.rgb = RGBColor(0, 64, 128)  # 统一颜色（蓝色）
            run.bold = True  # 统一加粗
            
            # 设置对齐方式
            para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            
            # 确保使用相同的标题样式
            para.style = 'Heading 3'  # 使用三级标题样式
            
            # 确保没有缩进
            para.paragraph_format.left_indent = Pt(0)
            para.paragraph_format.first_line_indent = Pt(0)
            
            fixed_count += 1
    
    return fixed_count

def html_to_docx(
    html_content: str, 
    title: str = "Document", 
    author: str = "System",
    versions: Optional[List[dict]] = None
) -> BytesIO:
    """
    将HTML内容转换为DOCX格式
    
    Args:
        html_content: HTML格式的文档内容
        title: 文档标题
        author: 文档作者
        versions: 可选的版本历史列表，每个版本是一个包含version, content, comment, created_at的字典
        
    Returns:
        BytesIO: 包含DOCX文件内容的二进制流
    """
    # 将 HTML 内容转换为 DOCX 文件
    doc = Document()
    
    # 预处理HTML，合并列表项后的内容
    def preprocess_html(html_text):
        # 使用正则表达式查找列表项模式并合并后续内容
        # 匹配列表项后跟换行和非列表项内容的模式
        pattern = r'(\d+\.)\s*\n+\s*([^<>\d\n][^<>\n]*)'
        # 替换为列表项和内容在同一行
        processed_html = re.sub(pattern, r'\1 \2', html_text)
        
        # 处理HTML中的有序列表
        soup = BeautifulSoup(processed_html, 'html.parser')
        
        # 查找所有有序列表
        for ol in soup.find_all('ol'):
            # 处理每个列表项
            for li in ol.find_all('li'):
                # 确保列表项中的内容不换行
                # 移除列表项中的段落标签，保留内容
                for p in li.find_all('p'):
                    p.replace_with(p.get_text())
        
        return str(soup)
    
    # 预处理HTML
    preprocessed_html = preprocess_html(html_content)

    # 检查文档是否有h1标题
    soup_check = BeautifulSoup(preprocessed_html, 'html.parser')
    has_h1_title = bool(soup_check.find('h1'))
    
    # 先添加经过处理的 HTML 标题（带上序号）
    html_text_with_numbers = add_numbering_to_headers(preprocessed_html)
    
    # 使用 BeautifulSoup 解析处理后的 HTML
    soup = BeautifulSoup(html_text_with_numbers, 'html.parser')
    
    # 收集所有标题信息，用于后续处理
    headers = []
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(tag.name[1])
        headers.append((tag, level))
    
    # 收集带有strong标签的段落标题
    for p_tag in soup.find_all('p'):
        strong_tags = p_tag.find_all(['strong', 'b'])
        if strong_tags and len(strong_tags) == 1 and strong_tags[0].get_text().strip() == p_tag.get_text().strip():
            # 这是一个带有strong标签的标题段落
            text = p_tag.get_text().strip()
            
            # 检查标题文本是否包含数字序号模式（如"2.1"）
            def extract_numbering_pattern(text):
                # 匹配如 "2.1" 或 "2.1.1" 的模式
                match = re.match(r'^(\d+\.\d+(\.\d+)*)[\s\.]+', text)
                if match:
                    return match.group(1)
                return None
            
            numbering_pattern = extract_numbering_pattern(text)
            
            # 如果标题包含数字序号模式，则根据模式确定级别
            if numbering_pattern:
                # 计算点的数量来确定级别（如"2.1"有1个点，所以是2级标题）
                dots_count = numbering_pattern.count('.')
                level = dots_count + 1
                # 确保级别在合理范围内
                level = max(2, min(level, 6))
            else:
                # 如果没有明确的序号模式，则使用默认逻辑
                # 默认作为三级标题处理
                level = 3
            
            headers.append((p_tag, level))
    
    # 创建样式
    def create_styles(doc):
        # 确保文档中有所需的样式
        styles = doc.styles
        
        # 创建或获取列表样式
        if 'List Bullet' not in styles:
            list_style = styles.add_style('List Bullet', WD_STYLE_TYPE.PARAGRAPH)
        else:
            list_style = styles['List Bullet']
            
        # 创建或获取有序列表样式
        if 'List Number' not in styles:
            list_number_style = styles.add_style('List Number', WD_STYLE_TYPE.PARAGRAPH)
        else:
            list_number_style = styles['List Number']
    
    # 创建样式
    create_styles(doc)

    # 如果没有h1标题，添加传入的title作为文档标题
    if not has_h1_title and title:
        heading = doc.add_heading(title, 0)
        heading.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        # 设置标题字体
        for run in heading.runs:
            run.font.color.rgb = RGBColor(0, 0, 128)  # 深蓝色
            run.font.size = Pt(16)  # 标题字体大小
    
    # 检测是否是数字列表项
    def is_numbered_list_item(text):
        # 检查文本是否以数字和点开头，如 "1." 或 "2."
        return bool(re.match(r'^\d+\.\s*', text.strip()))
    
    # 检测是否是重复序号的列表项，如 "1. 1." 或 "2. 2."
    def is_duplicate_numbered_list_item(text):
        # 检查文本是否匹配 "数字. 数字." 的模式
        return bool(re.match(r'^\d+\.\s+\d+\.\s*', text.strip()))
    
    # 去除文本中已有的序号
    def remove_existing_numbering(text):
        # 去除中文序号，如"一、"、"二、"等
        text = re.sub(r'^[一二三四五六七八九十]+、\s*', '', text)
        # 去除数字序号，如"1."、"2."等
        text = re.sub(r'^\d+\.\d*\s*', '', text)
        return text
    
    # 处理重复序号的列表项
    def process_duplicate_numbered_item(text):
        # 匹配 "数字. 数字." 的模式
        match = re.match(r'^(\d+\.\s+)(\d+\.\s*)(.*)', text.strip())
        if match:
            # 只保留第一个序号
            first_number, second_number, content = match.groups()
            return first_number, content
        return None, text
    
    # 递归处理HTML元素
    def process_element(element, parent_paragraph=None):
        if element.name is None:  # 文本节点
            text = element.strip()
            if text and parent_paragraph:
                # 检查是否是重复序号的列表项
                if is_duplicate_numbered_list_item(text):
                    # 创建普通段落，不使用列表样式
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Pt(18)
                    
                    # 处理重复序号
                    number, content = process_duplicate_numbered_item(text)
                    if number:
                        # 添加序号
                        run = p.add_run(number)
                        run.bold = True
                        # 添加内容
                        p.add_run(content)
                    else:
                        p.add_run(text)
                # 检查是否是普通数字列表项
                elif is_numbered_list_item(text) and parent_paragraph.style.name != 'List Number':
                    # 创建普通段落，不使用列表样式
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Pt(18)
                    
                    # 提取数字和文本内容
                    match = re.match(r'^(\d+\.\s*)(.*)', text)
                    if match:
                        number, content = match.groups()
                        # 添加序号
                        run = p.add_run(number)
                        run.bold = True
                        # 添加内容
                        p.add_run(content)
                else:
                    parent_paragraph.add_run(text)
            return
        
        # 处理标题
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(element.name[1])
            p = doc.add_paragraph()
            p.style = f'Heading {min(level, 9)}'  # Word最多支持9级标题
            
            # 添加标题文本
            run = p.add_run(element.get_text().strip())
            
            # 设置字体
            font = run.font
            font.size = Pt(16 - level)  # 根据级别调整字体大小
            
            # 设置颜色
            if level == 1:
                font.color.rgb = RGBColor(0, 0, 128)  # 深蓝色
            elif level == 2:
                font.color.rgb = RGBColor(0, 64, 128)  # 蓝色
            
            # 一级标题居中，其他左对齐
            if level == 1:
                p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            else:
                p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            
            return
        
        # 处理段落
        if element.name == 'p':
            text = element.get_text().strip()
            
            # 检查段落中是否包含strong标签，且strong标签内容符合标题格式
            strong_tags = element.find_all(['strong', 'b'])
            if strong_tags and len(strong_tags) == 1 and strong_tags[0].get_text().strip() == text:
                # 这是一个带有strong标签的标题段落
                p = doc.add_paragraph()
                
                # 根据标题级别设置样式
                # 查找该段落对应的标题级别
                level = 3  # 默认值
                for tag, lvl in headers:
                    if tag == element:
                        level = lvl
                        break
                
                p.style = f'Heading {min(level, 9)}'  # Word最多支持9级标题
                
                # 添加标题文本
                run = p.add_run(text)
                
                # 设置字体
                font = run.font
                font.size = Pt(16 - level)  # 根据级别调整字体大小
                
                # 设置颜色
                if level == 1:
                    font.color.rgb = RGBColor(0, 0, 128)  # 深蓝色
                elif level == 2:
                    font.color.rgb = RGBColor(0, 64, 128)  # 蓝色
                
                # 一级标题居中，其他左对齐
                if level == 1:
                    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                else:
                    p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                
                return
            
            # 检查是否是重复序号的列表项
            if is_duplicate_numbered_list_item(text):
                # 创建普通段落，不使用列表样式
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                
                # 处理重复序号
                number, content = process_duplicate_numbered_item(text)
                if number:
                    # 添加序号
                    run = p.add_run(number)
                    run.bold = True
                    # 添加内容
                    p.add_run(content)
                else:
                    p.add_run(text)
            # 检查是否是普通数字列表项
            elif is_numbered_list_item(text):
                # 创建普通段落，不使用列表样式
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                
                # 提取数字和文本内容
                match = re.match(r'^(\d+\.\s*)(.*)', text)
                if match:
                    number, content = match.groups()
                    # 添加序号
                    run = p.add_run(number)
                    run.bold = True
                    # 添加内容
                    p.add_run(content)
            else:
                # 普通段落
                p = doc.add_paragraph()
                for child in element.children:
                    process_element(child, p)
            return
        
        # 处理加粗
        if element.name == 'strong' or element.name == 'b':
            if parent_paragraph:
                run = parent_paragraph.add_run(element.get_text().strip())
                run.bold = True
            return
        
        # 处理斜体
        if element.name == 'em' or element.name == 'i':
            if parent_paragraph:
                run = parent_paragraph.add_run(element.get_text().strip())
                run.italic = True
            return
        
        # 处理下划线
        if element.name == 'u':
            if parent_paragraph:
                run = parent_paragraph.add_run(element.get_text().strip())
                run.underline = True
            return
        
        # 处理无序列表
        if element.name == 'ul':
            for li in element.find_all('li', recursive=False):
                # 创建普通段落，不使用列表样式
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                
                # 添加项目符号
                run = p.add_run('• ')
                run.bold = True
                
                # 处理列表项内容
                for child in li.children:
                    process_element(child, p)
            return
        
        # 处理有序列表
        if element.name == 'ol':
            for i, li in enumerate(element.find_all('li', recursive=False), 1):
                # 创建普通段落，不使用列表样式
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                
                # 添加序号
                run = p.add_run(f'{i}. ')
                run.bold = True
                
                # 处理列表项内容
                for child in li.children:
                    process_element(child, p)
            return
        
        # 处理其他元素的子元素
        for child in element.children:
            process_element(child, parent_paragraph)
    
    # 处理HTML主体
    for element in soup.body.children if soup.body else soup.children:
        if isinstance(element, str):
            text = element.strip()
            if text:
                # 检查是否是重复序号的列表项
                if is_duplicate_numbered_list_item(text):
                    # 创建普通段落，不使用列表样式
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Pt(18)
                    
                    # 处理重复序号
                    number, content = process_duplicate_numbered_item(text)
                    if number:
                        # 添加序号
                        run = p.add_run(number)
                        run.bold = True
                        # 添加内容
                        p.add_run(content)
                    else:
                        p.add_run(text)
                # 检查是否是普通数字列表项
                elif is_numbered_list_item(text):
                    # 创建普通段落，不使用列表样式
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Pt(18)
                    
                    # 提取数字和文本内容
                    match = re.match(r'^(\d+\.\s*)(.*)', text)
                    if match:
                        number, content = match.groups()
                        # 添加序号
                        run = p.add_run(number)
                        run.bold = True
                        # 添加内容
                        p.add_run(content)
                else:
                    # 普通段落
                    p = doc.add_paragraph()
                    run = p.add_run(text)
                    font = run.font
                    font.size = Pt(10.5)  # 正文字体大小
        else:
            process_element(element)
    
    # 修复文档中的标题格式
    fix_document_numbering(doc)
    
    # 如果需要添加版本历史
    if versions:
        doc.add_page_break()
        history_heading = doc.add_heading("版本历史", 1)
        history_heading.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        
        for v in versions:
            p = doc.add_paragraph()
            p.add_run(f"版本 {v['version']} - {v['created_at']}").bold = True
            if v.get('comment'):
                p.add_run(f" - {v['comment']}")
    
    # 将文档保存到内存中
    docx_bytes = BytesIO()
    doc.save(docx_bytes)
    docx_bytes.seek(0)
    
    return docx_bytes

def html_to_pdf(
    html_content: str, 
    title: str = "Document", 
    author: str = "System",
    versions: Optional[List[dict]] = None
) -> BytesIO:
    """
    将HTML内容转换为PDF格式
    
    Args:
        html_content: HTML格式的文档内容
        title: 文档标题
        author: 文档作者
        versions: 可选的版本历史列表，每个版本是一个包含version, content, comment, created_at的字典
        
    Returns:
        BytesIO: 包含PDF文件内容的二进制流
    """
    try:
        import pdfkit
        from io import BytesIO
        import tempfile
        
        # 预处理HTML，合并列表项后的内容
        def preprocess_html(html_text):
            # 使用正则表达式查找列表项模式并合并后续内容
            # 匹配列表项后跟换行和非列表项内容的模式
            pattern = r'(\d+\.)\s*\n+\s*([^<>\d\n][^<>\n]*)'
            # 替换为列表项和内容在同一行
            processed_html = re.sub(pattern, r'\1 \2', html_text)
            
            # 处理HTML中的有序列表
            soup = BeautifulSoup(processed_html, 'html.parser')
            
            # 查找所有有序列表
            for ol in soup.find_all('ol'):
                # 处理每个列表项
                for li in ol.find_all('li'):
                    # 确保列表项中的内容不换行
                    # 移除列表项中的段落标签，保留内容
                    for p in li.find_all('p'):
                        p.replace_with(p.get_text())
            
            return str(soup)
        
        # 预处理HTML
        preprocessed_html = preprocess_html(html_content)
        
        # 添加标题编号
        html_text_with_numbers = add_numbering_to_headers(preprocessed_html)
        
        # 检查文档是否有h1标题
        soup_check = BeautifulSoup(html_text_with_numbers, 'html.parser')
        has_h1_title = bool(soup_check.find('h1'))
        
        # 如果没有h1标题，添加传入的title作为文档标题
        if not has_h1_title and title:
            title_html = f"<h1 style='text-align:center;color:#000080;'>{title}</h1>"
            html_text_with_numbers = title_html + html_text_with_numbers
        
        # 添加版本历史（如果需要）
        if versions:
            versions_html = "<div style='page-break-before: always;'>"
            versions_html += "<h1 style='text-align:center;'>版本历史</h1>"
            for v in versions:
                versions_html += f"<p><strong>版本 {v['version']} - {v['created_at']}</strong>"
                if v.get('comment'):
                    versions_html += f" - {v['comment']}"
                versions_html += "</p>"
            versions_html += "</div>"
            html_text_with_numbers += versions_html
        
        # 添加基本样式
        css_text = """
        body {
            font-family: SimSun, Arial, sans-serif;
            font-size: 10.5pt;
            line-height: 1.5;
            margin: 2cm;
        }
        h1 {
            font-size: 16pt;
            color: #000080;
            text-align: center;
            margin-top: 24pt;
            margin-bottom: 12pt;
        }
        h2 {
            font-size: 14pt;
            color: #004080;
            margin-top: 18pt;
            margin-bottom: 9pt;
        }
        h3, h4, h5, h6 {
            font-size: 12pt;
            margin-top: 12pt;
            margin-bottom: 6pt;
        }
        p {
            margin-top: 6pt;
            margin-bottom: 6pt;
        }
        ol, ul {
            margin-left: 18pt;
        }
        li {
            margin-bottom: 6pt;
        }
        strong {
            font-weight: bold;
        }
        em {
            font-style: italic;
        }
        """
        
        # 创建完整的HTML文档
        complete_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>{title}</title>
            <style>
                {css_text}
            </style>
        </head>
        <body>
            {html_text_with_numbers}
        </body>
        </html>
        """
        
        # 配置pdfkit选项
        options = {
            'page-size': 'A4',
            'margin-top': '2cm',
            'margin-right': '2cm',
            'margin-bottom': '2cm',
            'margin-left': '2cm',
            'encoding': 'UTF-8',
            'no-outline': None,
            'quiet': ''
        }
        
        # 创建临时文件来保存PDF
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf_path = temp_pdf.name
        
        # 生成PDF到临时文件
        pdfkit.from_string(complete_html, temp_pdf_path, options=options)
        
        # 读取临时文件到内存
        with open(temp_pdf_path, 'rb') as f:
            pdf_bytes = BytesIO(f.read())
        
        # 删除临时文件
        import os
        os.unlink(temp_pdf_path)
        
        # 重置文件指针位置
        pdf_bytes.seek(0)
        return pdf_bytes
        
    except Exception as e:
        # 如果pdfkit失败，记录错误并抛出异常
        import logging
        logging.error(f"PDF转换失败: {str(e)}")
        raise Exception(f"PDF转换失败: {str(e)}")