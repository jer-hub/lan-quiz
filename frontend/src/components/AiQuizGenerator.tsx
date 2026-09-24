import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import type { AiPresets, AiRateLimit, Question } from "../shared";

const LS_PROVIDER = "lanquiz_ai_provider";
const LS_MODEL = "lanquiz_ai_model";
const LS_KEY = "lanquiz_ai_key";
const LS_BASE = "lanquiz_ai_base_url";
const LS_REMEMBER = "lanquiz_ai_remember";

export interface GeneratedQuizPatch {
  title: string;
  description: string;
  questions: Question[];
}

interface Props {
  onGenerated: (quiz: GeneratedQuizPatch) => void;
}

function loadRemember(): boolean {
  return localStorage.getItem(LS_REMEMBER) !== "0";
}

export default function AiQuizGenerator({ onGenerated }: Props) {
  const [open, setOpen] = useState(false);
  const [presets, setPresets] = useState<AiPresets | null>(null);
  const [provider, setProvider] = useState(
    () => localStorage.getItem(LS_PROVIDER) || "groq",
  );
  const [model, setModel] = useState(
    () => localStorage.getItem(LS_MODEL) || "qwen/qwen3-32b",
  );
  const [apiKey, setApiKey] = useState(() => localStorage.getItem(LS_KEY) || "");
  const [baseUrl, setBaseUrl] = useState(() => localStorage.getItem(LS_BASE) || "");
  const [remember, setRemember] = useState(loadRemember);
  const [topic, setTopic] = useState("");
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
  const [error, setError] = useState<string | null>(null);
  const [rateLimit, setRateLimit] = useState<AiRateLimit | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!open || presets) return;
    void api
      .getAiPresets()
      .then(setPresets)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load AI presets"));
  }, [open, presets]);

  const providerMeta = useMemo(
    () => presets?.providers.find((p) => p.id === provider) || null,
    [presets, provider],
  );

  const modelOptions = providerMeta?.models || [];
  const maxChars = presets?.extract?.max_extract_chars ?? 24_000;

  useEffect(() => {
    if (!providerMeta) return;
    if (provider === "custom") return;
    const ids = new Set(modelOptions.map((m) => m.id));
    if (!ids.has(model) && providerMeta.default_model) {
      setModel(providerMeta.default_model);
    }
  }, [provider, providerMeta, model, modelOptions]);

  const persistPrefs = () => {
    localStorage.setItem(LS_REMEMBER, remember ? "1" : "0");
    localStorage.setItem(LS_PROVIDER, provider);
    localStorage.setItem(LS_MODEL, model);
    if (baseUrl) localStorage.setItem(LS_BASE, baseUrl);
    else localStorage.removeItem(LS_BASE);
    if (remember && apiKey) localStorage.setItem(LS_KEY, apiKey);
    else localStorage.removeItem(LS_KEY);
  };

  const onFileChange = async (file: File | null) => {
    setError(null);
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
      else if (result.truncated) {
        setExtractWarning("Text was truncated to fit free-tier token limits.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Extract failed");
    } finally {
      setExtracting(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  const generate = async () => {
    setError(null);
    setRateLimit(null);
    const topicTrim = topic.trim();
    const materialTrim = sourceMaterial.trim();
    if (topicTrim.length < 3 && materialTrim.length < 20) {
      setError("Enter a topic and/or upload/paste source material");
      return;
    }
    if (!apiKey.trim()) {
      setError("Paste your API key (free tier keys supported for Groq)");
      return;
    }
    if (provider === "custom" && !baseUrl.trim()) {
      setError("Custom provider needs a base URL (…/v1)");
      return;
    }
    setBusy(true);
    persistPrefs();
    try {
      const result = await api.generateQuiz({
        provider,
        model: model.trim(),
        api_key: apiKey.trim(),
        base_url: provider === "custom" ? baseUrl.trim() : baseUrl.trim() || null,
        topic: topicTrim,
        source_material: materialTrim || null,
        question_count: questionCount,
        difficulty,
        language,
      });
      setRateLimit(result.rate_limit);
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
      setError(e instanceof Error ? e.message : "Generation failed");
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
        <div>
          <p className="font-display text-xl text-ink">AI Quiz Generator (Free tier supported)</p>
          <p className="text-sm text-ink/65">
            Optional cloud tool — paste your own key. Live games work offline without AI.
          </p>
        </div>
        <span className="shrink-0 rounded-lg bg-white/80 px-3 py-1 text-sm font-bold text-ink/70">
          {open ? "Hide" : "Show"}
        </span>
      </button>

      {open && (
        <div className="space-y-3 border-t border-amber-200/70 px-4 py-4">
          {presets?.note && <p className="text-xs text-ink/55">{presets.note}</p>}

          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
              {error}
            </div>
          )}
          {rateLimit?.warning && (
            <div
              className="rounded-xl border border-amber-300 bg-amber-100 px-3 py-2 text-sm text-amber-950"
              role="status"
            >
              {rateLimit.message ||
                `Approaching rate limit (${rateLimit.remaining_requests ?? "?"} remaining).`}
            </div>
          )}
          {extractWarning && (
            <div
              className="rounded-xl border border-amber-300 bg-amber-100 px-3 py-2 text-sm text-amber-950"
              role="status"
            >
              {extractWarning}
            </div>
          )}

          <label className="block text-sm font-bold">
            Topic / focus
            <textarea
              className="mt-1 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-normal"
              rows={2}
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Photosynthesis for grade 8 — or leave brief if using a file"
            />
          </label>

          <div className="space-y-2">
            <label className="block text-sm font-bold">
              Lesson file (optional)
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.docx,.txt,.md,application/pdf,text/plain,text/markdown"
                className="mt-1 block w-full text-sm font-normal file:mr-3 file:rounded-lg file:border-0 file:bg-brand file:px-3 file:py-2 file:font-bold file:text-white"
                disabled={extracting || busy}
                onChange={(e) => void onFileChange(e.target.files?.[0] ?? null)}
              />
            </label>
            <p className="text-xs text-ink/50">
              PDF, DOCX, TXT, or MD — max 5 MB. Extracted on this LAN server; only text is sent to
              Groq. No OCR for scanned PDFs.
            </p>
            {extractMeta && (
              <p className="text-xs font-semibold text-ink/70">
                {extractMeta.filename}: {extractMeta.char_count.toLocaleString()} chars
                {extractMeta.truncated ? " (truncated)" : ""}
              </p>
            )}
          </div>

          <label className="block text-sm font-bold">
            Source material
            <textarea
              className="mt-1 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-mono text-sm font-normal"
              rows={6}
              value={sourceMaterial}
              maxLength={maxChars}
              onChange={(e) => {
                setSourceMaterial(e.target.value);
                setExtractMeta(null);
                setExtractWarning(null);
              }}
              placeholder="Upload a file above, or paste lesson notes here. Edit before generating."
            />
            <span className="mt-1 block text-xs font-normal text-ink/50">
              {sourceMaterial.length.toLocaleString()} / {maxChars.toLocaleString()} characters
            </span>
          </label>

          <div className="grid gap-3 sm:grid-cols-3">
            <label className="text-sm font-bold">
              Questions
              <input
                type="number"
                min={3}
                max={20}
                className="mt-1 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-normal"
                value={questionCount}
                onChange={(e) => setQuestionCount(Number(e.target.value) || 8)}
              />
            </label>
            <label className="text-sm font-bold">
              Difficulty
              <select
                className="mt-1 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-normal"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
              >
                <option value="easy">Easy</option>
                <option value="medium">Medium</option>
                <option value="hard">Hard</option>
              </select>
            </label>
            <label className="text-sm font-bold">
              Language
              <input
                className="mt-1 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-normal"
                value={language}
                onChange={(e) => setLanguage(e.target.value)}
              />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-bold">
              Provider
              <select
                className="mt-1 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-normal"
                value={provider}
                onChange={(e) => setProvider(e.target.value)}
              >
                {(presets?.providers || [{ id: "groq", label: "Groq (free tier supported)" }]).map(
                  (p) => (
                    <option key={p.id} value={p.id}>
                      {p.label}
                    </option>
                  ),
                )}
              </select>
            </label>
            <label className="text-sm font-bold">
              Model
              {modelOptions.length > 0 && (
                <select
                  className="mt-1 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-normal"
                  value={modelOptions.some((m) => m.id === model) ? model : modelOptions[0]?.id}
                  onChange={(e) => setModel(e.target.value)}
                >
                  {modelOptions.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.label}
                    </option>
                  ))}
                </select>
              )}
              <input
                className="mt-2 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-mono text-sm font-normal"
                value={model}
                onChange={(e) => setModel(e.target.value)}
                placeholder="Or type any model id"
              />
            </label>
          </div>

          {(provider === "custom" || providerMeta) && (
            <label className="block text-sm font-bold">
              {provider === "custom" ? "Base URL (required)" : "Base URL override (optional)"}
              <input
                className="mt-1 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-mono text-sm font-normal"
                value={baseUrl}
                onChange={(e) => setBaseUrl(e.target.value)}
                placeholder={providerMeta?.base_url || "https://api.example.com/v1"}
              />
            </label>
          )}

          <label className="block text-sm font-bold">
            API key
            <input
              type="password"
              className="mt-1 w-full rounded-xl border border-sky-200 bg-white px-3 py-2 font-mono text-sm font-normal"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Paste key — never stored on the LanQuiz server"
              autoComplete="off"
            />
          </label>

          <div className="flex flex-wrap items-center justify-between gap-3">
            <label className="flex items-center gap-2 text-sm font-semibold text-ink/80">
              <input
                type="checkbox"
                checked={remember}
                onChange={(e) => setRemember(e.target.checked)}
              />
              Remember key on this device
            </label>
            {providerMeta?.docs_url && (
              <a
                href={providerMeta.docs_url}
                target="_blank"
                rel="noreferrer"
                className="text-sm font-bold text-brand-dark underline"
              >
                Get a free-tier key
              </a>
            )}
          </div>

          <button
            type="button"
            disabled={busy || extracting}
            onClick={() => void generate()}
            className="w-full rounded-xl bg-accent px-4 py-3 font-extrabold text-ink disabled:opacity-50 sm:w-auto"
          >
            {extracting ? "Extracting…" : busy ? "Generating…" : "Generate quiz draft"}
          </button>
          <p className="text-xs text-ink/50">
            Review and edit questions below, then Save. Defaults: Groq + qwen/qwen3-32b (alias
            qwen/qwen3.8-27b) or openai/gpt-oss-120b.
          </p>
        </div>
      )}
    </section>
  );
}
