'use client';

import { useEffect } from 'react';
import { useParams } from 'next/navigation';
import { useSessionStore } from '@/stores/session-store';
import { Button } from '@/components/ui/button';
import { ArrowLeft, MessageCircle, Settings, Activity, Music, Play, Pause, Download, Volume2 } from 'lucide-react';
import Link from 'next/link';

export default function ChatPage() {
  const params = useParams();
  const sessionId = params.sessionId as string;

  const {
    sessionId: currentSessionId,
    isConnected,
    connectionError,
    currentStage,
    stageDescription,
    progressPercentage,
    conversationHistory,
    userRequirement,
    debugLogs,
    showDebugPanel,
    sessionResult,
    toggleDebugPanel,
    connectToStream,
    sendMessage,
    isLoading,
    error
  } = useSessionStore();

  // 如果会话ID不匹配，更新store中的sessionId并连接SSE
  useEffect(() => {
    if (sessionId && sessionId !== currentSessionId) {
      // 先清理旧连接
      useSessionStore.getState().disconnectFromStream();
      // 设置新的sessionId
      useSessionStore.setState({ sessionId });
      // 延迟连接以避免重复
      setTimeout(async () => {
        await connectToStream();
      }, 100);
    }
  }, [sessionId, currentSessionId, connectToStream]);

  const getStageDisplayName = (stage: string) => {
    const stageMap: Record<string, string> = {
      'initializing': '初始化中',
      'collecting_requirements': '收集需求',
      'generating_lyrics': '生成歌词',
      'reviewing_lyrics': '审核歌词',
      'preparing_generation': '准备生成',
      'generating_music': '生成音乐',
      'evaluating_results': '评估结果',
      'completed': '完成',
      'failed': '失败'
    };
    return stageMap[stage] || stage;
  };

  const getProgressColor = (percentage: number) => {
    if (percentage < 30) return 'bg-red-500';
    if (percentage < 70) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      {/* 顶部导航栏 */}
      <div className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center">
              <Link href="/">
                <Button variant="ghost" className="mr-4">
                  <ArrowLeft className="h-4 w-4 mr-2" />
                  返回首页
                </Button>
              </Link>
              <div className="flex items-center">
                <Music className="h-6 w-6 text-blue-600 dark:text-blue-400 mr-2" />
                <h1 className="text-lg font-semibold text-gray-900 dark:text-white">
                  音乐生成会话
                </h1>
              </div>
            </div>
            <div className="flex items-center space-x-4">
              <div className="flex items-center">
                <div className={`w-2 h-2 rounded-full mr-2 ${isConnected ? 'bg-green-500' : 'bg-red-500'}`} />
                <span className="text-sm text-gray-600 dark:text-gray-300">
                  {isConnected ? '已连接' : '连接中断'}
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={toggleDebugPanel}
              >
                <Settings className="h-4 w-4 mr-2" />
                调试
              </Button>
            </div>
          </div>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

          {/* 左侧：对话区域 */}
          <div className="lg:col-span-2">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 h-[600px] flex flex-col">

              {/* 对话头部 */}
              <div className="p-4 border-b border-gray-200 dark:border-gray-700">
                <div className="flex items-center justify-between">
                  <div className="flex items-center">
                    <MessageCircle className="h-5 w-5 text-blue-600 dark:text-blue-400 mr-2" />
                    <h2 className="text-lg font-medium text-gray-900 dark:text-white">
                      对话记录
                    </h2>
                  </div>
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    会话ID: {sessionId?.slice(0, 8)}...
                  </span>
                </div>
              </div>

              {/* 对话内容 */}
              <div className="flex-1 overflow-y-auto p-4">
                {conversationHistory.length === 0 ? (
                  <div className="flex items-center justify-center h-full">
                    <div className="text-center">
                      <MessageCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                      <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                        开始对话
                      </h3>
                      <p className="text-gray-600 dark:text-gray-300">
                        请描述您想要的音乐风格和情绪
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-4">
                    {conversationHistory.map((turn, index) => (
                      <div
                        key={index}
                        className={`flex ${turn.role === 'user' ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg ${
                            turn.role === 'user'
                              ? 'bg-blue-600 text-white'
                              : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white'
                          }`}
                        >
                          <p className="text-sm">{turn.content}</p>
                          <p className="text-xs mt-1 opacity-70">
                            {new Date(turn.timestamp).toLocaleTimeString('zh-CN')}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* 输入区域 */}
              <div className="p-4 border-t border-gray-200 dark:border-gray-700">
                <div className="flex space-x-2">
                  <input
                    id="messageInput"
                    type="text"
                    placeholder="描述您想要的音乐风格..."
                    className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        const input = e.target as HTMLInputElement;
                        if (input.value.trim()) {
                          sendMessage(input.value.trim());
                          input.value = '';
                        }
                      }
                    }}
                    disabled={isLoading}
                  />
                  <Button
                    size="sm"
                    onClick={() => {
                      const input = document.getElementById('messageInput') as HTMLInputElement;
                      if (input && input.value.trim()) {
                        sendMessage(input.value.trim());
                        input.value = '';
                      }
                    }}
                    disabled={isLoading}
                  >
                    发送
                  </Button>
                </div>
              </div>
            </div>
          </div>

          {/* 右侧：状态面板 */}
          <div className="space-y-6">

            {/* 当前状态 */}
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                  当前状态
                </h3>
                <Activity className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              </div>

              <div className="space-y-3">
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      {getStageDisplayName(currentStage)}
                    </span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {Math.round(progressPercentage)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all duration-500 ${getProgressColor(progressPercentage)}`}
                      style={{ width: `${progressPercentage}%` }}
                    />
                  </div>
                </div>

                {stageDescription && (
                  <p className="text-sm text-gray-600 dark:text-gray-300">
                    {stageDescription}
                  </p>
                )}
              </div>
            </div>

            {/* 用户需求 */}
            {userRequirement && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-3">
                  需求信息
                </h3>
                <div className="space-y-2 text-sm">
                  {userRequirement.style && (
                    <div>
                      <span className="font-medium text-gray-700 dark:text-gray-300">风格：</span>
                      <span className="text-gray-600 dark:text-gray-400">{userRequirement.style}</span>
                    </div>
                  )}
                  {userRequirement.mood && (
                    <div>
                      <span className="font-medium text-gray-700 dark:text-gray-300">情绪：</span>
                      <span className="text-gray-600 dark:text-gray-400">{userRequirement.mood}</span>
                    </div>
                  )}
                  {userRequirement.theme && (
                    <div>
                      <span className="font-medium text-gray-700 dark:text-gray-300">主题：</span>
                      <span className="text-gray-600 dark:text-gray-400">{userRequirement.theme}</span>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 调试日志 */}
            {showDebugPanel && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-3">
                  调试日志
                </h3>
                <div className="max-h-60 overflow-y-auto">
                  {debugLogs.length === 0 ? (
                    <p className="text-sm text-gray-500 dark:text-gray-400">暂无日志</p>
                  ) : (
                    <div className="space-y-2">
                      {debugLogs.slice(-10).map((log, index) => (
                        <div key={index} className="text-xs">
                          <span className="text-gray-500 dark:text-gray-400">
                            {new Date(log.timestamp).toLocaleTimeString('zh-CN')}
                          </span>
                          <span className="ml-2 text-gray-700 dark:text-gray-300">
                            {log.message}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 音频结果播放器 */}
            {sessionResult && sessionResult.audio_files && sessionResult.audio_files.length > 0 && (
              <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-lg font-medium text-gray-900 dark:text-white">
                    生成结果
                  </h3>
                  <Music className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                </div>

                <div className="space-y-4">
                  {sessionResult.audio_files.map((audioFile, index) => (
                    <div key={index} className="bg-gray-50 dark:bg-gray-700 rounded-lg p-3">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                          音频 {index + 1}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          评分: {audioFile.score?.toFixed(1) || 'N/A'}
                        </span>
                      </div>

                      <audio
                        controls
                        className="w-full mb-2"
                        src={`http://localhost:8001${audioFile.url}`}
                      >
                        您的浏览器不支持音频播放。
                      </audio>

                      <div className="flex items-center justify-between">
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          时长: {audioFile.duration}s
                        </span>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => {
                            const link = document.createElement('a');
                            link.href = `http://localhost:8001${audioFile.url}`;
                            link.download = audioFile.filename;
                            link.click();
                          }}
                        >
                          <Download className="h-3 w-3 mr-1" />
                          下载
                        </Button>
                      </div>
                    </div>
                  ))}

                  {/* 最终歌词 */}
                  {sessionResult.final_lyrics && (
                    <div className="border-t border-gray-200 dark:border-gray-600 pt-3">
                      <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                        歌词
                      </h4>
                      <div className="bg-gray-50 dark:bg-gray-700 rounded p-2 text-xs text-gray-600 dark:text-gray-400 whitespace-pre-wrap">
                        {sessionResult.final_lyrics}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* 错误显示 */}
            {(error || connectionError) && (
              <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
                <h3 className="text-sm font-medium text-red-800 dark:text-red-200 mb-1">
                  连接错误
                </h3>
                <p className="text-sm text-red-700 dark:text-red-300">
                  {error || connectionError}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}