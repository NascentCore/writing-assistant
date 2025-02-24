import { PaperClipOutlined, PictureOutlined } from '@ant-design/icons';
import { history } from '@umijs/max';
import { Input, Tabs } from 'antd';
import React from 'react';
import styles from './index.less';

const { TabPane } = Tabs;

interface WritingCard {
  id: string;
  title: string;
  description: string;
  icon: string;
  tag?: string;
}

const writingTypes: WritingCard[] = [
  {
    id: 'long-writing',
    title: '长文写作',
    description: '分步骤生成大纲和文稿',
    icon: '📝',
  },
  {
    id: 'article',
    title: '文章',
    description: '撰写各主流平台文章',
    icon: '📄',
    tag: '分步骤',
  },
  {
    id: 'marketing',
    title: '宣传文案',
    description: '撰写各平台的推广文案',
    icon: '📢',
  },
  {
    id: 'essay',
    title: '作文',
    description: '专为学生打造满分作文',
    icon: '✍️',
  },
];

const Home: React.FC = () => {
  const tabs = [
    '全部',
    '工作',
    '商业营销',
    '学习/教育',
    '社媒文章',
    '文学艺术',
    '回复和改写',
  ];

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>我是小标，你的标书写作助手</h1>
        <p className={styles.subtitle}>
          请告诉我你的具体需求，让我来帮你完成吧~
        </p>
      </div>

      <Tabs defaultActiveKey="0" className={styles.tabs}>
        {tabs.map((tab, index) => (
          <TabPane tab={tab} key={index} />
        ))}
      </Tabs>

      <div className={styles.cardGrid}>
        {writingTypes.map((card) => (
          <div
            key={card.id}
            className={styles.card}
            onClick={() => history.push(`/writing/${card.id}`)}
          >
            <div className={styles.cardIcon}>{card.icon}</div>
            <div className={styles.cardContent}>
              <h3>{card.title}</h3>
              <p>{card.description}</p>
            </div>
            {card.tag && <div className={styles.cardTag}>{card.tag}</div>}
          </div>
        ))}
      </div>

      <div className={styles.inputArea}>
        <Input
          size="large"
          placeholder="给 小标 发送消息"
          prefix={<span className={styles.inputPrefix}>给</span>}
          suffix={
            <div className={styles.inputSuffix}>
              <PaperClipOutlined />
              <PictureOutlined />
              <span>这是聊透顶</span>
              <span className={styles.divider}>|</span>
              <span className={styles.stepToggle}>
                分步骤
                <div className={styles.toggle} />
              </span>
            </div>
          }
        />
      </div>
    </div>
  );
};

export default Home;
