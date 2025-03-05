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