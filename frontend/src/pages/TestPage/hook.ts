import supabase from '@/utils/supabase';
import { message } from 'antd';
import { useState } from 'react';
import { RegisterFormValues } from './type';

export const useRegistration = () => {
  const [loading, setLoading] = useState(false);

  const registerUser = async (values: RegisterFormValues) => {
    try {
      setLoading(true);

      // 去除确认密码字段
      const { confirmPassword, ...registerData } = values; // eslint-disable-line @typescript-eslint/no-unused-vars

      // 使用Supabase Auth注册新用户
      const { error: signUpError } = await supabase.auth.signUp({
        email: registerData.email,
        password: registerData.password,
      });

      if (signUpError) {
        throw signUpError;
      }

      // 立即登录新注册的用户
      const { data: signInData, error: signInError } =
        await supabase.auth.signInWithPassword({
          email: registerData.email,
          password: registerData.password,
        });

      if (signInError) {
        throw signInError;
      }

      // 登录成功后，创建用户记录到 users 表
      if (signInData.user) {
        try {
          const { error: profileError } = await supabase.from('users').insert({
            id: signInData.user.id,
            username: registerData.username,
            gender: registerData.gender || null,
            age: registerData.age || null,
            created_at: new Date().toISOString(),
          });

          if (profileError) {
            console.error('创建用户资料错误:', profileError);
            // 记录错误但不抛出，因为用户账户已创建
          }
        } catch (profileError) {
          console.error('创建用户资料异常:', profileError);
          // 记录错误但不抛出，确保不影响注册流程
        }
      }

      message.success('注册并登录成功！');
      return signInData;
    } catch (error: any) {
      // 提供更详细的错误信息
      let errorMessage = '注册失败：';

      if (error.message.includes('row-level security policy')) {
        errorMessage +=
          '权限问题，无法创建用户资料。用户账户已创建，但资料创建失败。';
      } else if (
        error.message.includes('Email address') &&
        error.message.includes('is invalid')
      ) {
        errorMessage +=
          '邮箱格式不被接受，请尝试使用其他邮箱地址（如Gmail或企业邮箱）';
      } else if (
        error.status === 401 ||
        error.message.includes('Unauthorized')
      ) {
        errorMessage += '未授权操作，请重新登录。';
      } else {
        errorMessage += error.message || '未知错误';
      }

      message.error(errorMessage);
      console.error('注册错误：', error);
      return null;
    } finally {
      setLoading(false);
    }
  };

  return {
    loading,
    registerUser,
  };
};
