export interface Question {
  id?: number;
  text: string;
  image?: string | null;
  options: string[];
  correct_indices: number[];
  time_limit: number;
  order_index?: number;
}

export interface QuizSummary {
  id: number;
  title: string;
  description: string;
  question_count: number;
  created_at: string;
  updated_at: string;
  teacher_id?: number | null;
}

export interface Quiz extends QuizSummary {
  questions: Question[];
}

export interface PlayerInfo {
  sid: string;
  nickname: string;
  score: number;
  is_host?: boolean;
  student_id?: number | null;
}

export interface LeaderboardEntry {
  rank: number;
  sid: string;
  nickname: string;
  score: number;
  student_id?: number | null;
}

export interface LobbyState {
  pin: string;
  status: string;
  quiz_title: string;
  quiz_id: number;
  players: PlayerInfo[];
  player_count: number;
  question_count: number;
  current_question_index: number;
  requires_student_code?: boolean;
  assignment_id?: number | null;
  class_id?: number | null;
}

export interface QuestionPayload {
  question_index: number;
  total_questions: number;
  id: number;
  text: string;
  image?: string | null;
  options: string[];
  time_limit: number;
  started_at?: number;
}

export interface QuestionEndedPayload {
  question_index: number;
  correct_indices: number[];
  options: string[];
  results: Array<{
    sid: string;
    nickname: string;
    answered: boolean;
    option_index: number | null;
    correct: boolean;
    points: number;
    score: number;
  }>;
  leaderboard: LeaderboardEntry[];
  answer_count: number;
  player_count: number;
}

export interface GameEndedPayload {
  pin: string;
  quiz_title: string;
  leaderboard: LeaderboardEntry[];
  podium: LeaderboardEntry[];
}

export interface GameInfo {
  app: string;
  host_ip: string;
  port: number;
  public_base_url: string;
  join_path: string;
  score_base: number;
  scoring_formula: string;
}

export interface GameHistory {
  id: number;
  pin: string;
  quiz_id: number | null;
  quiz_title: string;
  played_at: string;
  player_count: number;
  results: LeaderboardEntry[];
  teacher_id?: number | null;
  class_id?: number | null;
  assignment_id?: number | null;
}

export interface AuthResponse {
  role: string;
  token: string;
  user_id?: number | null;
  username?: string | null;
  student_id?: number | null;
  class_id?: number | null;
  display_name?: string | null;
  class_name?: string | null;
}

export interface MeResponse {
  role: string;
  user_id?: number | null;
  username?: string | null;
  student_id?: number | null;
  class_id?: number | null;
  display_name?: string | null;
  class_name?: string | null;
}

export interface ClassOut {
  id: number;
  name: string;
  join_code: string;
  student_count: number;
  created_at: string;
}

export interface StudentOut {
  id: number;
  class_id: number;
  display_name: string;
  student_code: string;
  created_at: string;
}

export interface Assignment {
  id: number;
  class_id: number;
  class_name: string;
  quiz_id: number;
  quiz_title: string;
  title: string;
  status: string;
  due_at: string | null;
  max_attempts: number | null;
  score_policy: string;
  created_at: string;
  is_overdue?: boolean;
  best_score?: number | null;
  play_count?: number;
  played?: boolean;
}

export interface AssignmentResultRow {
  student_id: number;
  display_name: string;
  student_code: string;
  score: number | null;
  rank: number | null;
  play_count: number;
  last_played_at: string | null;
}

export interface AssignmentResults {
  assignment_id: number;
  title: string;
  class_name: string;
  score_policy: string;
  max_attempts: number | null;
  rows: AssignmentResultRow[];
}

export interface AssignmentLive {
  active: boolean;
  pin: string | null;
  status: string | null;
  player_count: number;
  quiz_title: string | null;
}

export interface GradebookCell {
  assignment_id: number;
  assignment_title: string;
  score: number | null;
  rank: number | null;
  played_at: string | null;
}

export interface GradebookRow {
  student_id: number;
  display_name: string;
  student_code: string;
  scores: GradebookCell[];
  total: number;
}

export interface Gradebook {
  class_id: number;
  class_name: string;
  assignments: Assignment[];
  rows: GradebookRow[];
}

export interface PinPeek {
  pin: string;
  quiz_title: string;
  status: string;
  requires_student_code: boolean;
  player_count: number;
}

export interface AiModelPreset {
  id: string;
  label: string;
  aliases?: string[];
}

export interface AiProviderPreset {
  id: string;
  label: string;
  base_url: string;
  docs_url: string;
  models: AiModelPreset[];
  default_model: string;
}

export interface AiPresets {
  label: string;
  default_provider: string;
  default_model: string;
  providers: AiProviderPreset[];
  note: string;
  extract?: {
    max_upload_bytes: number;
    max_extract_chars: number;
    formats: string[];
  };
}

export interface AiRateLimit {
  warning: boolean;
  message: string;
  remaining_requests: number | null;
  retry_after_seconds: number | null;
}

export interface AiExtractResult {
  text: string;
  char_count: number;
  truncated: boolean;
  warning: string;
  filename: string;
}

export interface AiGenerateResult {
  quiz: {
    title: string;
    description: string;
    questions: Question[];
  };
  rate_limit: AiRateLimit;
}

export const OPTION_COLORS = [
  "bg-opt-a",
  "bg-opt-b",
  "bg-opt-c",
  "bg-opt-d",
  "bg-opt-e",
  "bg-opt-f",
] as const;

export const OPTION_SHAPES = ["▲", "◆", "●", "■", "★", "✦"] as const;
