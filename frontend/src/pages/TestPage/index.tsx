import supabase from '@/utils/supabase';
import { faker } from '@faker-js/faker/locale/zh_CN';
import { Button, message } from 'antd';
import React, { useState } from 'react';
import styles from './index.module.less';

const TestPage: React.FC = () => {
  const [loading, setLoading] = useState(false);

  const insertFakeData = async () => {
    try {
      setLoading(true);

      // 使用faker生成一条假数据
      const fakeData = {
        name: faker.person.fullName(),
        // created_at由Supabase自动生成，无需提供
      };

      // 插入数据到表中
      const { data, error } = await supabase
        .from('测试') // 从截图中看不出确切表名，请替换为实际表名
        .insert(fakeData)
        .select();

      if (error) {
        throw error;
      }

      message.success('数据插入成功！');
      console.log('插入的数据：', data);
    } catch (error: any) {
      message.error(`插入失败：${error.message || '未知错误'}`);
      console.error('插入错误：', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.testPage}>
      <h1>测试页</h1>
      <p>这是一个测试页面。</p>

      <div className={styles.actionArea}>
        <Button type="primary" onClick={insertFakeData} loading={loading}>
          插入假数据到Supabase
        </Button>
      </div>
    </div>
  );
};

export default TestPage;
