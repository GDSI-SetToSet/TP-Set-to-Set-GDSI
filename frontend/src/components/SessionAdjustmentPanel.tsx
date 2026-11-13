import axios from 'axios';
import { AlertTriangle, CheckCircle2, Save } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { getExercises } from '../services/exerciseService';
import { getSessionAdjustment, saveSessionAdjustment } from '../services/sessionAdjustmentService';
import type { Exercise } from '../types/exercise';
import type { AdjustmentBlock, AdjustmentEntry, SessionAdjustmentContext } from '../types/sessionAdjustment';
import { formatWeight } from '../utils/dailyRoutineFormat.mjs';
import {
  adjustmentStatusMessage,
  countChanges,
  entryError,
  painIntensityLabel,
  toAdjustmentInput,
} from '../utils/sessionAdjustment.mjs';

interface ProblemDetails {
  detail?: string | { detail?: string; errors?: { field: string; message: string }[] };
  errors?: { field: string; message: string }[];
}

function SessionReports({ context }: { context: SessionAdjustmentContext }) {
  return (
    <div className="session-adjustment__reports">
      <section>
        <h4>Cargas registradas</h4>
        {context.logged_exercises.length === 0 ? (
          <p className="daily-routines__muted">No registró series.</p>
        ) : (
          <ul>
            {context.logged_exercises.map((exercise) => (
              <li key={exercise.exercise_id}>
                <strong>{exercise.exercise_name}</strong>:{' '}
                {exercise.sets.map((set) => `${set.reps_completed} × ${formatWeight(set.weight_kg)}`).join(' · ')}
              </li>
            ))}
          </ul>
        )}
        <p>RPE: <strong>{context.rpe !== null ? `${context.rpe}/10` : 'Sin reportar'}</strong></p>
      </section>
      <section>
        <h4>Molestias y dolores</h4>
        {context.pain_zones.length === 0 ? (
          <p className="daily-routines__muted">No reportó molestias en esta sesión.</p>
        ) : (
          <ul>
            {context.pain_zones.map((zone, index) => (
              <li key={`${zone.zone}-${index}`}>
                <span className={`session-adjustment__pain session-adjustment__pain--${zone.intensity.toLowerCase()}`}>
                  {painIntensityLabel(zone.intensity)}
                </span>{' '}
                {zone.zone_label}{zone.exercise_name ? ` (${zone.exercise_name})` : ' (post-sesión)'}
              </li>
            ))}
          </ul>
        )}
      </section>
      <section>
        <h4>Pedidos de reemplazo</h4>
        {context.replacement_requests.length === 0 ? (
          <p className="daily-routines__muted">No pidió reemplazos.</p>
        ) : (
          <ul>
            {context.replacement_requests.map((request) => (
              <li key={request.original_exercise_id}>
                {request.replacement_exercise_name
                  ? <><strong>{request.original_exercise_name}</strong> → {request.replacement_exercise_name}</>
                  : <><strong>{request.original_exercise_name}</strong>: lo salteó (sin alternativa disponible)</>}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** US-26: ajustar el mismo día de rutina para la próxima sesión, desde la sesión finalizada. */
export function SessionAdjustmentPanel({ sessionId }: { sessionId: string }) {
  const [context, setContext] = useState<SessionAdjustmentContext | null>(null);
  const [library, setLibrary] = useState<Exercise[]>([]);
  const [blocks, setBlocks] = useState<AdjustmentBlock[]>([]);
  const [note, setNote] = useState('');
  const [loadError, setLoadError] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [problems, setProblems] = useState<{ field: string; message: string }[]>([]);
  const [message, setMessage] = useState('');
  const alertRef = useRef<HTMLDivElement>(null);

  function load(next: SessionAdjustmentContext) {
    setContext(next);
    setBlocks(next.blocks);
    setNote(next.current_adjustment?.note ?? '');
  }

  useEffect(() => {
    let active = true;
    Promise.all([getSessionAdjustment(sessionId), getExercises().catch(() => [])])
      .then(([loaded, exercises]) => {
        if (!active) return;
        load(loaded);
        setLibrary(exercises);
      })
      .catch(() => { if (active) setLoadError('No pudimos cargar la sesión para ajustarla. Intentá nuevamente.'); });
    return () => { active = false; };
  }, [sessionId]);

  useEffect(() => {
    if (error) alertRef.current?.focus();
  }, [error]);

  if (loadError) return <p className="form-alert" role="alert">{loadError}</p>;
  if (!context) return <p role="status">Cargando sesión…</p>;

  const names = new Map<string, string>(library.map((exercise) => [exercise.id, exercise.name]));
  context.blocks.forEach((block) => block.exercises.forEach((entry) => {
    if (!names.has(entry.exercise_id)) names.set(entry.exercise_id, entry.exercise_name);
  }));
  const changes = countChanges(context.blocks, blocks);
  const noteChanged = note.trim() !== (context.current_adjustment?.note ?? '');
  const status = adjustmentStatusMessage(context.current_adjustment);

  const update = (b: number, e: number, change: Partial<AdjustmentEntry>) => {
    setMessage('');
    setProblems((current) => current.filter((problem) => !entryError([problem], b, e)));
    setBlocks((current) => current.map((block, bi) => (bi !== b ? block : {
      ...block,
      exercises: block.exercises.map((entry, ei) => (ei !== e ? entry : { ...entry, ...change })),
    })));
  };

  async function save() {
    setSaving(true);
    setError('');
    setProblems([]);
    setMessage('');
    try {
      const saved = await saveSessionAdjustment(sessionId, toAdjustmentInput(blocks, note));
      load(await getSessionAdjustment(sessionId));
      setMessage(saved.status === 'PENDING'
        ? 'Ajuste guardado. El alumno está entrenando: se aplicará cuando termine su sesión en curso.'
        : 'Ajuste guardado. El alumno lo verá en su próxima sesión de este día.');
    } catch (caught) {
      if (axios.isAxiosError<ProblemDetails>(caught)) {
        const data = caught.response?.data;
        const detail = typeof data?.detail === 'object' ? data.detail : null;
        setProblems(detail?.errors ?? data?.errors ?? []);
        setError((detail?.detail ?? (typeof data?.detail === 'string' ? data.detail : undefined)) ?? 'Revisá los datos del ajuste.');
      } else {
        setError('No pudimos guardar el ajuste. Intentá nuevamente.');
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="session-adjustment" aria-label={`Ajustar la próxima sesión de ${context.day_name}`}>
      <SessionReports context={context} />

      <h4 className="session-adjustment__title">Próxima sesión de “{context.day_name}”</h4>
      {status && <p className="session-adjustment__status" role="status">{status}</p>}
      {!context.can_adjust ? (
        <p className="form-alert" role="alert">{context.blocked_reason}</p>
      ) : (
        <form className="rt-form" onSubmit={(event) => { event.preventDefault(); void save(); }}>
          {error && (
            <div className="rt-alert" role="alert" tabIndex={-1} ref={alertRef}>
              <AlertTriangle size={20} aria-hidden />
              <div>
                <strong>{error}</strong>
                {problems.length > 0 && <ul>{problems.map((problem) => <li key={problem.field + problem.message}>{problem.message}</li>)}</ul>}
              </div>
            </div>
          )}
          {message && <p className="profile-success" role="status"><CheckCircle2 size={18} aria-hidden /> {message}</p>}

          {blocks.map((block, b) => (
            <div className="rt-block" key={`${block.name}-${b}`}>
              <h3>{block.name}<small>{block.exercises.length} ejercicios</small></h3>
              {block.exercises.map((entry, e) => {
                const failure = entryError(problems, b, e);
                const id = `adj-${sessionId}-${b}-${e}`;
                return (
                  <div className={`rt-row${failure ? ' rt-row--invalid' : ''}`} key={`${b}-${e}`}>
                    <label className="rt-row__exercise">Ejercicio
                      <select
                        className="exercise-select"
                        value={entry.exercise_id}
                        aria-invalid={Boolean(failure)}
                        aria-describedby={failure ? `${id}-err` : undefined}
                        onChange={(event) => update(b, e, { exercise_id: event.target.value, exercise_name: names.get(event.target.value) ?? '' })}
                      >
                        {[...names.entries()].map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                      </select>
                    </label>
                    <label>Series
                      <input type="number" inputMode="numeric" min={1} max={20} value={entry.sets} onChange={(event) => update(b, e, { sets: Number(event.target.value) })} />
                    </label>
                    <label>Repeticiones
                      <input type="text" maxLength={50} value={entry.reps} onChange={(event) => update(b, e, { reps: event.target.value })} />
                    </label>
                    <label>Descanso (s)
                      <input type="number" inputMode="numeric" min={0} max={600} value={entry.rest_seconds} onChange={(event) => update(b, e, { rest_seconds: Number(event.target.value) })} />
                    </label>
                    <label>Carga (kg)
                      <input type="number" inputMode="decimal" min={0} step="0.5" value={entry.target_weight_kg ?? ''} onChange={(event) => update(b, e, { target_weight_kg: event.target.value ? Number(event.target.value) : null })} />
                    </label>
                    {failure && <p className="rt-row__error" id={`${id}-err`}><AlertTriangle size={16} aria-hidden /> {failure}</p>}
                  </div>
                );
              })}
            </div>
          ))}

          <label className="session-adjustment__note">Nota para el alumno (opcional)
            <textarea maxLength={500} rows={3} value={note} placeholder="Ej.: Bajamos la carga por la molestia en la rodilla." onChange={(event) => { setNote(event.target.value); setMessage(''); }} />
          </label>
          <div className="rt-actions">
            <button type="submit" className="profile-save" disabled={saving || (changes === 0 && !noteChanged)}>
              <Save size={18} aria-hidden /> {saving ? 'Guardando…' : changes > 0 ? `Guardar ajuste (${changes} ${changes === 1 ? 'cambio' : 'cambios'})` : 'Guardar ajuste'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
