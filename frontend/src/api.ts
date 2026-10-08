import type {
  AiExtractResult,
  AiGenerateResult,
  AiPresets,
  Assignment,
  AssignmentLive,
  AssignmentResults,
  AttemptDetail,
  AttemptSubmitResult,
  AuthResponse,
  ClassOut,
  GameHistory,
  GameInfo,
  Gradebook,
  MeResponse,
  PinPeek,
  QuestionAnalysis,
  Quiz,
  QuizSummary,
  StudentOut,
} from "./shared";

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
}

export function getAuthToken() {
  return authToken;
}

function formatErrorDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const d = detail as Record<string, unknown>;
    if (typeof d.message === "string") {
      const retry = d.retry_after_seconds;
      return retry != null ? `${d.message} (retry in ${retry}s)` : d.message;
    }
    try {
      return JSON.stringify(detail);
    } catch {
      return fallback;
    }
  }
  return fallback;
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (!(init?.body instanceof FormData)) {
    headers["Content-Type"] = headers["Content-Type"] || "application/json";
  }
  if (authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    let detail: unknown = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? body;
    } catch {
      /* ignore */
    }
    throw new Error(formatErrorDetail(detail, "Request failed"));
  }
  if (res.status === 204) return undefined as T;
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("text/csv")) {
    return (await res.text()) as T;
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () =>
    request<{ status: string; app: string; public_base_url?: string; host_ip_is_loopback?: boolean }>(
      "/api/health",
    ),
  gameInfo: () => request<GameInfo>("/api/games/info"),
  peekPin: (pin: string) => request<PinPeek>(`/api/games/pin/${encodeURIComponent(pin)}`),

  registerTeacher: (body: { username: string; password: string }) =>
    request<AuthResponse>("/api/auth/register", { method: "POST", body: JSON.stringify(body) }),
  loginTeacher: (body: { username: string; password: string }) =>
    request<AuthResponse>("/api/auth/login", { method: "POST", body: JSON.stringify(body) }),
  loginStudent: (body: {
    student_code: string;
    password: string;
    join_code?: string | null;
  }) =>
    request<AuthResponse>("/api/auth/student/login", {
      method: "POST",
      body: JSON.stringify(body),
    }),
  me: () => request<MeResponse>("/api/auth/me"),
  importTeachers: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{
      added: Array<{ user_id: number | null; username: string }>;
      skipped: Array<{ row: number; reason: string }>;
    }>("/api/auth/teachers/import", { method: "POST", body: fd, headers: {} });
  },

  listQuizzes: () => request<QuizSummary[]>("/api/quizzes"),
  getQuiz: (id: number) => request<Quiz>(`/api/quizzes/${id}`),
  createQuiz: (body: unknown) =>
    request<Quiz>("/api/quizzes", { method: "POST", body: JSON.stringify(body) }),
  updateQuiz: (id: number, body: unknown) =>
    request<Quiz>(`/api/quizzes/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteQuiz: (id: number) => request<void>(`/api/quizzes/${id}`, { method: "DELETE" }),
  exportQuiz: (id: number) => request<unknown>(`/api/quizzes/${id}/export`),
  importQuiz: (body: unknown) =>
    request<Quiz>("/api/quizzes/import", { method: "POST", body: JSON.stringify(body) }),
  uploadImage: async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{ url: string }>("/api/quizzes/upload-image", {
      method: "POST",
      body: fd,
      headers: {},
    });
  },

  listHistory: () => request<GameHistory[]>("/api/games/history"),
  deleteHistory: (id: number) =>
    request<void>(`/api/games/history/${id}`, { method: "DELETE" }),
  historyAnalysis: (id: number) =>
    request<{ history_id: number; pin: string; quiz_title: string; analysis: QuestionAnalysis[] }>(
      `/api/games/history/${id}/analysis`,
    ),

  listClasses: () => request<ClassOut[]>("/api/classes"),
  createClass: (body: { name: string }) =>
    request<ClassOut>("/api/classes", { method: "POST", body: JSON.stringify(body) }),
  getClass: (id: number) => request<ClassOut>(`/api/classes/${id}`),
  updateClass: (id: number, body: { name: string }) =>
    request<ClassOut>(`/api/classes/${id}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteClass: (id: number) => request<void>(`/api/classes/${id}`, { method: "DELETE" }),
  listStudents: (classId: number) =>
    request<StudentOut[]>(`/api/classes/${classId}/students`),
  addStudent: (
    classId: number,
    body: { display_name: string; student_code: string; password?: string },
  ) =>
    request<StudentOut>(`/api/classes/${classId}/students`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  deleteStudent: (classId: number, studentId: number) =>
    request<void>(`/api/classes/${classId}/students/${studentId}`, { method: "DELETE" }),
  importRoster: async (classId: number, file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    const res = await request<{ added: StudentOut[]; skipped: Array<{ row: number; reason: string }> } | StudentOut[]>(
      `/api/classes/${classId}/students/import`,
      {
        method: "POST",
        body: fd,
        headers: {},
      },
    );
    // Backward compat: old server returned a bare array.
    if (Array.isArray(res)) return { added: res, skipped: [] };
    return res;
  },

  listAssignments: () => request<Assignment[]>("/api/assignments"),
  listMyAssignments: () => request<Assignment[]>("/api/assignments/mine"),
  myScores: () => request<Array<Record<string, unknown>>>("/api/assignments/mine/scores"),
  createAssignment: (body: {
    class_id: number;
    quiz_id: number;
    title?: string;
    due_at?: string | null;
    max_attempts?: number | null;
    score_policy?: string;
  }) =>
    request<Assignment>("/api/assignments", { method: "POST", body: JSON.stringify(body) }),
  updateAssignment: (
    id: number,
    body: {
      title?: string;
      due_at?: string | null;
      clear_due_at?: boolean;
      max_attempts?: number | null;
      clear_max_attempts?: boolean;
      score_policy?: string;
    },
  ) =>
    request<Assignment>(`/api/assignments/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  closeAssignment: (id: number) =>
    request<Assignment>(`/api/assignments/${id}/close`, { method: "POST" }),
  reopenAssignment: (id: number) =>
    request<Assignment>(`/api/assignments/${id}/reopen`, { method: "POST" }),
  deleteAssignment: (id: number) =>
    request<void>(`/api/assignments/${id}`, { method: "DELETE" }),
  getAssignmentResults: (id: number) =>
    request<AssignmentResults>(`/api/assignments/${id}/results`),
  getAssignmentLive: (id: number) => request<AssignmentLive>(`/api/assignments/${id}/live`),
  getAssignmentAnalysis: (id: number) =>
    request<{ assignment_id: number; title: string; analysis: QuestionAnalysis[] }>(
      `/api/assignments/${id}/analysis`,
    ),
  createAttempt: (assignmentId: number) =>
    request<AttemptDetail["attempt"]>(`/api/assignments/${assignmentId}/attempts`, { method: "POST" }),
  getAttempt: (attemptId: number) => request<AttemptDetail>(`/api/attempts/${attemptId}`),
  submitAttempt: (
    attemptId: number,
    answers: Array<{ order_index: number; option_index?: number | null; answer_text?: string | null; question_id?: number | null }>,
  ) =>
    request<AttemptSubmitResult>(`/api/attempts/${attemptId}/submit`, {
      method: "POST",
      body: JSON.stringify({ answers }),
    }),

  getGradebook: (classId: number) => request<Gradebook>(`/api/gradebook/${classId}`),
  exportGradebook: async (classId: number) => {
    const headers: Record<string, string> = {};
    if (authToken) headers.Authorization = `Bearer ${authToken}`;
    const res = await fetch(`/api/gradebook/${classId}/export`, { headers });
    if (!res.ok) throw new Error("Export failed");
    return res.blob();
  },

  getAiPresets: () => request<AiPresets>("/api/ai/presets"),
  extractText: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<AiExtractResult>("/api/ai/extract-text", {
      method: "POST",
      body: form,
    });
  },
  generateQuiz: (body: {
    provider: string;
    model: string;
    api_key: string;
    base_url?: string | null;
    topic: string;
    source_material?: string | null;
    question_count: number;
    difficulty: string;
    language: string;
  }) =>
    request<AiGenerateResult>("/api/ai/generate-quiz", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
