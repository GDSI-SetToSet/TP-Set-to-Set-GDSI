import { Activity, Clock, Dumbbell, ListChecks, TrendingDown, TrendingUp, Trophy, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { BodyMapSelector } from './BodyMapSelector';
import type { ReportZoneInput } from '../types/bodyMapReport';
import { createBodyMapReport } from '../services/bodyMapReportService';
import { reportWorkoutSessionRpe, getWorkoutSessionSummary } from '../services/routineTemplateService';
import type { WorkoutSession, WorkoutSessionSummary } from '../types/routineTemplate';
import { shouldPromptForRpe } from '../utils/sessionRpeState.mjs';
import '../styles/session-summary.css';

interface SessionSummaryDialogProps {
  sessionId: string;
  onClose: () => void;
  onRpeSaved?: (session: WorkoutSession) => void;
  onZonesReported?: () => void;
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

export function SessionSummaryDialog({ sessionId, onClose, onRpeSaved, onZonesReported }: SessionSummaryDialogProps) {
  const [summary, setSummary] = useState<WorkoutSessionSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [ratingOpen, setRatingOpen] = useState(false);
  const [selectedRpe, setSelectedRpe] = useState<number | null>(null);
  const [selectedZones, setSelectedZones] = useState<ReportZoneInput[]>([]);
  const [savingRpe, setSavingRpe] = useState(false);
  const [rpeError, setRpeError] = useState('');
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

  const handleSaveRpe = async () => {
    if (selectedRpe === null || savingRpe) return;
    setSavingRpe(true);
    setRpeError('');
    try {
      let reportedZones = false;
      if (selectedZones.length > 0) {
        await createBodyMapReport({ context: 'POST_SESSION', session_id: sessionId, zones: selectedZones });
        setSelectedZones([]);
        reportedZones = true;
      }
      const updatedSession = await reportWorkoutSessionRpe(sessionId, selectedRpe);
      setSummary((current) => current ? { ...current, rpe: updatedSession.rpe ?? selectedRpe } : current);
      onRpeSaved?.(updatedSession);
      if (reportedZones) onZonesReported?.();
      setRatingOpen(false);
    } catch {
      setRpeError('No pudimos guardar tu calificación. Intentá nuevamente.');
    } finally {
      setSavingRpe(false);
    }
  };

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

        {shouldPromptForRpe(summary) && (
          <section className="session-summary__rpe-form" aria-labelledby="session-summary-rpe-title">
            <h3 id="session-summary-rpe-title">¿Cómo calificarías tu esfuerzo?</h3>
            <p>Indicá tu esfuerzo percibido (RPE) del 1 al 10, o continuá para completarlo después.</p>
            <div className="session-summary__rpe-options" role="radiogroup" aria-label="Escala de esfuerzo percibido de 1 a 10">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={selectedRpe === value}
                  className={selectedRpe === value ? 'session-summary__rpe-option session-summary__rpe-option--selected' : 'session-summary__rpe-option'}
                  onClick={() => setSelectedRpe(value)}
                >
                  {value}
                </button>
              ))}
            </div>
            <div className="session-summary__rpe-follow-up">
              <button
                type="button"
                className="session-summary__rpe-save"
                disabled={selectedRpe === null || savingRpe}
                onClick={() => void handleSaveRpe()}
              >
                {savingRpe ? 'Guardando…' : 'Guardar reporte'}
              </button>
              <button
                type="button"
                className="session-summary__rate-link"
                onClick={() => {
                  setRatingOpen(true);
                  setRpeError('');
                }}
              >
                Reportar molestias o dolor (opcional)
              </button>
            </div>
            {rpeError && !ratingOpen && <p className="session-summary__rpe-error" role="alert">{rpeError}</p>}
          </section>
        )}
        {summary && summary.rpe !== null && summary.rpe !== undefined && (
          <p className="session-summary__rpe-saved" role="status">Esfuerzo calificado: {summary.rpe}/10</p>
        )}
        <button ref={closeButton} type="button" onClick={onClose}>
          {shouldPromptForRpe(summary) ? 'Continuar sin reportar' : 'Continuar'}
        </button>
      </div>
      {ratingOpen && <div className="session-rating-overlay" role="dialog" aria-modal="true" aria-labelledby="session-rating-title">
        <section className="session-rating-dialog">
          <button type="button" className="session-rating-dialog__close" aria-label="Cerrar formulario" onClick={() => setRatingOpen(false)}><X size={20} /></button>
          <div className="session-rating-dialog__icon" aria-hidden="true"><Activity size={24} /></div>
          <h2 id="session-rating-title">¿Cómo estuvo tu entrenamiento?</h2>
          <p className="session-rating-dialog__intro">Compartí tu esfuerzo y cualquier molestia para que tu entrenador pueda acompañar tu progreso.</p>

          <div className="session-rating-dialog__field">
            <h3>¿Cómo calificarías tu esfuerzo?</h3>
            <p>Indicá tu nivel de esfuerzo percibido en una escala del 1 al 10.</p>
            <div className="session-rating-dialog__options" role="radiogroup" aria-label="Escala de esfuerzo percibido de 1 a 10">
              {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => (
                <button
                  key={value}
                  type="button"
                  role="radio"
                  aria-checked={selectedRpe === value}
                  className={selectedRpe === value ? 'session-rating-dialog__option session-rating-dialog__option--selected' : 'session-rating-dialog__option'}
                  onClick={() => setSelectedRpe(value)}
                >{value}<span>{value <= 2 ? 'Muy suave' : value <= 4 ? 'Suave' : value <= 6 ? 'Moderado' : value <= 8 ? 'Duro' : 'Máximo'}</span></button>
              ))}
            </div>
          </div>

          <div className="session-rating-dialog__field session-rating-dialog__body-map">
            <h3>¿Sentiste molestias o dolor?</h3>
            <p>Este registro es opcional. Marcá las zonas y el tipo de sensación.</p>
            <BodyMapSelector selectedZones={selectedZones} onChange={setSelectedZones} />
          </div>
          {rpeError && <p className="session-rating-dialog__error" role="alert">{rpeError}</p>}
          <footer className="session-rating-dialog__actions">
            <button type="button" className="session-rating-dialog__cancel" onClick={() => setRatingOpen(false)} disabled={savingRpe}>Ahora no</button>
            <button type="button" className="session-rating-dialog__save" disabled={selectedRpe === null || savingRpe} onClick={() => void handleSaveRpe()}>
              {savingRpe ? 'Guardando…' : 'Guardar reporte'}
            </button>
          </footer>
        </section>
      </div>}
    </div>
  );
}
