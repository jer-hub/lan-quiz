import { useCallback, useState } from "react";

export type Lang = "en" | "vi";

const KEY = "lanquiz_lang";

const dict = {
  en: {
    appName: "LanQuiz",
    heroTitle: "Classroom quizzes on your own Wi-Fi",
    heroSub: "Teachers manage classes and assignments. Students join with a roster code. Live PIN games work fully offline after setup.",
    teacherDashboard: "Teacher dashboard",
    myClass: "My class",
    teacherLogin: "Teacher login",
    studentLogin: "Student login",
    joinPin: "Join with PIN",
    joinTitle: "Join LanQuiz",
    joinSub: "Enter the PIN shown on the host screen.",
    gamePin: "Game PIN",
    nickname: "Nickname",
    studentCode: "Student code",
    classGameNote: "Class game — your display name comes from the roster.",
    joinGame: "Join game",
    connecting: "Connecting…",
    team: "Team",
    chooseTeam: "Choose a team…",
    assignments: "Assignments",
    startHomework: "Start homework",
  },
  vi: {
    appName: "LanQuiz",
    heroTitle: "Trắc nghiệm trong lớp qua Wi-Fi nội bộ",
    heroSub: "Giáo viên quản lý lớp và bài tập. Học sinh tham gia bằng mã số. Trò chơi PIN trực tiếp chạy offline sau khi cài đặt.",
    teacherDashboard: "Bảng giáo viên",
    myClass: "Lớp của tôi",
    teacherLogin: "Giáo viên đăng nhập",
    studentLogin: "Học sinh đăng nhập",
    joinPin: "Tham gia bằng PIN",
    joinTitle: "Tham gia LanQuiz",
    joinSub: "Nhập mã PIN trên màn hình của giáo viên.",
    gamePin: "Mã PIN",
    nickname: "Biệt danh",
    studentCode: "Mã học sinh",
    classGameNote: "Trò chơi lớp — tên hiển thị lấy từ danh sách.",
    joinGame: "Tham gia",
    connecting: "Đang kết nối…",
    team: "Đội",
    chooseTeam: "Chọn đội…",
    assignments: "Bài tập",
    startHomework: "Làm bài tập",
  },
} as const;

export type Strings = Record<string, string>;

export function getLang(): Lang {
  try {
    return sessionStorage.getItem(KEY) === "vi" || localStorage.getItem(KEY) === "vi" ? "vi" : "en";
  } catch {
    return "en";
  }
}

export function useLang() {
  const [lang, setLangState] = useState<Lang>(getLang);
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {
      /* ignore */
    }
  }, []);
  const t: Strings = dict[lang] as unknown as Strings;
  return { lang, setLang, t };
}
