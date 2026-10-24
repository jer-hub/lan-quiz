import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { AiPresets, AiRateLimit, Question } from "../shared";

const PROVIDER = "google";
const DEFAULT_MODEL = "gemini-3.8-flash";
const KEY_URL = "https://aistudio.google.com/apikey";
const LS_MODEL = "lanquiz_ai_model";
const LS_KEY = "lanquiz_ai_key";
const LS_REMEMBER = "lanquiz_ai_remember";
// Saved by older versions that offered several providers.
const LEGACY_KEYS = ["lanquiz_ai_provider", "lanquiz_ai_base_url"];
const MIN_QUESTIONS = 3;
const MAX_QUESTIONS = 20;
const DIFFICULTIES = [
  ["easy", "Easy"],
  ["medium", "Medium"],
  ["hard", "Hard"],
] as const;
const LANGUAGE_SUGGESTIONS = ["English", "Vietnamese", "Filipino", "Spanish", "French", "Chinese"];

export interface GeneratedQuizPatch {
  title: string;
  description: string;
  questions: Question[];
}

interface Props {
  onGenerated: (quiz: GeneratedQuizPatch) => void;
}

type Notice = { tone: "success" | "warning" | "error"; text: string };

const NOTICE_STYLES: Record<Notice["tone"], string> = {
  success: "border-emerald-200 bg-emerald-50 text-emerald-900",
  warning: "border-amber-300 bg-amber-100 text-amber-950",
  error: "border-red-200 bg-red-50 text-red-800",
};

const FIELD = "w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-normal";

function loadRemember(): boolean {
  return localStorage.getItem(LS_REMEMBER) !== "0";
}

function clampQuestions(n: number): number {
  if (!Number.isFinite(n)) return 8;
  return Math.min(MAX_QUESTIONS, Math.max(MIN_QUESTIONS, Math.round(n)));
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <fieldset className="space-y-2">
      <legend className="mb-2 flex items-center gap-2 text-sm font-bold text-ink">
        <span className="grid h-6 w-6 place-items-center rounded-full bg-brand text-xs text-white" aria-hidden>
          {n}
        </span>
        {title}
      </legend>
      {children}
    </fieldset>
  );
}

export default function AiQuizGenerator({ onGenerated }: Props) {
  const [open, setOpen] = useState(false);
  const [presets, setPresets] = useState<AiPresets | null>(null);
  const [model, setModel] = useState(() => localStorage.getItem(LS_MODEL) || DEFAULT_MODEL);
  const [apiKey, setApiKey] = useState(() => localStorage.getItem(LS_KEY) || "");
  const [editingKey, setEditingKey] = useState(() => !localStorage.getItem(LS_KEY));
  const [showKey, setShowKey] = useState(false);
  const [remember, setRemember] = useState(loadRemember);
  const [topic, setTopic] = useState("");
  const [notesOpen, setNotesOpen] = useState(false);
  const [sourceMaterial, setSourceMaterial] = useState("");
  const [extractWarning, setExtractWarning] = useState<string | null>(null);
  const [extractMeta, setExtractMeta] = useState<{
    filename: string;
    char_count: number;
    truncated: boolean;
  } | null>(null);
  const [questionCount, setQuestionCount] = useState(8);
  const [difficulty, setDifficulty] = useState("medium");
  const [language, setLanguage] = useState("English");
  const [busy, setBusy] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [notice, setNotice] = useState<Notice | null>(null);
  const [rateLimit, setRateLimit] = useState<AiRateLimit | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open || presets) return;
    void api
      .getAiPresets()
      .then(setPresets)
      .catch((e) =>
        setNotice({ tone: "error", text: e instanceof Error ? e.message : "Failed to load AI settings" }),
      );
  }, [open, presets]);

  const providerMeta = useMemo(
    () => presets?.providers.find((p) => p.id === PROVIDER) || null,
    [presets],
  );
  const modelOptions = providerMeta?.models || [];
  const maxChars = presets?.extract?.max_extract_chars ?? 24_000;
  const keyUrl = providerMeta?.docs_url || KEY_URL;

  useEffect(() => {
    if (!providerMeta) return;
    const ids = new Set(modelOptions.map((m) => m.id));
    if (!ids.has(model) && providerMeta.default_model) setModel(providerMeta.default_model);
  }, [providerMeta, model, modelOptions]);

  // Live seconds counter while generating, so a slow model never looks frozen.
  useEffect(() => {
    if (!busy) return;
    const started = Date.now();
    setElapsed(0);
    const id = window.setInterval(() => setElapsed(Math.round((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(id);
  }, [busy]);

  const topicTrim = topic.trim();
  const materialTrim = sourceMaterial.trim();
  const hasKey = apiKey.trim().length >= 8;
  const hasContent = topicTrim.length >= 3 || materialTrim.length >= 20;
  const blocker = !hasKey
    ? "Add your Gemini API key in step 1."
    : !hasContent
      ? "Add a topic (3+ characters) or lesson notes in step 2."
      : null;

  const modelLabel = (id: string) =>
    modelOptions.find((m) => m.id === id)?.label.replace(" (default)", "") || id;

  const persistPrefs = () => {
    localStorage.setItem(LS_REMEMBER, remember ? "1" : "0");
    localStorage.setItem(LS_MODEL, model);
    LEGACY_KEYS.forEach((k) => localStorage.removeItem(k));
    if (remember && apiKey) localStorage.setItem(LS_KEY, apiKey);
    else localStorage.removeItem(LS_KEY);
  };

  const forgetKey = () => {
    setApiKey("");
    localStorage.removeItem(LS_KEY);
    setEditingKey(true);
  };

  const onFileChange = async (file: File | null) => {
    setNotice(null);
    setExtractWarning(null);
    if (!file) return;
    setExtracting(true);
    try {
      const result = await api.extractText(file);
      setSourceMaterial(result.text);
      setExtractMeta({
        filename: result.filename,
        char_count: result.char_count,
        truncated: result.truncated,
      });
      if (result.warning) setExtractWarning(result.warning);
      else if (result.truncated) setExtractWarning("The text was shortened to fit Gemini's limits.");
    } catch (e) {
      setNotice({ tone: "error", text: e instanceof Error ? e.message : "Could not read that file" });
    } finally {
      setExtracting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const generate = async () => {
    setNotice(null);
    setRateLimit(null);
    if (blocker) {
      setNotice({ tone: "error", text: blocker });
      return;
    }
    setBusy(true);
    persistPrefs();
    try {
      const result = await api.generateQuiz({
        provider: PROVIDER,
        model: model.trim(),
        api_key: apiKey.trim(),
        topic: topicTrim,
        source_material: materialTrim || null,
        question_count: questionCount,
        difficulty,
        language,
      });
      setRateLimit(result.rate_limit);
      const count = result.quiz.questions.length;
      const added = `Added ${count} question${count === 1 ? "" : "s"} below. Review them, then Save quiz.`;
      setNotice(
        result.fallback_used
          ? {
              tone: "warning",
              text: `${added} ${modelLabel(model.trim())} was busy, so ${modelLabel(result.model_used)} wrote this draft.`,
            }
          : { tone: "success", text: `${added} Written by ${modelLabel(result.model_used)}.` },
      );
      if (remember) setEditingKey(false);
      onGenerated({
        title: result.quiz.title,
        description: result.quiz.description,
        questions: result.quiz.questions.map((q) => ({
          text: q.text,
          image: q.image ?? null,
          options: q.options,
          correct_indices: q.correct_indices,
          time_limit: q.time_limit || 20,
        })),
      });
    } catch (e) {
      setNotice({ tone: "error", text: e instanceof Error ? e.message : "Generation failed" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="mb-6 overflow-hidden rounded-2xl border border-amber-200/80 bg-gradient-to-br from-amber-50 to-sky-50 shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left"
        aria-expanded={open}
      >
        <span className="flex items-center gap-3">
          <span
            className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-white text-xl shadow-sm"
            aria-hidden
          >
            ✨
          </span>
          <span>
            <span className="block font-display text-xl text-ink">Generate with AI</span>
            <span className="block text-sm text-ink/65">
              Draft questions from a topic or your lesson notes with Google Gemini. Optional — games
              work without it.
            </span>
          </span>
        </span>
        <span className="shrink-0 rounded-lg bg-white/80 px-3 py-1 text-sm font-bold text-ink/70">
          {open ? "Hide" : "Open"}
        </span>
      </button>

      {open && (
        <div className="space-y-6 border-t border-amber-200/70 px-4 py-5">
          <Step n={1} title="Your Gemini API key">
            {hasKey && !editingKey ? (
              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm">
                <span className="font-semibold text-emerald-900">✓ Key saved on this device</span>
                <span className="flex gap-4">
                  <button
                    type="button"
                    onClick={() => setEditingKey(true)}
                    className="font-bold text-brand-dark underline"
                  >
                    Change
                  </button>
                  <button type="button" onClick={forgetKey} className="font-bold text-ink/60 underline">
                    Forget
                  </button>
                </span>
              </div>
            ) : (
              <div className="space-y-2">
                <div className="flex gap-2">
                  <input
                    type={showKey ? "text" : "password"}
                    aria-label="Gemini API key"
                    className={`${FIELD} font-mono text-sm`}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="Paste your key"
                    autoComplete="off"
                    spellCheck={false}
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey((v) => !v)}
                    className="shrink-0 rounded-xl border border-sky-200 bg-white px-3 text-sm font-bold text-ink/70"
                    aria-pressed={showKey}
                  >
                    {showKey ? "Hide" : "Show"}
                  </button>
                </div>
                <div className="flex flex-wrap items-center justify-between gap-2 text-sm">
                  <label className="flex items-center gap-2 font-semibold text-ink/75">
                    <input
                      type="checkbox"
                      checked={remember}
                      onChange={(e) => setRemember(e.target.checked)}
                    />
                    Remember on this device
                  </label>
                  <a
                    href={keyUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="font-bold text-brand-dark underline"
                  >
                    Get a free key from Google AI Studio ↗
                  </a>
                </div>
                <p className="text-xs text-ink/55">
                  Your key stays in this browser and is sent only to Google. LanQuiz never stores it.
                </p>
              </div>
            )}
          </Step>

          <Step n={2} title="What should the quiz cover?">
            <input
              aria-label="Quiz topic"
              className={FIELD}
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Photosynthesis for grade 8"
            />
            <button
              type="button"
              onClick={() => setNotesOpen((v) => !v)}
              className="text-sm font-bold text-brand-dark"
              aria-expanded={notesOpen}
            >
              {notesOpen ? "− Hide lesson notes" : "+ Add lesson notes (optional)"}
            </button>
            {notesOpen && (
              <div className="space-y-2 rounded-xl border border-dashed border-sky-300 bg-white/70 p-3">
                <div className="flex flex-wrap items-center gap-3">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={extracting || busy}
                    className="rounded-lg bg-brand px-3 py-2 text-sm font-bold text-white disabled:opacity-50"
                  >
                    {extracting ? "Reading file…" : "Upload a file"}
                  </button>
                  <span className="text-xs text-ink/55">PDF, DOCX, TXT or MD · max 5 MB · or paste below</span>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".pdf,.docx,.txt,.md,application/pdf,text/plain,text/markdown"
                    className="hidden"
                    onChange={(e) => void onFileChange(e.target.files?.[0] ?? null)}
                  />
                </div>
                {extractMeta && (
                  <p className="text-xs font-semibold text-ink/70">
                    {extractMeta.filename} · {extractMeta.char_count.toLocaleString()} characters
                    {extractMeta.truncated ? " (shortened)" : ""}
                  </p>
                )}
                {extractWarning && <p className="text-xs text-amber-900">{extractWarning}</p>}
                <textarea
                  aria-label="Lesson notes"
                  className={`${FIELD} font-mono text-sm`}
                  rows={6}
                  value={sourceMaterial}
                  maxLength={maxChars}
                  onChange={(e) => {
                    setSourceMaterial(e.target.value);
                    setExtractMeta(null);
                    setExtractWarning(null);
                  }}
                  placeholder="Paste lesson notes here, or upload a file above. Questions will stick to these notes."
                />
                <p className="text-right text-xs text-ink/50">
                  {sourceMaterial.length.toLocaleString()} / {maxChars.toLocaleString()} characters
                </p>
              </div>
            )}
          </Step>

          <Step n={3} title="Quiz settings">
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="text-sm font-bold">
                Questions
                <div className="mt-1 flex items-center rounded-xl border border-sky-200 bg-white">
                  <button
                    type="button"
                    aria-label="Fewer questions"
                    onClick={() => setQuestionCount((n) => clampQuestions(n - 1))}
                    disabled={questionCount <= MIN_QUESTIONS}
                    className="px-3 py-2 text-lg font-bold text-ink/70 disabled:opacity-30"
                  >
                    −
                  </button>
                  <input
                    type="number"
                    aria-label="Number of questions"
                    min={MIN_QUESTIONS}
                    max={MAX_QUESTIONS}
                    className="w-full bg-transparent py-2 text-center font-normal"
                    value={questionCount}
                    onChange={(e) => setQuestionCount(Number(e.target.value))}
                    onBlur={() => setQuestionCount((n) => clampQuestions(n))}
                  />
                  <button
                    type="button"
                    aria-label="More questions"
                    onClick={() => setQuestionCount((n) => clampQuestions(n + 1))}
                    disabled={questionCount >= MAX_QUESTIONS}
                    className="px-3 py-2 text-lg font-bold text-ink/70 disabled:opacity-30"
                  >
                    +
                  </button>
                </div>
              </div>
              <div className="text-sm font-bold">
                Difficulty
                <div
                  role="radiogroup"
                  aria-label="Difficulty"
                  className="mt-1 grid grid-cols-3 gap-1 rounded-xl border border-sky-200 bg-white p-1"
                >
                  {DIFFICULTIES.map(([value, label]) => (
                    <button
                      key={value}
                      type="button"
                      role="radio"
                      aria-checked={difficulty === value}
                      onClick={() => setDifficulty(value)}
                      className={`rounded-lg py-1.5 text-sm font-bold ${
                        difficulty === value ? "bg-brand text-white" : "text-ink/70 hover:bg-sky-50"
                      }`}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <label className="text-sm font-bold">
                Language
                <input
                  className={`mt-1 ${FIELD}`}
                  list="ai-language-suggestions"
                  value={language}
                  onChange={(e) => setLanguage(e.target.value)}
                />
                <datalist id="ai-language-suggestions">
                  {LANGUAGE_SUGGESTIONS.map((l) => (
                    <option key={l} value={l} />
                  ))}
                </datalist>
              </label>
            </div>
            {modelOptions.length > 0 && (
              <details className="pt-1 text-sm">
                <summary className="cursor-pointer font-bold text-ink/70">
                  Advanced · Model: {modelLabel(model)}
                </summary>
                <select
                  aria-label="Gemini model"
                  className={`mt-2 ${FIELD}`}
                  value={modelOptions.some((m) => m.id === model) ? model : modelOptions[0]?.id}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {modelOptions.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-ink/55">
                  If the model is busy, LanQuiz switches to Gemini 3.5 Flash-Lite automatically.
                </p>
              </details>
            )}
          </Step>

          <div className="space-y-2 border-t border-amber-200/70 pt-4">
            <button
              type="button"
              disabled={busy || extracting || Boolean(blocker)}
              onClick={() => void generate()}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-4 py-3 font-extrabold text-ink disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy && (
                <span
                  className="h-4 w-4 animate-spin rounded-full border-2 border-ink/30 border-t-ink"
                  aria-hidden
                />
              )}
              {busy ? `Generating… ${elapsed}s` : "Generate quiz draft"}
            </button>
            <p className="text-center text-xs text-ink/55" aria-live="polite">
              {busy
                ? "Usually 5–20 seconds."
                : (blocker ?? "Questions are added to the editor below for you to review before saving.")}
            </p>
            {notice && (
              <div
                className={`rounded-xl border px-3 py-2 text-sm ${NOTICE_STYLES[notice.tone]}`}
                role={notice.tone === "error" ? "alert" : "status"}
              >
                {notice.text}
              </div>
            )}
            {rateLimit?.warning && (
              <div className={`rounded-xl border px-3 py-2 text-sm ${NOTICE_STYLES.warning}`} role="status">
                {rateLimit.message ||
                  `Approaching rate limit (${rateLimit.remaining_requests ?? "?"} remaining).`}
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  );
}
