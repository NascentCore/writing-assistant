"""大纲相关的工具函数"""

def build_paragraph_key(paragraph, siblings_dict, parent_dict):
    """递归构建段落的层级key
    
    Args:
        paragraph: 段落对象，必须包含 id 和 parent_id 属性
        siblings_dict: Dict[Optional[int], List[int]] 父ID到子段落ID列表的映射
        parent_dict: Dict[int, Any] 段落ID到段落对象的映射
        
    Returns:
        str: 形如 "1" 或 "1-2" 或 "1-2-3" 的层级key
    """
    if not paragraph.parent_id:
        # 顶级段落
        siblings = siblings_dict.get(None, [])
        return str(siblings.index(paragraph.id) + 1)
    
    # 获取父段落的key
    parent_key = build_paragraph_key(parent_dict[paragraph.parent_id], siblings_dict, parent_dict)
    
    # 获取当前段落在同级中的序号
    siblings = siblings_dict.get(paragraph.parent_id, [])
    current_index = siblings.index(paragraph.id) + 1
    
    return f"{parent_key}-{current_index}" 

def build_paragraph_data(paragraph, level=1, parent_id=None):
    """
    构建段落数据，用于保存到数据库或API响应
    
    Args:
        paragraph: 段落对象，必须包含必要的属性
        level: 段落级别，默认为1
        parent_id: 父段落ID，默认为None
        
    Returns:
        Dict: 包含段落数据的字典
    """
    # 如果输入是数据库模型对象
    if hasattr(paragraph, 'id'):
        return {
            "id": paragraph.id,
            "title": paragraph.title,
            "description": paragraph.description,
            "level": paragraph.level,
            "parent_id": paragraph.parent_id,
            "count_style": paragraph.count_style.value if hasattr(paragraph, 'count_style') and paragraph.count_style else None,
            "reference_status": paragraph.reference_status if hasattr(paragraph, 'reference_status') else 0
        }
    # 如果输入是字典
    elif isinstance(paragraph, dict):
        para_data = {
            "title": paragraph.get("title", ""),
            "description": paragraph.get("description", ""),
            "level": paragraph.get("level", level),
            "parent_id": parent_id
        }
        
        # 添加可选字段
        if "count_style" in paragraph:
            para_data["count_style"] = paragraph["count_style"]
        if "reference_status" in paragraph:
            para_data["reference_status"] = paragraph["reference_status"]
            
        return para_data
    # 如果是其他类型（如docx的Paragraph对象）
    else:
        return {
            "title": paragraph.text if hasattr(paragraph, "text") else "",
            "description": "",
            "level": level,
            "parent_id": parent_id
        }

def build_paragraph_response(paragraph, siblings_dict=None, paragraphs_dict=None, references_dict=None, reference_status_enum=None):
    """构建段落API响应数据
    
    Args:
        paragraph: 段落对象，必须包含id, title, description, level, reference_status等属性
        siblings_dict: 父ID到子段落ID列表的映射，用于构建key
        paragraphs_dict: 段落ID到段落对象的映射，用于构建key
        references_dict: 段落ID到引用列表的映射
        reference_status_enum: 引用状态枚举类
        
    Returns:
        Dict: 包含段落数据的字典，用于API响应
    """
    data = {
        "id": str(paragraph.id),
        "title": paragraph.title,
        "description": paragraph.description,
        "level": paragraph.level
    }
    
    # 添加key，如果提供了必要的字典
    if siblings_dict and paragraphs_dict:
        data["key"] = build_paragraph_key(paragraph, siblings_dict, paragraphs_dict)
    
    # 添加引用状态
    if hasattr(paragraph, "reference_status"):
        if reference_status_enum:
            data["reference_status"] = reference_status_enum(paragraph.reference_status).value
        else:
            data["reference_status"] = paragraph.reference_status
    
    # 只有1级段落才有count_style
    if paragraph.level == 1 and hasattr(paragraph, "count_style") and paragraph.count_style:
        data["count_style"] = paragraph.count_style.value
    
    # 只有1级段落才有引用
    if paragraph.level == 1:
        data["references"] = []
        # 如果提供了引用字典，则添加引用
        if references_dict and paragraph.id in references_dict:
            data["references"] = references_dict[paragraph.id]
    
    return data 