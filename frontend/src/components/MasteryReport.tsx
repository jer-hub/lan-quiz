import { useEffect, useState } from "react";
import { api } from "../api";
import type { MasteryCell, MasteryReport as Report } from "../shared";

function formatAccuracy(accuracy: number) {
  return `${Number.isInteger(accuracy) ? accuracy : accuracy.toFixed(1)}%`;
}

function Cell({ cell }: { cell: MasteryCell }) {
  if (cell.accuracy == null) {
    return (
      <td className="px-3 py-2 text-xs text-ink/50" title={`${cell.answer_count} answered`}>
        not enough answers
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

/** Downloads the mastery report as CSV: one row per student, one column per topic. */
function ExportCsvButton({ classId }: { classId: number }) {
  const [error, setError] = useState<string | null>(null);

  const exportCsv = async () => {
    setError(null);
    try {
      const blob = await api.exportMasteryReport(classId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `mastery-class-${classId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
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

  useEffect(() => {
    let cancelled = false;
    setReport(null);
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
  }, [classId]);

  if (error) return <p className="text-danger">{error}</p>;
  if (!report) return <p className="text-ink/60">Loading…</p>;

  return (
    <div>
      <p className="text-sm text-ink/70">
        Accuracy over each student's most recent {report.window} answers on a topic. A topic is
        mastered at {report.mastery_threshold}% or above; fewer than {report.min_answers} answers is
        not enough to say.
      </p>
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
          No answers on tagged questions yet. Add topics to questions, then assign the quiz as homework.
        </p>
      )}
      <p className="mt-3 text-sm text-ink/60">
        {report.untagged_answer_count} answer{report.untagged_answer_count === 1 ? " was" : "s were"} on
        questions without topics and {report.untagged_answer_count === 1 ? "is" : "are"} not in this report.
      </p>
      <ExportCsvButton classId={classId} />
    </div>
  );
}
