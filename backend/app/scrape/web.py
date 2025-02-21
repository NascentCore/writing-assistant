from typing import Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
import shortuuid
from sqlalchemy.orm import Session
from sqlalchemy import select
from datetime import datetime
import logging
from app.models.web_page import WebPage

# 配置日志
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class WebScraper:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

    def fetch_url(self, url: str) -> Optional[Dict[str, Any]]:
        """获取URL内容"""
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                return self._parse_content(url, response.text)
            else:
                logger.error(f"Failed to fetch {url}, status: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error fetching {url}: {str(e)}")
            return None

    def _parse_content(self, url: str, html_content: str) -> Dict[str, Any]:
        """解析HTML内容"""
        soup = BeautifulSoup(html_content, 'html.parser')
        title = soup.title.string.strip().replace('\t', '').replace('\n', '') if soup.title else ''
        return {
            'url': url,
            'title': title,
            'text_content': ' '.join([p.get_text() for p in soup.find_all('p')]),
            'html_content': html_content,
            'summary': '',
        }

    def save_to_db(self, user_id: str, content: Dict[str, Any], db: Session) -> WebPage:
        """保存内容到数据库"""
        webpage = WebPage(
            webpage_id=f"webpage-{shortuuid.uuid()}",
            user_id=user_id,
            url=content['url'],
            title=content['title'],
            text_content=content['text_content'],
            html_content=content['html_content'],
            summary=content['summary'],
            status=2,
        )
        db.add(webpage)
        db.commit()
        return webpage

    def get_by_url(self, url: str, db: Session) -> Optional[WebPage]:
        """根据URL检索内容"""
        query = select(WebPage).where(WebPage.url == url)
        result = db.execute(query)
        webpage = result.scalar_one_or_none()
        return webpage

    def scrape_and_save(self, user_id: str, url: str, db: Session) -> Optional[WebPage]:
        """抓取并保存URL内容"""
        content = self.fetch_url(url)
        if content:
            return self.save_to_db(user_id, content, db)
        return None
    
# 创建一个单例实例
scraper = WebScraper()
