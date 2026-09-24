import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api, setAuthToken } from "../api";

export type AuthRole = "teacher" | "student";

export interface AuthState {
  role: AuthRole | null;
  token: string | null;
  userId: number | null;
  username: string | null;
  studentId: number | null;
  classId: number | null;
  displayName: string | null;
  className: string | null;
}

interface AuthContextValue extends AuthState {
  ready: boolean;
  loginTeacher: (username: string, password: string) => Promise<void>;
  registerTeacher: (username: string, password: string) => Promise<void>;
  loginStudent: (studentCode: string, password: string, joinCode?: string) => Promise<void>;
  logout: () => void;
  isTeacher: boolean;
  isStudent: boolean;
}

const STORAGE_KEY = "lanquiz_auth";

const empty: AuthState = {
  role: null,
  token: null,
  userId: null,
  username: null,
  studentId: null,
  classId: null,
  displayName: null,
  className: null,
};

const AuthContext = createContext<AuthContextValue | null>(null);

function loadStored(): AuthState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return empty;
    return { ...empty, ...JSON.parse(raw) };
  } catch {
    return empty;
  }
}

function persist(state: AuthState) {
  if (!state.token) {
    localStorage.removeItem(STORAGE_KEY);
    setAuthToken(null);
    return;
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  setAuthToken(state.token);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>(empty);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const stored = loadStored();
    setState(stored);
    setAuthToken(stored.token);
    if (stored.token) {
      api
        .me()
        .then((me) => {
          const next: AuthState = {
            role: me.role as AuthRole,
            token: stored.token,
            userId: me.user_id ?? null,
            username: me.username ?? null,
            studentId: me.student_id ?? null,
            classId: me.class_id ?? null,
            displayName: me.display_name ?? null,
            className: me.class_name ?? null,
          };
          setState(next);
          persist(next);
        })
        .catch(() => {
          setState(empty);
          persist(empty);
        })
        .finally(() => setReady(true));
    } else {
      setReady(true);
    }
  }, []);

  const applyAuth = useCallback((data: {
    role: string;
    token: string;
    user_id?: number | null;
    username?: string | null;
    student_id?: number | null;
    class_id?: number | null;
    display_name?: string | null;
    class_name?: string | null;
  }) => {
    const next: AuthState = {
      role: data.role as AuthRole,
      token: data.token,
      userId: data.user_id ?? null,
      username: data.username ?? null,
      studentId: data.student_id ?? null,
      classId: data.class_id ?? null,
      displayName: data.display_name ?? null,
      className: data.class_name ?? null,
    };
    setState(next);
    persist(next);
  }, []);

  const loginTeacher = useCallback(
    async (username: string, password: string) => {
      applyAuth(await api.loginTeacher({ username, password }));
    },
    [applyAuth],
  );

  const registerTeacher = useCallback(
    async (username: string, password: string) => {
      applyAuth(await api.registerTeacher({ username, password }));
    },
    [applyAuth],
  );

  const loginStudent = useCallback(
    async (studentCode: string, password: string, joinCode?: string) => {
      applyAuth(
        await api.loginStudent({
          student_code: studentCode,
          password,
          join_code: joinCode || null,
        }),
      );
    },
    [applyAuth],
  );

  const logout = useCallback(() => {
    setState(empty);
    persist(empty);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      ...state,
      ready,
      loginTeacher,
      registerTeacher,
      loginStudent,
      logout,
      isTeacher: state.role === "teacher",
      isStudent: state.role === "student",
    }),
    [state, ready, loginTeacher, registerTeacher, loginStudent, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
