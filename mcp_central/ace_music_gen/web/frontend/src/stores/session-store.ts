/**
 * 会话状态管理 Store
 */

import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';
import {
  SessionState,
  ConversationTurn,
  SessionResult,
  DebugLog,
  LyricsVersion,
  UserRequirement
} from '@/types';
import apiClient from '@/lib/api-client';

interface SessionStore {
  // 当前会话信息
  sessionId: string | null;
  isConnected: boolean;
  connectionError: string | null;

  // 会话状态
  currentStage: string;
  stageDescription: string;
  progressPercentage: number;

  // 对话数据
  conversationHistory: ConversationTurn[];
  userRequirement: UserRequirement | null;
  lyricsVersions: LyricsVersion[];

  // 调试信息
  debugLogs: DebugLog[];
  showDebugPanel: boolean;

  // 最终结果
  sessionResult: SessionResult | null;

  // 加载状态
  isLoading: boolean;
  error: string | null;

  // Actions
  startSession: (config?: any) => Promise<void>;
  sendMessage: (content: string) => Promise<void>;
  reviewLyrics: (version: number, approved: boolean, feedback?: string) => Promise<void>;
  connectToStream: () => Promise<void>;
  disconnectFromStream: () => void;
  updateSessionState: (state: Partial<SessionState>) => void;
  addConversationTurn: (turn: ConversationTurn) => void;
  addDebugLog: (log: DebugLog) => void;
  toggleDebugPanel: () => void;
  setError: (error: string | null) => void;
  clearSession: () => void;
  fetchSessionResult: () => Promise<void>;

  // 内部状态
  _eventSource: EventSource | null;
}

export const useSessionStore = create<SessionStore>()(
  subscribeWithSelector((set, get) => ({
    // 初始状态
    sessionId: null,
    isConnected: false,
    connectionError: null,
    currentStage: 'initializing',
    stageDescription: '',
    progressPercentage: 0,
    conversationHistory: [],
    userRequirement: null,
    lyricsVersions: [],
    debugLogs: [],
    showDebugPanel: false,
    sessionResult: null,
    isLoading: false,
    error: null,
    _eventSource: null,

    // 创建会话
    startSession: async (config = {}) => {
      set({ isLoading: true, error: null });

      try {
        const response = await apiClient.startSession({ config });

        if (response.success && response.data) {
          const sessionId = response.data.session_id;
          set({
            sessionId,
            currentStage: 'initializing',
            stageDescription: '会话已创建，正在初始化...',
            progressPercentage: 0,
            isLoading: false,
          });

          // 连接到SSE流
          await get().connectToStream();
        } else {
          throw new Error(response.error?.message || '创建会话失败');
        }
      } catch (error) {
        console.error('Start session error:', error);
        set({
          error: error instanceof Error ? error.message : '创建会话失败',
          isLoading: false,
        });
      }
    },

    // 发送消息
    sendMessage: async (content: string) => {
      const { sessionId } = get();
      if (!sessionId) return;

      set({ isLoading: true });

      try {
        // 不在这里添加用户消息，等待SSE推送
        const response = await apiClient.sendMessage(sessionId, {
          content,
          message_type: 'user_input',
        });

        if (response.success) {
          // 用户消息和Agent回复都会通过SSE推送
          set({ isLoading: false });
        } else {
          throw new Error(response.error?.message || '发送消息失败');
        }
      } catch (error) {
        console.error('Send message error:', error);
        set({
          error: error instanceof Error ? error.message : '发送消息失败',
          isLoading: false,
        });
      }
    },

    // 审核歌词
    reviewLyrics: async (version: number, approved: boolean, feedback?: string) => {
      const { sessionId } = get();
      if (!sessionId) return;

      set({ isLoading: true });

      try {
        const response = await apiClient.reviewLyrics(sessionId, {
          version,
          approved,
          feedback,
        });

        if (response.success) {
          // 更新歌词版本状态
          set((state) => ({
            lyricsVersions: state.lyricsVersions.map((lyrics) =>
              lyrics.version === version
                ? { ...lyrics, approved, user_feedback: feedback || null }
                : lyrics
            ),
            isLoading: false,
          }));
        } else {
          throw new Error(response.error?.message || '歌词审核失败');
        }
      } catch (error) {
        console.error('Review lyrics error:', error);
        set({
          error: error instanceof Error ? error.message : '歌词审核失败',
          isLoading: false,
        });
      }
    },

    // 连接SSE流
    connectToStream: async () => {
      const { sessionId, _eventSource } = get();
      if (!sessionId) return;

      // 如果已有连接，先断开
      if (_eventSource) {
        _eventSource.close();
        set({ _eventSource: null });
      }

      try {
        // 首先拉取当前会话状态
        console.log('Fetching session state before connecting SSE...');
        const stateResponse = await apiClient.getSessionState(sessionId);
        if (stateResponse.success && stateResponse.data) {
          const state = stateResponse.data;
          set({
            currentStage: state.current_stage,
            stageDescription: state.stage_description || '',
            progressPercentage: state.progress_percentage || 0,
            conversationHistory: state.conversation_history || [],
            userRequirement: state.user_requirement || null,
            lyricsVersions: state.lyrics_versions || [],
            debugLogs: state.debug_logs || [],
          });
          console.log('Session state loaded:', state);
        }

        const eventSource = apiClient.createEventSource(sessionId);

        eventSource.onopen = () => {
          set({ isConnected: true, connectionError: null });
          console.log('SSE connected');
        };

        eventSource.onerror = (error) => {
          console.error('SSE error:', error);
          set({
            isConnected: false,
            connectionError: 'SSE连接失败',
          });
        };

        // 监听各种事件类型
        eventSource.addEventListener('connected', (event) => {
          console.log('SSE connected event:', event.data);
        });

        eventSource.addEventListener('chat_message', (event) => {
          const data = JSON.parse(event.data);
          get().addConversationTurn({
            role: data.role,
            content: data.content,
            timestamp: data.timestamp,
            metadata: data.metadata,
          });
        });

        eventSource.addEventListener('state_update', (event) => {
          const data = JSON.parse(event.data);
          set({
            currentStage: data.stage,
            stageDescription: data.description,
            progressPercentage: data.progress,
          });
        });

        eventSource.addEventListener('debug_log', (event) => {
          const data = JSON.parse(event.data);
          get().addDebugLog({
            timestamp: data.timestamp,
            level: data.level,
            message: data.message,
            metadata: data.metadata,
          });
        });

        eventSource.addEventListener('error', (event) => {
          const data = JSON.parse(event.data);
          set({ error: data.error });
        });

        eventSource.addEventListener('complete', (event) => {
          const data = JSON.parse(event.data);
          console.log('Session completed:', data);
          // 获取最终结果
          get().fetchSessionResult();
        });

        set({ _eventSource: eventSource });
      } catch (error) {
        console.error('Failed to connect SSE:', error);
        set({ connectionError: 'SSE连接失败' });
      }
    },

    // 断开SSE连接
    disconnectFromStream: () => {
      const { _eventSource } = get();
      if (_eventSource) {
        _eventSource.close();
        set({
          _eventSource: null,
          isConnected: false,
        });
      }
    },

    // 更新会话状态
    updateSessionState: (state: Partial<SessionState>) => {
      set((current) => ({
        ...current,
        ...state,
      }));
    },

    // 添加对话记录
    addConversationTurn: (turn: ConversationTurn) => {
      set((state) => ({
        conversationHistory: [...state.conversationHistory, turn],
      }));
    },

    // 添加调试日志
    addDebugLog: (log: DebugLog) => {
      set((state) => ({
        debugLogs: [...state.debugLogs, log].slice(-50), // 只保留最近50条
      }));
    },

    // 切换调试面板
    toggleDebugPanel: () => {
      set((state) => ({
        showDebugPanel: !state.showDebugPanel,
      }));
    },

    // 设置错误
    setError: (error: string | null) => {
      set({ error });
    },

    // 清除会话
    clearSession: () => {
      get().disconnectFromStream();
      set({
        sessionId: null,
        isConnected: false,
        connectionError: null,
        currentStage: 'initializing',
        stageDescription: '',
        progressPercentage: 0,
        conversationHistory: [],
        userRequirement: null,
        lyricsVersions: [],
        debugLogs: [],
        sessionResult: null,
        error: null,
        _eventSource: null,
      });
    },

    // 获取会话结果
    fetchSessionResult: async () => {
      const { sessionId } = get();
      if (!sessionId) return;

      try {
        const response = await apiClient.getSessionResult(sessionId);
        if (response.success && response.data) {
          set({ sessionResult: response.data });
        }
      } catch (error) {
        console.error('Failed to fetch session result:', error);
      }
    },
  }))
);

// 在store外部添加一个清理函数
export const cleanupSessionStore = () => {
  const store = useSessionStore.getState();
  store.disconnectFromStream();
};