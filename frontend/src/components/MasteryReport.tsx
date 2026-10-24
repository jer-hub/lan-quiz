import { useEffect, useState } from "react";
import { api } from "../api";
import { NOT_ENOUGH_ANSWERS, saveDownload } from "../shared";
import type { MasteryCell, MasteryReport as Report } from "../shared";

function formatAccuracy(accuracy: number) {
  return `${Number.isInteger(accuracy) ? accuracy : accuracy.toFixed(1)}%`;
}

function Cell({ cell }: { cell: MasteryCell }) {
  if (cell.accuracy == null) {
    return (
      <td className="px-3 py-2 text-xs text-ink/50" title={`${cell.answer_count} answered`}>
        {NOT_ENOUGH_ANSWERS}
      </td>
    );
  }
  return (
    <td
      className={`px-3 py-2 ${cell.mastered ? "bg-success/15 font-bold text-ink" : ""}`}
      title={`${cell.answer_count} most recent answers`}
    >
      {formatAccuracy(cell.accuracy)}
      {cell.mastered && <span className="ml-1 text-success">✓ mastered</span>}
    </td>
  );
}

/** The class's mastery threshold: shows the current one and saves a new whole-number percentage. */
function ThresholdSetting({
  classId,
  threshold,
  onSaved,
}: {
  classId: number;
  threshold: number;
  onSaved: () => void;
}) {
  const [value, setValue] = useState(String(threshold));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setValue(String(threshold)), [threshold]);

  const parsed = Number(value);
  const valid = /^\d+$/.test(value.trim()) && parsed >= 1 && parsed <= 100;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!valid) return;
    setSaving(true);
    setError(null);
    try {
      await api.updateClass(classId, { mastery_threshold: parsed });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the mastery threshold");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={save} className="mt-3 flex flex-wrap items-center gap-2 text-sm">
      <label htmlFor={`mastery-threshold-${classId}`} className="font-bold">
        Mastery threshold
      </label>
      <input
        id={`mastery-threshold-${classId}`}
        type="number"
        min={1}
        max={100}
        step={1}
        inputMode="numeric"
        className="w-20 rounded-xl border border-sky-200 px-3 py-2"
        value={value}
        onChange={(e) => setValue(e.target.value)}
      />
      <span>%</span>
      <button
        type="submit"
        disabled={!valid || saving || parsed === threshold}
        className="rounded-xl bg-brand px-4 py-2 font-bold text-white disabled:opacity-50"
      >
        {saving ? "Saving…" : "Save"}
      </button>
      {!valid && <span className="text-danger">Enter a whole number from 1 to 100.</span>}
      {error && <span className="text-danger">{error}</span>}
    </form>
  );
}

/** Downloads the mastery report as CSV: one row per student, one column per topic. */
function ExportCsvButton({ classId }: { classId: number }) {
  const [error, setError] = useState<string | null>(null);

  const exportCsv = async () => {
    setError(null);
    try {
      saveDownload(await api.exportMasteryReport(classId), `mastery-class-${classId}.csv`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Export failed");
    }
  };

  return (
    <div className="mt-3 flex flex-wrap items-center gap-3">
      <button
        type="button"
        onClick={() => void exportCsv()}
        className="rounded-xl bg-accent px-4 py-2 font-extrabold text-ink"
      >
        Export CSV
      </button>
      {error && <span className="text-sm text-danger">{error}</span>}
    </div>
  );
}

/** The class's mastery report: each student's accuracy on each topic, mastered topics marked. */
export default function MasteryReport({ classId }: { classId: number }) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setError(null);
    api
      .getMasteryReport(classId)
      .then((r) => {
        if (!cancelled) setReport(r);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : "Failed to load the mastery report");
      });
    return () => {
      cancelled = true;
    };
  }, [classId, reloads]);

  // A different class starts from a blank report; a reload after saving keeps the table on screen.
  useEffect(() => setReport(null), [classId]);

  if (error) return <p className="text-danger">{error}</p>;
  if (!report) return <p className="text-ink/60">Loading…</p>;

  return (
    <div>
      <p className="text-sm text-ink/70">
        Accuracy over each student's most recent {report.window} answers on a topic. A topic is
        mastered at {report.mastery_threshold}% or above; fewer than {report.min_answers} answers is
        not enough to say.
      </p>
      <ThresholdSetting
        classId={classId}
        threshold={report.mastery_threshold}
        onSaved={() => setReloads((n) => n + 1)}
      />
      {report.topics.length > 0 ? (
        <div className="mt-3 overflow-x-auto rounded-2xl border border-sky-200 bg-white">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-sky-50">
              <tr>
                <th className="px-3 py-2 font-bold">Student</th>
                {report.topics.map((t) => (
                  <th key={t} className="px-3 py-2 font-bold">
                    {t}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {report.rows.map((row) => (
                <tr key={row.student_id} className="border-t border-sky-100">
                  <td className="px-3 py-2 font-semibold">
                    {row.display_name}{" "}
                    <span className="font-mono text-xs text-ink/50">{row.student_code}</span>
                  </td>
                  {row.cells.map((cell) => (
                    <Cell key={cell.topic} cell={cell} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="mt-3 text-ink/50">
          No answers on questions with topics yet. Add topics to questions, then assign the quiz as homework.
        </p>
      )}
      <p className="mt-3 text-sm text-ink/60">
        {report.answers_without_topics} answer{report.answers_without_topics === 1 ? " was" : "s were"} on
        questions without topics and {report.answers_without_topics === 1 ? "is" : "are"} not in this report.
      </p>
      <ExportCsvButton classId={classId} />
    </div>
  );
}
