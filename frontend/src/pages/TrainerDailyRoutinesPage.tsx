import { ArrowLeft, ChevronDown, ListChecks, RefreshCw, SlidersHorizontal } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { SessionAdjustmentPanel } from '../components/SessionAdjustmentPanel';
import { ROUTES } from '../constants/routes';
import { getTrainerDailyRoutines } from '../services/trainerStudentService';
import type { DailyRoutineItem } from '../types/trainerStudent';
import {
  RPE_UNREPORTED_LABEL,
  countByStatus,
  dailyRoutineStatusLabel,
  formatDuration,
  formatWeight,
  isFinishedWithoutRpe,
  localDateInputValue,
  sortDailyRoutines,
  totalSets,
} from '../utils/dailyRoutineFormat.mjs';
import '../styles/daily-routines.css';

function formatTime(value: string): string {
  return new Date(value).toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' });
}

function DailyRoutineDetail({ item }: { item: DailyRoutineItem }) {
  const { session } = item;
  const [adjusting, setAdjusting] = useState(false);
  if (!session) {
    return <p className="daily-routines__muted">El alumno todavía no comenzó su entrenamiento en este día.</p>;
  }
  return (
    <div className="daily-routines__detail">
      <dl className="daily-routines__session">
        <div><dt>Día de rutina</dt><dd>{session.day_name}</dd></div>
        <div><dt>Inicio</dt><dd>{formatTime(session.started_at)}</dd></div>
        <div><dt>Fin</dt><dd>{session.finished_at ? formatTime(session.finished_at) : 'En curso'}</dd></div>
        <div><dt>Duración</dt><dd>{formatDuration(session.duration_seconds)}</dd></div>
        {item.status === 'FINISHED' && (
          <div>
            <dt>RPE</dt>
            <dd>
              {session.rpe !== null && session.rpe !== undefined
                ? `${session.rpe}/10`
                : RPE_UNREPORTED_LABEL}
            </dd>
          </div>
        )}
      </dl>
      {item.status === 'FINISHED' && (
        <button
          type="button"
          className="daily-routines__refresh session-adjustment__toggle"
          aria-pressed={adjusting}
          onClick={() => setAdjusting((value) => !value)}
        >
          {adjusting
            ? <><ListChecks size={16} aria-hidden="true" /> Ver series registradas</>
            : <><SlidersHorizontal size={16} aria-hidden="true" /> Ajustar próxima sesión</>}
        </button>
      )}
      {adjusting ? (
        <SessionAdjustmentPanel sessionId={session.id} />
      ) : item.exercises.length === 0 ? (
        <p className="daily-routines__muted">Todavía no registró series en esta sesión.</p>
      ) : (
        item.exercises.map((exercise) => (
          <div className="daily-routines__exercise" key={exercise.exercise_id}>
            <h3>{exercise.exercise_name}</h3>
            <div className="daily-routines__table-wrap">
              <table>
                <thead>
                  <tr><th scope="col">Serie</th><th scope="col">Reps</th><th scope="col">Carga</th><th scope="col">Tiempo</th><th scope="col">Hora</th></tr>
                </thead>
                <tbody>
                  {exercise.sets.map((set) => (
                    <tr key={set.set_number}>
                      <td>{set.set_number}</td>
                      <td>{set.reps_completed}</td>
                      <td>{formatWeight(set.weight_kg)}</td>
                      <td>{formatDuration(set.duration_seconds)}</td>
                      <td>{formatTime(set.recorded_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

export function TrainerDailyRoutinesPage() {
  const [date, setDate] = useState(() => localDateInputValue());
  const [items, setItems] = useState<DailyRoutineItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [openId, setOpenId] = useState<string | null>(null);

  const load = useCallback((selectedDate: string) => {
    setLoading(true);
    setError('');
    getTrainerDailyRoutines(selectedDate)
      .then((loaded) => setItems(sortDailyRoutines(loaded)))
      .catch(() => setError('No pudimos cargar las rutinas del día. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (date) load(date);
  }, [date, load]);

  const counts = countByStatus(items);

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className="profile-card daily-routines">
        <div className="profile-heading">
          <span>SEGUIMIENTO</span>
          <h1>Rutinas del día</h1>
          <p>Mirá en qué estado está el entrenamiento de cada alumno y las series que registró.</p>
        </div>

        <div className="daily-routines__toolbar">
          <label htmlFor="daily-routines-date">
            Día
            <input
              id="daily-routines-date"
              type="date"
              value={date}
              max={localDateInputValue()}
              onChange={(event) => setDate(event.target.value)}
            />
          </label>
          <button type="button" className="daily-routines__refresh" onClick={() => load(date)} disabled={loading || !date}>
            <RefreshCw size={16} aria-hidden="true" /> Actualizar
          </button>
        </div>

        {!loading && !error && items.length > 0 && (
          <ul className="daily-routines__summary" aria-label="Resumen del día">
            <li className="is-training"><strong>{counts.TRAINING}</strong> Entrenando</li>
            <li className="is-finished"><strong>{counts.FINISHED}</strong> Finalizadas</li>
            <li className="is-not-started"><strong>{counts.NOT_STARTED}</strong> No comenzadas</li>
          </ul>
        )}

        {loading ? (
          <p role="status">Cargando rutinas del día…</p>
        ) : error ? (
          <p className="form-alert" role="alert">{error}</p>
        ) : items.length === 0 ? (
          <p className="plan-empty">No tenés alumnos con un vínculo activo.</p>
        ) : (
          <ul className="daily-routines__list">
            {items.map((item) => {
              const open = openId === item.relationship_id;
              const detailId = `daily-routine-${item.relationship_id}`;
              return (
                <li key={item.relationship_id} className="daily-routines__row">
                  <button
                    type="button"
                    className="daily-routines__row-header"
                    aria-expanded={open}
                    aria-controls={detailId}
                    onClick={() => setOpenId(open ? null : item.relationship_id)}
                  >
                    <span className="daily-routines__student">
                      <strong>{item.student_name}</strong>
                      <small>{item.routine_name ?? 'Sin rutina asignada'}{item.session ? ` · ${item.session.day_name}` : ''}</small>
                    </span>
                    <span className="daily-routines__meta">
                      {item.session && <small>{totalSets(item)} series</small>}
                      <span
                        className={`daily-routines__status daily-routines__status--${isFinishedWithoutRpe(item) ? 'unreported' : item.status.toLowerCase()}`}
                      >
                        {dailyRoutineStatusLabel(item)}
                      </span>
                      <ChevronDown size={18} aria-hidden="true" className={open ? 'is-open' : ''} />
                    </span>
                  </button>
                  {open && (
                    <div id={detailId} className="daily-routines__row-body">
                      <DailyRoutineDetail item={item} />
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </main>
  );
}
