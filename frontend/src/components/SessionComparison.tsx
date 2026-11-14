import { useEffect, useState } from 'react';
import { getSessionComparison } from '../services/trainerStudentService';
import type { ExerciseComparison, SessionComparison as Comparison } from '../types/trainerStudent';
import { formatDuration } from '../utils/dailyRoutineFormat.mjs';
import { deltaTone, formatDelta, formatKg, formatReps, setsCompliance } from '../utils/sessionComparison.mjs';

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('es-AR', { day: '2-digit', month: '2-digit' });
}

/** Diferencia contra una referencia; no muestra nada si no hay con qué comparar. */
function Delta({ current, reference, unit = '', label }: {
  current: number | null | undefined;
  reference: number | null | undefined;
  unit?: string;
  label: string;
}) {
  const text = formatDelta(current, reference, unit);
  if (!text) return null;
  return (
    <span className={`session-comparison__delta session-comparison__delta--${deltaTone(current, reference)}`}>
      {text} <span className="session-comparison__delta-ref">{label}</span>
    </span>
  );
}

function ExerciseRow({ exercise, hasPrevious }: { exercise: ExerciseComparison; hasPrevious: boolean }) {
  const { planned, performed, previous } = exercise;
  const compliance = setsCompliance(exercise);
  return (
    <div className="daily-routines__exercise session-comparison__exercise">
      <h3>
        {exercise.exercise_name}
        {exercise.replaced_exercise_name && (
          <small className="session-comparison__note"> · reemplazó a {exercise.replaced_exercise_name}</small>
        )}
        {!planned && <small className="session-comparison__note"> · fuera de lo planificado</small>}
      </h3>
      <div className="daily-routines__table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Métrica</th>
              <th scope="col">Planificado</th>
              <th scope="col">Realizado</th>
              {hasPrevious && <th scope="col">Sesión previa</th>}
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">Series</th>
              <td>{planned ? planned.sets : '—'}</td>
              <td>
                {performed?.sets_completed ?? 0}
                {compliance && <span className="session-comparison__hint">{compliance}</span>}
              </td>
              {hasPrevious && (
                <td>
                  {previous?.sets_completed ?? '—'}
                  <Delta current={performed?.sets_completed} reference={previous?.sets_completed} label="vs previa" />
                </td>
              )}
            </tr>
            <tr>
              <th scope="row">Repeticiones</th>
              <td>{planned ? planned.reps : '—'}</td>
              <td>{formatReps(performed)}</td>
              {hasPrevious && <td>{formatReps(previous)}</td>}
            </tr>
            <tr>
              <th scope="row">Carga máxima</th>
              <td>{planned ? formatKg(planned.target_weight_kg) : '—'}</td>
              <td>
                {formatKg(performed?.max_weight_kg)}
                <Delta current={performed?.max_weight_kg} reference={planned?.target_weight_kg} unit="kg" label="vs plan" />
              </td>
              {hasPrevious && (
                <td>
                  {formatKg(previous?.max_weight_kg)}
                  <Delta current={performed?.max_weight_kg} reference={previous?.max_weight_kg} unit="kg" label="vs previa" />
                </td>
              )}
            </tr>
            <tr>
              <th scope="row">Volumen</th>
              <td>—</td>
              <td>{performed ? formatKg(performed.volume_kg) : '—'}</td>
              {hasPrevious && (
                <td>
                  {previous ? formatKg(previous.volume_kg) : '—'}
                  <Delta current={performed?.volume_kg} reference={previous?.volume_kg} unit="kg" label="vs previa" />
                </td>
              )}
            </tr>
            <tr>
              <th scope="row">Tiempo de series</th>
              <td>—</td>
              <td>{performed ? formatDuration(performed.total_duration_seconds) : '—'}</td>
              {hasPrevious && <td>{previous ? formatDuration(previous.total_duration_seconds) : '—'}</td>}
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function SessionComparison({ sessionId }: { sessionId: string }) {
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setComparison(null);
    setError('');
    getSessionComparison(sessionId)
      .then((loaded) => { if (active) setComparison(loaded); })
      .catch(() => { if (active) setError('No pudimos cargar la comparación de métricas. Intentá nuevamente.'); });
    return () => { active = false; };
  }, [sessionId]);

  if (error) return <p className="form-alert" role="alert">{error}</p>;
  if (!comparison) return <p role="status">Cargando comparación…</p>;

  const { session, previous_session: previous } = comparison;
  return (
    <section className="session-comparison" aria-label="Comparación de métricas">
      <p className="daily-routines__muted">
        {previous
          ? `Comparada con lo planificado y con la sesión previa de "${session.day_name}" del ${formatDate(previous.started_at)}.`
          : `Comparada con lo planificado. Es la primera sesión finalizada de "${session.day_name}", no hay una sesión previa.`}
      </p>
      <dl className="daily-routines__session">
        <div>
          <dt>Duración</dt>
          <dd>
            {formatDuration(session.duration_seconds)}
            {previous && <small> (previa {formatDuration(previous.duration_seconds)})</small>}
          </dd>
        </div>
        <div>
          <dt>RPE</dt>
          <dd>{session.rpe ?? '—'}{previous?.rpe != null && <small> (previa {previous.rpe})</small>}</dd>
        </div>
        <div>
          <dt>Volumen total</dt>
          <dd>{formatKg(comparison.volume_kg)}</dd>
          <Delta current={comparison.volume_kg} reference={comparison.previous_volume_kg} unit="kg" label="vs previa" />
        </div>
      </dl>
      {comparison.exercises.length === 0 ? (
        <p className="daily-routines__muted">No hay ejercicios planificados ni registrados para comparar.</p>
      ) : (
        comparison.exercises.map((exercise) => (
          <ExerciseRow key={exercise.exercise_id} exercise={exercise} hasPrevious={Boolean(previous)} />
        ))
      )}
    </section>
  );
}
