from app.services.langchain_service import OutlineGenerator

# 这是一个简单的测试脚本，用于直接测试OutlineGenerator类
# 注意：这不是单元测试文件，正式的单元测试在backend/tests/目录下

if __name__ == "__main__":
    outline_generator = OutlineGenerator()
    print(outline_generator.generate_outline("写一篇关于AI的文章"))