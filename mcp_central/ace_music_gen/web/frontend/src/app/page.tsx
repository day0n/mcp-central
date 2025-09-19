'use client';

import { useEffect } from 'react';
import { useSessionStore } from '@/stores/session-store';
import { Button } from '@/components/ui/button';
import { Music, Settings, History } from 'lucide-react';

export default function HomePage() {
  const { sessionId, startSession, isLoading, error } = useSessionStore();

  const handleStartNewSession = async () => {
    await startSession({
      audio_duration: 30.0,
      language: '中文',
      enable_pinyin: true
    });
  };

  // 如果已有会话，重定向到对话页面
  useEffect(() => {
    if (sessionId) {
      window.location.href = `/chat/${sessionId}`;
    }
  }, [sessionId]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 dark:from-gray-900 dark:to-gray-800">
      <div className="container mx-auto px-4 py-16">
        {/* 头部标题 */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center mb-6">
            <Music className="h-16 w-16 text-blue-600 dark:text-blue-400 mr-4" />
            <h1 className="text-5xl font-bold text-gray-900 dark:text-white">
              ACE Music Gen
            </h1>
          </div>
          <p className="text-xl text-gray-600 dark:text-gray-300 max-w-3xl mx-auto">
            基于AI的智能音乐生成器，通过多轮对话收集需求，生成个性化音乐作品
          </p>
        </div>

        {/* 特性展示 */}
        <div className="grid md:grid-cols-3 gap-8 mb-12">
          <div className="bg-white dark:bg-gray-700 rounded-lg p-6 shadow-lg">
            <div className="h-12 w-12 bg-blue-100 dark:bg-blue-900 rounded-lg flex items-center justify-center mb-4">
              <Music className="h-6 w-6 text-blue-600 dark:text-blue-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              智能对话生成
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              通过自然语言对话，AI会理解您的音乐需求，生成符合期望的歌词和音乐
            </p>
          </div>

          <div className="bg-white dark:bg-gray-700 rounded-lg p-6 shadow-lg">
            <div className="h-12 w-12 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center mb-4">
              <Settings className="h-6 w-6 text-green-600 dark:text-green-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              实时状态监控
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              可视化显示AI的思考过程和生成进度，让您了解每一步的处理状态
            </p>
          </div>

          <div className="bg-white dark:bg-gray-700 rounded-lg p-6 shadow-lg">
            <div className="h-12 w-12 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center mb-4">
              <History className="h-6 w-6 text-purple-600 dark:text-purple-400" />
            </div>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              会话历史管理
            </h3>
            <p className="text-gray-600 dark:text-gray-300">
              保存所有生成记录，支持会话恢复和历史回顾，管理您的音乐创作
            </p>
          </div>
        </div>

        {/* 错误显示 */}
        {error && (
          <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-8">
            <p className="text-red-800 dark:text-red-200">{error}</p>
          </div>
        )}

        {/* 开始按钮 */}
        <div className="text-center">
          <Button
            onClick={handleStartNewSession}
            disabled={isLoading}
            className="px-8 py-3 text-lg font-semibold"
            size="lg"
          >
            {isLoading ? (
              <>
                <div className="animate-spin h-5 w-5 mr-3 border-2 border-white border-t-transparent rounded-full" />
                创建会话中...
              </>
            ) : (
              <>
                <Music className="h-5 w-5 mr-3" />
                开始音乐生成
              </>
            )}
          </Button>
        </div>

        {/* 使用说明 */}
        <div className="mt-16 bg-white dark:bg-gray-700 rounded-lg p-8 shadow-lg">
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-6 text-center">
            使用指南
          </h2>
          <div className="grid md:grid-cols-2 gap-8">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                生成流程
              </h3>
              <ol className="space-y-2 text-gray-600 dark:text-gray-300">
                <li className="flex items-start">
                  <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium mr-3 mt-0.5">1</span>
                  描述您想要的音乐风格和情绪
                </li>
                <li className="flex items-start">
                  <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium mr-3 mt-0.5">2</span>
                  AI将生成歌词候选版本供您选择
                </li>
                <li className="flex items-start">
                  <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium mr-3 mt-0.5">3</span>
                  确认歌词后，系统开始生成音乐
                </li>
                <li className="flex items-start">
                  <span className="bg-blue-600 text-white rounded-full w-6 h-6 flex items-center justify-center text-sm font-medium mr-3 mt-0.5">4</span>
                  获得个性化的音乐作品
                </li>
              </ol>
            </div>

            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                支持特性
              </h3>
              <ul className="space-y-2 text-gray-600 dark:text-gray-300">
                <li className="flex items-center">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-3"></div>
                  多种音乐风格（说唱、摇滚、民谣等）
                </li>
                <li className="flex items-center">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-3"></div>
                  中文歌词多音字智能标注
                </li>
                <li className="flex items-center">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-3"></div>
                  可调节音频时长和质量
                </li>
                <li className="flex items-center">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-3"></div>
                  实时生成进度反馈
                </li>
                <li className="flex items-center">
                  <div className="w-2 h-2 bg-green-500 rounded-full mr-3"></div>
                  多候选音频对比试听
                </li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
