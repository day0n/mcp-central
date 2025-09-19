/**
 * API 类型定义
 */

export interface APIResponse<T = any> {
  success: boolean;
  data?: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  request_id: string;
}

export interface SessionConfig {
  audio_duration?: number;
  language?: string;
  enable_pinyin?: boolean;
}

export interface SessionData {
  session_id: string;
  created_at: string;
  status: string;
}

export interface ConversationTurn {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  metadata?: Record<string, any>;
}

export interface UserRequirement {
  style: string;
  mood: string;
  duration: number;
  language: string;
  specific_requests: string[];
  theme: string;
  target_audience: string;
}

export interface LyricsVersion {
  version: number;
  content: string;
  approved: boolean;
  user_feedback: string | null;
  created_at: string;
  pinyin_annotated: string | null;
}

export interface DebugLog {
  timestamp: string;
  level: string;
  message: string;
  metadata: Record<string, any>;
}

export interface SessionState {
  session_id: string;
  current_stage: string;
  stage_description: string;
  progress_percentage: number;
  conversation_history: ConversationTurn[];
  user_requirement: UserRequirement;
  lyrics_versions: LyricsVersion[];
  debug_logs: DebugLog[];
}

export interface AudioFile {
  url: string;
  filename: string;
  duration: number;
  score: number;
}

export interface SessionResult {
  audio_files: AudioFile[];
  final_lyrics: string;
  metadata: {
    generation_time?: number;
    quality_scores?: Record<string, number>;
    [key: string]: any;
  };
}

export interface ChatMessage {
  content: string;
  message_type?: string;
  metadata?: Record<string, any>;
}

export interface LyricsReview {
  version: number;
  approved: boolean;
  feedback?: string;
}

export interface SSEEvent {
  event: string;
  data: Record<string, any>;
}

// API 请求类型
export interface StartSessionRequest {
  config?: SessionConfig;
}

export interface SendMessageRequest extends ChatMessage {}

export interface ReviewLyricsRequest extends LyricsReview {}