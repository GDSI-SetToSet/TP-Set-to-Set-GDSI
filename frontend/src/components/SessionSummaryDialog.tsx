import { Clock, Dumbbell, ListChecks, TrendingDown, TrendingUp, Trophy } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getWorkoutSessionSummary } from '../services/routineTemplateService';
import type { WorkoutSessionSummary } from '../types/routineTemplate';
import '../styles/session-summary.css';

interface SessionSummaryDialogProps {
  sessionId: string;
  onClose: () => void;
}

function formatKg(value: number): string {
  return value.toLocaleString('es-AR', { maximumFractionDigits: 2 });
}

function formatDuration(totalSeconds: number): string {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) return `${hours} h ${minutes} min`;
  return minutes > 0 ? `${minutes} min ${seconds} s` : `${seconds} s`;
}

function HistoryComparison({ summary }: { summary: WorkoutSessionSummary }) {
  const { history } = summary;
  if (history.previous_sessions_count === 0) {
    return <p className="session-summary__history">Primera sesión registrada de {summary.day_name}. La próxima vas a poder compararte.</p>;
  }
  if (history.tonnage_delta_percent === null) {
    return <p className="session-summary__history">Promedio anterior de {summary.day_name}: {formatKg(history.average_tonnage_kg ?? 0)} kg.</p>;
  }
  const delta = history.tonnage_delta_percent;
  const sessionsLabel = history.previous_sessions_count === 1 ? 'la sesión anterior' : `tus ${history.previous_sessions_count} sesiones anteriores`;
  if (delta === 0) {
    return <p className="session-summary__history">Mismo tonelaje que el promedio de {sessionsLabel} de {summary.day_name}.</p>;
  }
  const Icon = delta > 0 ? TrendingUp : TrendingDown;
  return (
    <p className={`session-summary__history session-summary__history--${delta > 0 ? 'up' : 'down'}`}>
      <Icon size={18} aria-hidden="true" />
      <span>
        <strong>{delta > 0 ? '+' : ''}{delta.toLocaleString('es-AR')} %</strong> de tonelaje frente al promedio de {sessionsLabel} de {summary.day_name} ({formatKg(history.average_tonnage_kg ?? 0)} kg).
      </span>
    </p>
  );
}

export function SessionSummaryDialog({ sessionId, onClose }: SessionSummaryDialogProps) {
  const [summary, setSummary] = useState<WorkoutSessionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const closeButton = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    let cancelled = false;
    getWorkoutSessionSummary(sessionId)
      .then((data) => { if (!cancelled) setSummary(data); })
      .catch(() => { if (!cancelled) setError('No pudimos cargar el resumen de tu sesión. Igual quedó registrada.'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [sessionId]);

  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    closeButton.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onCloseRef.current(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  return (
    <div className="workout-celebration" role="dialog" aria-modal="true" aria-labelledby="workout-celebration-title">
      <div className="workout-confetti" aria-hidden="true">{Array.from({ length: 28 }, (_, index) => <span key={index} className={`workout-confetti__piece workout-confetti__piece--${index % 6}`} style={{ left: `${(index * 37) % 100}%`, animationDelay: `${(index % 8) * 0.12}s` }} />)}</div>
      <div className="workout-celebration__card session-summary">
        <span className="workout-celebration__icon" aria-hidden="true">✦</span>
        <h2 id="workout-celebration-title">¡Felicitaciones!</h2>
        <p>Terminaste el entrenamiento{summary ? ` de ${summary.day_name}` : ''}. Esto es lo que lograste:</p>

        {loading && <p className="session-summary__status" role="status">Calculando tu resumen…</p>}
        {error && <p className="session-summary__status session-summary__status--error" role="alert">{error}</p>}

        {summary && <>
          <dl className="session-summary__metrics">
            <div>
              <dt><Dumbbell size={16} aria-hidden="true" /> Tonelaje total</dt>
              <dd>{formatKg(summary.total_tonnage_kg)} kg</dd>
            </div>
            <div>
              <dt><Clock size={16} aria-hidden="true" /> Duración</dt>
              <dd>{formatDuration(summary.duration_seconds)}</dd>
            </div>
            <div>
              <dt><ListChecks size={16} aria-hidden="true" /> Series</dt>
              <dd>
                {summary.programmed_sets === null
                  ? `${summary.completed_sets} completadas`
                  : `${summary.completed_sets} / ${summary.programmed_sets}`}
              </dd>
            </div>
          </dl>

          <HistoryComparison summary={summary} />

          {summary.personal_records.length > 0 && (
            <section className="session-summary__prs" aria-labelledby="session-summary-prs-title">
              <h3 id="session-summary-prs-title"><Trophy size={18} aria-hidden="true" /> {summary.personal_records.length === 1 ? 'Nuevo récord personal' : `${summary.personal_records.length} récords personales`}</h3>
              <ul>
                {summary.personal_records.map((record) => (
                  <li key={record.exercise_id}>
                    <strong>{record.exercise_name}</strong>
                    <span>
                      {formatKg(record.weight_kg)} kg × {record.reps_completed}
                      {record.previous_weight_kg === null ? ' · primer récord' : ` · antes ${formatKg(record.previous_weight_kg)} kg`}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </>}

        <button ref={closeButton} type="button" onClick={onClose}>Continuar</button>
      </div>
    </div>
  );
}
