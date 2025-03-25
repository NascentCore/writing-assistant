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
            return str(index + 1)
    
    # 清除所有标题标签的内容中的编号
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        original_text = tag.get_text().strip()
        # 去除现有的编号（中文编号和数字编号）
        clean_text = re.sub(r'^[\d一二三四五六七八九十]+[\.、][\d一二三四五六七八九十\.、]*\s*', '', original_text)
        clean_text = re.sub(r'^\d+(\.\d+)+\s+', '', clean_text)
        tag.clear()
        tag.append(clean_text)  # 保存清理后的文本
    
    # 按文档顺序收集所有标题标签
    all_headers = []
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(tag.name[1])
        text = tag.get_text().strip()
        all_headers.append((tag, level, text))
    
    # 用于跟踪标题编号的计数器
    h2_counter = 0  # 二级标题计数器
    h3_counters = {}  # 每个二级标题下的三级标题计数器
    h4_counters = {}  # 每个三级标题下的四级标题计数器
    h5_counters = {}  # 每个四级标题下的五级标题计数器
    
    # 当前标题的父标题ID
    current_h2_id = None
    current_h3_id = None
    current_h4_id = None
    
    # 为每个标题生成编号
    for i, (tag, level, text) in enumerate(all_headers):
        if level == 1:
            # 一级标题不加编号
            continue
        elif level == 2:
            # 二级标题：一、二、三...
            h2_counter += 1
            current_h2_id = h2_counter
            # 重置低级标题计数器
            h3_counters[current_h2_id] = 0
            
            # 生成编号
            numbering = f'{get_chinese_number(h2_counter-1)}、'
            tag.clear()
            tag.append(f"{numbering}{text}")
        
        elif level == 3:
            # 三级标题：1.1, 1.2, 2.1...
            if current_h2_id is None:
                current_h2_id = 1
                h3_counters[current_h2_id] = 0
            
            h3_counters[current_h2_id] += 1
            current_h3_id = f"{current_h2_id}.{h3_counters[current_h2_id]}"
            # 重置四级标题计数器
            h4_counters[current_h3_id] = 0
            
            # 生成编号
            numbering = f'{current_h2_id}.{h3_counters[current_h2_id]}'
            tag.clear()
            tag.append(f"{numbering} {text}")
        
        elif level == 4:
            # 四级标题：1.1.1, 1.1.2, 1.2.1...
            if current_h3_id is None:
                if current_h2_id is None:
                    current_h2_id = 1
                    h3_counters[current_h2_id] = 0
                h3_counters[current_h2_id] += 1
                current_h3_id = f"{current_h2_id}.{h3_counters[current_h2_id]}"
                h4_counters[current_h3_id] = 0
            
            h4_counters[current_h3_id] += 1
            current_h4_id = f"{current_h3_id}.{h4_counters[current_h3_id]}"
            # 重置五级标题计数器
            h5_counters[current_h4_id] = 0
            
            # 生成编号
            numbering = f'{current_h3_id}.{h4_counters[current_h3_id]}'
            tag.clear()
            tag.append(f"{numbering} {text}")
        
        elif level == 5:
            # 五级标题：1.1.1.1, 1.1.1.2...
            if current_h4_id is None:
                if current_h3_id is None:
                    if current_h2_id is None:
                        current_h2_id = 1
                        h3_counters[current_h2_id] = 0
                    h3_counters[current_h2_id] += 1
                    current_h3_id = f"{current_h2_id}.{h3_counters[current_h2_id]}"
                    h4_counters[current_h3_id] = 0
                h4_counters[current_h3_id] += 1
                current_h4_id = f"{current_h3_id}.{h4_counters[current_h3_id]}"
                h5_counters[current_h4_id] = 0
            
            h5_counters[current_h4_id] += 1
            
            # 生成编号
            numbering = f'{current_h4_id}.{h5_counters[current_h4_id]}'
            tag.clear()
            tag.append(f"{numbering} {text}")
    
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
    total_paragraphs = len(doc.paragraphs)
    
    # 遍历所有段落
    for i, para in enumerate(doc.paragraphs):
        # 获取标题文本
        text = para.text.strip()
        
        # 检查是否是形如"1.1.1.1"的四级标题 (四个数字)
        four_level_match = re.match(r'^(\d+)\.(\d+)\.(\d+)\.(\d+)[\s\.]*(.*)$', text)
        if four_level_match:
            section, subsection, subsubsection, subsubsubsection, title_text = four_level_match.groups()
            
            # 清除段落内容
            para.clear()
            
            # 添加标题文本
            run = para.add_run(f"{section}.{subsection}.{subsubsection}.{subsubsubsection} {title_text}")
            
            # 设置字体
            font = run.font
            font.size = Pt(12)
            font.color.rgb = RGBColor(0, 64, 128)
            run.bold = True
            
            # 设置对齐方式
            para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            
            # 使用四级标题样式
            para.style = 'Heading 4'
            
            fixed_count += 1
            continue

        # 检查是否是形如"1.1.1"的三级标题 (三个数字)
        three_level_match = re.match(r'^(\d+)\.(\d+)\.(\d+)[\s\.]*(.*)$', text)
        if three_level_match and not four_level_match:
            section, subsection, subsubsection, title_text = three_level_match.groups()
            
            # 清除段落内容
            para.clear()
            
            # 添加标题文本
            run = para.add_run(f"{section}.{subsection}.{subsubsection} {title_text}")
            
            # 设置字体
            font = run.font
            font.size = Pt(13)
            font.color.rgb = RGBColor(0, 64, 128)
            run.bold = True
            
            # 设置对齐方式
            para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            
            # 使用三级标题样式
            para.style = 'Heading 3'
            
            fixed_count += 1
            continue
        
        # 检查是否是形如"2.3"或"3.1"的二级标题
        two_level_match = re.match(r'^(\d+)\.(\d+)[\s\.]*(.*)$', text)
        
        # 也检查中文标题格式，如"二.三"
        if not two_level_match:
            chinese_match = re.match(r'^([一二三四五六七八九十]+)[\.．。]([一二三四五六七八九十]+)[\s\.]*(.*)$', text)
            if chinese_match:
                section, subsection, title_text = chinese_match.groups()
                para.clear()
                run = para.add_run(f"{section}.{subsection} {title_text}")
                
                font = run.font
                font.size = Pt(13)
                font.color.rgb = RGBColor(0, 64, 128)
                run.bold = True
                
                para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                para.style = 'Heading 2'
                
                para.paragraph_format.left_indent = Pt(0)
                para.paragraph_format.first_line_indent = Pt(0)
                
                fixed_count += 1
                continue
        
        if two_level_match:
            section, subsection, title_text = two_level_match.groups()
            para.clear()
            run = para.add_run(f"{section}.{subsection} {title_text}")
            
            font = run.font
            font.size = Pt(13)
            font.color.rgb = RGBColor(0, 64, 128)
            run.bold = True
            
            para.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            para.style = 'Heading 2'
            
            para.paragraph_format.left_indent = Pt(0)
            para.paragraph_format.first_line_indent = Pt(0)
            
            fixed_count += 1
    
    return fixed_count

def html_to_docx(
    html_content: str, 
    title: str = "Document", 
    author: str = "System",
    versions: Optional[List[dict]] = None,
    add_numbering: bool = True
) -> BytesIO:
    """
    将HTML内容转换为DOCX格式
    
    Args:
        html_content: HTML格式的文档内容
        title: 文档标题
        author: 文档作者
        versions: 可选的版本历史列表，每个版本是一个包含version, content, comment, created_at的字典
        add_numbering: 是否为标题添加序号，默认为True
        
    Returns:
        BytesIO: 包含DOCX文件内容的二进制流
    """
    # 将 HTML 内容转换为 DOCX 文件
    doc = Document()
    
    # 预处理HTML，合并列表项后的内容
    def preprocess_html(html_text):
        # 使用正则表达式查找列表项模式并合并后续内容
        pattern = r'(\d+\.)\s*\n+\s*([^<>\d\n][^<>\n]*)'
        processed_html = re.sub(pattern, r'\1 \2', html_text)
        
        # 处理HTML中的有序列表
        soup = BeautifulSoup(processed_html, 'html.parser')
        for ol in soup.find_all('ol'):
            for li in ol.find_all('li'):
                for p in li.find_all('p'):
                    p.replace_with(p.get_text())
        
        return str(soup)
    
    # 预处理HTML
    preprocessed_html = preprocess_html(html_content)
    
    # 检查文档是否有h1标题
    soup_check = BeautifulSoup(preprocessed_html, 'html.parser')
    has_h1_title = bool(soup_check.find('h1'))
    
    # 根据add_numbering参数决定是否添加序号
    if add_numbering:
        html_text_with_numbers = add_numbering_to_headers(preprocessed_html)
    else:
        html_text_with_numbers = preprocessed_html
    
    # 使用 BeautifulSoup 解析处理后的 HTML
    soup = BeautifulSoup(html_text_with_numbers, 'html.parser')
    
    # 如果没有h1标题，添加传入的title作为文档标题
    if not has_h1_title and title:
        heading = doc.add_heading(title, 0)
        heading.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
        for run in heading.runs:
            run.font.color.rgb = RGBColor(0, 0, 128)
            run.font.size = Pt(16)
    
    # 收集所有标题信息
    headers = []
    for tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
        level = int(tag.name[1])
        headers.append((tag, level))
    
    # 收集带有strong标签的段落标题
    for p_tag in soup.find_all('p'):
        strong_tags = p_tag.find_all(['strong', 'b'])
        if strong_tags and len(strong_tags) == 1 and strong_tags[0].get_text().strip() == p_tag.get_text().strip():
            text = p_tag.get_text().strip()
            
            def extract_numbering_pattern(text):
                match = re.match(r'^(\d+\.\d+(\.\d+)*)[\s\.]+', text)
                if match:
                    return match.group(1)
                return None
            
            numbering_pattern = extract_numbering_pattern(text)
            level = 3  # 默认三级标题
            
            if numbering_pattern:
                dots_count = numbering_pattern.count('.')
                level = dots_count + 1
                level = max(2, min(level, 6))
            
            headers.append((p_tag, level))
    
    # 创建样式
    def create_styles(doc):
        styles = doc.styles
        if 'List Bullet' not in styles:
            styles.add_style('List Bullet', WD_STYLE_TYPE.PARAGRAPH)
        if 'List Number' not in styles:
            styles.add_style('List Number', WD_STYLE_TYPE.PARAGRAPH)
    
    create_styles(doc)
    
    # 辅助函数定义
    def is_numbered_list_item(text):
        return bool(re.match(r'^\d+\.\s*', text.strip()))
    
    def is_duplicate_numbered_list_item(text):
        return bool(re.match(r'^\d+\.\s+\d+\.\s*', text.strip()))
    
    def process_duplicate_numbered_item(text):
        match = re.match(r'^(\d+\.\s+)(\d+\.\s*)(.*)', text.strip())
        if match:
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
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Pt(18)
                    
                    number, content = process_duplicate_numbered_item(text)
                    if number:
                        run = p.add_run(number)
                        run.bold = True
                        p.add_run(content)
                    else:
                        p.add_run(text)
                # 检查是否是普通数字列表项
                elif is_numbered_list_item(text) and parent_paragraph.style.name != 'List Number':
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Pt(18)
                    
                    match = re.match(r'^(\d+\.\s*)(.*)', text)
                    if match:
                        number, content = match.groups()
                        run = p.add_run(number)
                        run.bold = True
                        p.add_run(content)
                else:
                    parent_paragraph.add_run(text)
            return
        
        # 处理标题
        if element.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            level = int(element.name[1])
            p = doc.add_paragraph()
            p.style = f'Heading {min(level, 9)}'
            
            run = p.add_run(element.get_text().strip())
            
            font = run.font
            font.size = Pt(16 - level)
            
            if level == 1:
                font.color.rgb = RGBColor(0, 0, 128)
                p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
            elif level == 2:
                font.color.rgb = RGBColor(0, 64, 128)
                p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            else:
                p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
            
            return
        
        # 处理段落
        if element.name == 'p':
            text = element.get_text().strip()
            
            # 检查段落中是否包含strong标签作为标题
            strong_tags = element.find_all(['strong', 'b'])
            if strong_tags and len(strong_tags) == 1 and strong_tags[0].get_text().strip() == text:
                p = doc.add_paragraph()
                
                level = 3  # 默认值
                for tag, lvl in headers:
                    if tag == element:
                        level = lvl
                        break
                
                p.style = f'Heading {min(level, 9)}'
                run = p.add_run(text)
                
                font = run.font
                font.size = Pt(16 - level)
                
                if level == 1:
                    font.color.rgb = RGBColor(0, 0, 128)
                    p.alignment = WD_PARAGRAPH_ALIGNMENT.CENTER
                elif level == 2:
                    font.color.rgb = RGBColor(0, 64, 128)
                    p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                else:
                    p.alignment = WD_PARAGRAPH_ALIGNMENT.LEFT
                
                return
            
            # 处理列表项
            if is_duplicate_numbered_list_item(text):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                
                number, content = process_duplicate_numbered_item(text)
                if number:
                    run = p.add_run(number)
                    run.bold = True
                    p.add_run(content)
                else:
                    p.add_run(text)
            elif is_numbered_list_item(text):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                
                match = re.match(r'^(\d+\.\s*)(.*)', text)
                if match:
                    number, content = match.groups()
                    run = p.add_run(number)
                    run.bold = True
                    p.add_run(content)
            else:
                p = doc.add_paragraph()
                for child in element.children:
                    process_element(child, p)
            return
        
        # 处理格式化标签
        if element.name in ['strong', 'b']:
            if parent_paragraph:
                run = parent_paragraph.add_run(element.get_text().strip())
                run.bold = True
            return
        
        if element.name in ['em', 'i']:
            if parent_paragraph:
                run = parent_paragraph.add_run(element.get_text().strip())
                run.italic = True
            return
        
        if element.name == 'u':
            if parent_paragraph:
                run = parent_paragraph.add_run(element.get_text().strip())
                run.underline = True
            return
        
        # 处理列表
        if element.name == 'ul':
            for li in element.find_all('li', recursive=False):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                run = p.add_run('• ')
                run.bold = True
                for child in li.children:
                    process_element(child, p)
            return
        
        if element.name == 'ol':
            for i, li in enumerate(element.find_all('li', recursive=False), 1):
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Pt(18)
                run = p.add_run(f'{i}. ')
                run.bold = True
                for child in li.children:
                    process_element(child, p)
            return
        
        # 处理其他元素
        for child in element.children:
            process_element(child, parent_paragraph)
    
    # 处理HTML主体
    for element in soup.body.children if soup.body else soup.children:
        if isinstance(element, str):
            text = element.strip()
            if text:
                if is_duplicate_numbered_list_item(text):
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Pt(18)
                    number, content = process_duplicate_numbered_item(text)
                    if number:
                        run = p.add_run(number)
                        run.bold = True
                        p.add_run(content)
                    else:
                        p.add_run(text)
                elif is_numbered_list_item(text):
                    p = doc.add_paragraph()
                    p.paragraph_format.left_indent = Pt(18)
                    match = re.match(r'^(\d+\.\s*)(.*)', text)
                    if match:
                        number, content = match.groups()
                        run = p.add_run(number)
                        run.bold = True
                        p.add_run(content)
                else:
                    p = doc.add_paragraph()
                    run = p.add_run(text)
                    font = run.font
                    font.size = Pt(10.5)
        else:
            process_element(element)
    
    # 修复文档中的标题格式
    fixed_count = fix_document_numbering(doc)
    
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
    versions: Optional[List[dict]] = None,
    add_numbering: bool = True
) -> BytesIO:
    """
    将HTML内容转换为PDF格式
    
    Args:
        html_content: HTML格式的文档内容
        title: 文档标题
        author: 文档作者
        versions: 可选的版本历史列表，每个版本是一个包含version, content, comment, created_at的字典
        add_numbering: 是否为标题添加序号，默认为True
        
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
            pattern = r'(\d+\.)\s*\n+\s*([^<>\d\n][^<>\n]*)'
            processed_html = re.sub(pattern, r'\1 \2', html_text)
            
            # 处理HTML中的有序列表
            soup = BeautifulSoup(processed_html, 'html.parser')
            for ol in soup.find_all('ol'):
                for li in ol.find_all('li'):
                    for p in li.find_all('p'):
                        p.replace_with(p.get_text())
            
            return str(soup)
        
        # 预处理HTML
        preprocessed_html = preprocess_html(html_content)
        
        # 检查文档是否有h1标题
        soup_check = BeautifulSoup(preprocessed_html, 'html.parser')
        has_h1_title = bool(soup_check.find('h1'))
        
        # 根据add_numbering参数决定是否添加序号
        if add_numbering:
            html_text_with_numbers = add_numbering_to_headers(preprocessed_html)
        else:
            html_text_with_numbers = preprocessed_html
        
        # 如果没有h1标题，添加传入的title作为文档标题
        if not has_h1_title and title:
            title_html = f"<h1 style='text-align:center;color:#000080;font-size:16pt;'>{title}</h1>"
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
            text-align: left;
        }
        h3 {
            font-size: 13pt;
            color: #004080;
            margin-top: 12pt;
            margin-bottom: 6pt;
            text-align: left;
        }
        h4 {
            font-size: 12pt;
            color: #004080;
            margin-top: 12pt;
            margin-bottom: 6pt;
            text-align: left;
        }
        h5, h6 {
            font-size: 11pt;
            color: #004080;
            margin-top: 12pt;
            margin-bottom: 6pt;
            text-align: left;
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
        .numbered-list {
            margin-left: 18pt;
        }
        .numbered-list-item {
            font-weight: bold;
        }
        .numbered-list-content {
            font-weight: normal;
        }
        """
        
        # 处理列表项的样式
        soup = BeautifulSoup(html_text_with_numbers, 'html.parser')
        
        # 处理数字列表项
        def is_numbered_list_item(text):
            return bool(re.match(r'^\d+\.\s*', text.strip()))
        
        def is_duplicate_numbered_list_item(text):
            return bool(re.match(r'^\d+\.\s+\d+\.\s*', text.strip()))
        
        # 处理段落中的列表项
        for p in soup.find_all('p'):
            text = p.get_text().strip()
            if is_duplicate_numbered_list_item(text):
                match = re.match(r'^(\d+\.\s+)(\d+\.\s*)(.*)', text.strip())
                if match:
                    first_number, second_number, content = match.groups()
                    p['class'] = p.get('class', []) + ['numbered-list']
                    p.clear()
                    number_span = soup.new_tag('span')
                    number_span['class'] = ['numbered-list-item']
                    number_span.string = first_number
                    p.append(number_span)
                    content_span = soup.new_tag('span')
                    content_span['class'] = ['numbered-list-content']
                    content_span.string = content
                    p.append(content_span)
            elif is_numbered_list_item(text):
                match = re.match(r'^(\d+\.\s*)(.*)', text)
                if match:
                    number, content = match.groups()
                    p['class'] = p.get('class', []) + ['numbered-list']
                    p.clear()
                    number_span = soup.new_tag('span')
                    number_span['class'] = ['numbered-list-item']
                    number_span.string = number
                    p.append(number_span)
                    content_span = soup.new_tag('span')
                    content_span['class'] = ['numbered-list-content']
                    content_span.string = content
                    p.append(content_span)
        
        html_text_with_numbers = str(soup)
        
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