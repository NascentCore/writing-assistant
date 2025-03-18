import requests
from bs4 import BeautifulSoup
from langchain_community.document_loaders import AsyncHtmlLoader
from langchain_community.document_transformers import Html2TextTransformer

html2text = Html2TextTransformer()

def baidu_search(query: str, top_k: int = 3):
    # 模拟请求百度搜索
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"}
    search_url = f"https://www.baidu.com/s?wd={query}"

    response = requests.get(search_url, headers=headers)
    if response.status_code != 200:
        raise Exception("百度搜索请求失败")

    soup = BeautifulSoup(response.text, "lxml")

    # 提取搜索结果（这里我们假设百度的搜索结果有一定的结构）
    results = []
    for idx, item in enumerate(soup.select(".result.c-container"), 1):  # 百度搜索结果的标识符
        if idx > top_k:
            break
        title = item.select_one("h3").get_text() if item.select_one("h3") else ""
        link = item.select_one("a")["href"] if item.select_one("a") else ""
        description = item.select_one(".c-abstract").get_text() if item.select_one(".c-abstract") else ""
        results.append({
            "title": title,
            "link": link,
            "description": description
        })

    # 提取链接并加载网页内容
    urls = [res["link"] for res in results]
    loader = AsyncHtmlLoader(urls)
    docs = loader.load()

    # 转换网页内容为纯文本
    for doc in docs:
        if doc.page_content == '':
            doc.page_content = doc.metadata.get('description', '')

    docs_transformed = html2text.transform_documents(docs)

    # 组装搜索内容
    search_contents = []
    for i, doc in enumerate(docs_transformed):
        title_content = results[i]["title"]
        search_contents.append(f">>>>>>>>>>>>>>>>>>>>以下是标题为<h1>{title_content}</h1>的网页内容\n{doc.page_content}\n<<<<<<<<<<<<<<<<<以上是标题为<h1>{title_content}</h1>的网页内容\n")

    return "\n\n".join([doc for doc in search_contents])

if __name__ == "__main__":
    result = baidu_search("临安区人口数量，农业人口比例?")
    print(result)