import { fetchWithAuthNew } from '@/utils/fetch';
import { FieldTimeOutlined } from '@ant-design/icons';
import { history } from '@umijs/max';
import { Button, Spin, message } from 'antd';
import React, { useEffect, useState } from 'react';
import CustomerSender from './components/Sender';
import styles from './index.less';
// const { TabPane } = Tabs;

interface WritingCard {
  id: string;
  title: string;
  description: string;
  icon: string;
  tag?: string;
  value?: string;
  outlines?: { id: number; title: string }[] | null;
}

// 模板接口类型
interface Template {
  id: string;
  show_name: string;
  description: string;
  value: string;
  is_default: boolean;
  background_url: string;
  template_type: string;
  variables: any;
  created_at: string;
  updated_at: string;
  outlines: { id: number; title: string }[] | null;
  has_steps: boolean;
}

interface TemplateResponse {
  templates: Template[];
  total: number;
  page: number;
  page_size: number;
}

// 静态写作类型数据
const writingTypes: WritingCard[] = [];

const Home: React.FC = () => {
  // 存储模板数据的状态
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedTemplateValue, setSelectedTemplateValue] =
    useState<string>('');
  const [selectedOutlineId, setSelectedOutlineId] = useState<number | null>(
    null,
  );
  const [selectedOutlines, setSelectedOutlines] = useState<
    { id: number; title: string }[] | null
  >(null);
  const [hasSteps, setHasSteps] = useState<boolean>(false);

  // 获取模板列表
  useEffect(() => {
    const fetchTemplates = async () => {
      setLoading(true);
      setError(null);
      try {
        // fetchWithAuthNew 直接返回 data 部分
        const data = await fetchWithAuthNew<TemplateResponse>(
          '/api/v1/writing/templates?page=1&page_size=10',
        );
        if (data && 'templates' in data) {
          setTemplates(data.templates);
        } else {
          setError('获取模板数据格式错误');
          message.error('获取模板数据格式错误');
        }
      } catch (error) {
        console.error('获取模板列表失败:', error);
        setError('获取模板列表失败');
        message.error('获取模板列表失败，请稍后重试');
      } finally {
        setLoading(false);
      }
    };

    fetchTemplates();
  }, []);

  // 将模板数据转换为卡片格式
  const templateCards: WritingCard[] = templates.map((template) => ({
    id: template.id,
    title: template.show_name,
    description: template.description,
    icon: template.background_url
      ? `<img src="${template.background_url}" alt="${template.show_name}" style="width: 24px; height: 24px;" />`
      : '📄',
    tag: template.has_steps ? '分步骤' : undefined,
    value: template.value,
    outlines: template.outlines,
  }));

  // 合并静态写作类型和模板卡片
  const allCards = [...writingTypes, ...templateCards];

  // 处理卡片点击事件
  const handleCardClick = (card: WritingCard) => {
    console.log('点击卡片:', card);
    if (card.value) {
      setSelectedTemplateValue(card.value);
    }

    // 如果模板有大纲，选择第一个大纲并保存大纲列表
    if (card.outlines && card.outlines.length > 0) {
      console.log('设置大纲:', card.outlines);
      setSelectedOutlineId(card.outlines[0].id);
      setSelectedOutlines(card.outlines);
    } else {
      setSelectedOutlineId(null);
      setSelectedOutlines(null);
    }

    // 设置是否分步骤
    console.log('设置分步骤:', card.tag === '分步骤');
    setHasSteps(card.tag === '分步骤');
  };

  return (
    <div className={styles.container}>
      <div>
        <Button
          style={{ float: 'right' }}
          icon={<FieldTimeOutlined style={{ fontSize: 18 }} />}
          onClick={async () => {
            history.push('/WritingHistory');
          }}
        />
      </div>
      {/* <Tabs defaultActiveKey="0" className={styles.tabs}>
        {tabs.map((tab, index) => (
          <TabPane tab={tab} key={index} />
        ))}
      </Tabs> */}
      <div style={{ marginBottom: 'auto' }}>
        <div className={styles.header}>
          <h1 className={styles.title}>我是小标，你的标书写作助手</h1>
          <p className={styles.subtitle}>
            请告诉我你的具体需求，让我来帮你完成吧~
          </p>
        </div>
        <Spin spinning={loading} tip="加载模板中...">
          <div className={styles.cardGrid}>
            {error ? (
              <div className={styles.errorMessage}>{error}，请刷新页面重试</div>
            ) : allCards.length > 0 ? (
              allCards.map((card) => (
                <div
                  key={card.id}
                  className={styles.card}
                  onClick={() => handleCardClick(card)}
                >
                  <div className={styles.cardIcon}>
                    {card.icon.startsWith('<img') ? (
                      <div dangerouslySetInnerHTML={{ __html: card.icon }} />
                    ) : (
                      card.icon
                    )}
                  </div>
                  <div className={styles.cardContent}>
                    <h3>{card.title}</h3>
                    <p>{card.description}</p>
                  </div>
                  {card.tag && <div className={styles.cardTag}>{card.tag}</div>}
                </div>
              ))
            ) : (
              !loading && (
                <div className={styles.emptyMessage}>暂无可用模板</div>
              )
            )}
          </div>
        </Spin>
      </div>

      <div className={styles.inputArea}>
        <CustomerSender
          value={selectedTemplateValue}
          selectedOutlineId={selectedOutlineId}
          outlines={selectedOutlines}
          has_steps={hasSteps}
          onMessageSent={(message) => {
            console.log('发送消息:', message);
            // 这里可以添加处理消息的逻辑
          }}
        />
      </div>
    </div>
  );
};

export default Home;
