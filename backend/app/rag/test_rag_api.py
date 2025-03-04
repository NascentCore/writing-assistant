import asyncio
from backend.app.rag.rag_api import RagAPI

async def test_chat():
    # 初始化RAG API客户端
    rag_client = RagAPI(base_url="http://rag.llm.sxwl.ai:30003/api")
    
    # 测试参数
    kb_ids = ["KBc6ee41b73bea42adacf11bf282d9fd28_240625"]  # 替换为实际的知识库ID
    question = "公路跨海建设有哪些主要规定"
    
    try:
        # 调用chat接口
        response_iterator = rag_client.chat(
            kb_ids=kb_ids,
            question=question,
            streaming=True,
            history=[],
            networking=False,
            product_source="saas",
            rerank=False,
            only_need_search_results=False,
            hybrid_search=False,
            max_token=512,
            api_base="https://ark.cn-beijing.volces.com/api/v3/",
            api_key="ff9ed2dd-cdf0-40d4-b4ec-d3aa19e2bd0b",
            model="ep-20241227141027-d7lnk",
            api_context_length=4096,
            chunk_size=800,
            top_p=1.0,
            top_k=30,
            temperature=0.5,
            user_id="zzp"
        )
        
        # 处理流式响应
        full_response = ""
        for chunk in response_iterator:
            if "choices" in chunk and len(chunk["choices"]) > 0:
                content = chunk["choices"][0].get("delta", {}).get("content", "")
                if content:
                    print(content, end="", flush=True)  # 实时打印内容
                    full_response += content
            
        print("\n\n完整响应:", full_response)
        
    except Exception as e:
        print(f"发生错误: {str(e)}")

if __name__ == "__main__":
    # 运行测试
    asyncio.run(test_chat()) 