import axios from 'axios';
import { AlertTriangle, ArrowLeft, CheckCircle2, Plus, Save, Trash2, Undo2 } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getExercises } from '../services/exerciseService';
import {
  confirmRoutineDraft,
  discardRoutineDraft,
  getStudentRoutine,
  saveRoutineDraft,
} from '../services/studentRoutineService';
import type { Exercise } from '../types/exercise';
import { ROUTINE_INTENSITIES, type RoutineIntensity, type RoutineTemplate } from '../types/routineTemplate';
import type { RoutineDraftInput, StudentRoutineView } from '../types/studentRoutine';

const INTENSITY_OPTIONS = Object.entries(ROUTINE_INTENSITIES) as [RoutineIntensity, string][];

interface ProblemDetails {
  detail?: string;
  errors?: { field: string; message: string }[];
}

// ponytail: edita ejercicios y parámetros; agregar/quitar días o bloques se hace en la plantilla.
function toInput(source: RoutineTemplate, version: number, volume: number | null): RoutineDraftInput {
  return {
    draft_version: version,
    desired_weekly_volume: volume,
    name: source.name,
    duration_weeks: source.duration_weeks,
    intensity: source.intensity,
    has_no_materials_alternative: source.has_no_materials_alternative,
    days: source.days.map((day) => ({
      name: day.name,
      blocks: day.blocks.map((block) => ({
        name: block.name,
        estimated_duration_minutes: block.estimated_duration_minutes ?? 1,
        exercises: block.exercises.map((item) => ({
          exercise_id: item.exercise.id,
          sets: item.sets,
          reps: item.reps,
          rest_seconds: item.rest_seconds,
          target_weight_kg: item.target_weight_kg,
        })),
      })),
    })),
  };
}

type Entry = RoutineDraftInput['days'][0]['blocks'][0]['exercises'][0];

const rowPath = (d: number, b: number, e: number) => `days.${d}.blocks.${b}.exercises.${e}`;

export function StudentRoutineEditPage() {
  const { studentId = '' } = useParams();
  const [view, setView] = useState<StudentRoutineView | null>(null);
  const [form, setForm] = useState<RoutineDraftInput | null>(null);
  const [library, setLibrary] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [dirty, setDirty] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [problems, setProblems] = useState<{ field: string; message: string }[]>([]);
  const summaryRef = useRef<HTMLDivElement>(null);

  function load(next: StudentRoutineView) {
    setView(next);
    setForm(toInput(next.draft ?? next.routine, next.draft_version, next.desired_weekly_volume));
    setDirty(false);
    setProblems(next.conflicts);
    setError(next.conflicts.length ? 'Esta rutina tiene ejercicios que no son compatibles con las limitaciones del alumno' : '');
  }

  useEffect(() => {
    Promise.all([getStudentRoutine(studentId), getExercises()])
      .then(([loaded, exercises]) => {
        load(loaded);
        setLibrary(exercises);
      })
      .catch(() => setError('No pudimos cargar la rutina del alumno. Verificá que tenga una rutina asignada.'))
      .finally(() => setLoading(false));
  }, [studentId]);

  // El resumen de errores recibe el foco para que se anuncie y se encuentre con teclado.
  useEffect(() => {
    if (error || problems.length) summaryRef.current?.focus();
  }, [error, problems]);

  function handleError(caught: unknown) {
    if (axios.isAxiosError<ProblemDetails>(caught)) {
      setProblems(caught.response?.data?.errors ?? []);
      setError(caught.response?.data?.detail ?? 'Revisá los datos ingresados.');
    } else {
      setError('No pudimos completar la acción. Intentá nuevamente.');
    }
  }

  async function run(name: string, action: () => Promise<void>, success: string) {
    setBusy(name);
    setError('');
    setProblems([]);
    setMessage('');
    try {
      await action();
      setMessage(success);
    } catch (caught) {
      handleError(caught);
    } finally {
      setBusy('');
    }
  }

  const reload = async () => load(await getStudentRoutine(studentId));
  const saveDraft = () => run('save', async () => {
    await saveRoutineDraft(studentId, form!);
    await reload();
  }, 'Borrador guardado. El alumno sigue viendo la versión vigente.');
  const discard = () => run('discard', async () => {
    await discardRoutineDraft(studentId);
    await reload();
  }, 'Borrador descartado. Volviste a la versión vigente.');
  // Confirmar publica el borrador guardado, así que primero se guardan los cambios en pantalla.
  const confirm = () => run('confirm', async () => {
    await saveRoutineDraft(studentId, form!);
    load(await confirmRoutineDraft(studentId));
  }, 'Cambios confirmados: el alumno ya ve la rutina actualizada.');

  function edit(change: (current: RoutineDraftInput) => RoutineDraftInput, keepErrors = true) {
    setForm((current) => (current ? change(current) : current));
    setDirty(true);
    if (!keepErrors) setProblems([]);
  }

  const mapEntries = (d: number, b: number, change: (entries: Entry[]) => Entry[]) => edit((current) => ({
    ...current,
    days: current.days.map((day, di) => (di !== d ? day : {
      ...day,
      blocks: day.blocks.map((block, bi) => (bi !== b ? block : { ...block, exercises: change(block.exercises) })),
    })),
  }), false);

  const updateEntry = (d: number, b: number, e: number, change: Partial<Entry>) =>
    mapEntries(d, b, (entries) => entries.map((entry, ei) => (ei === e ? { ...entry, ...change } : entry)));
  const removeEntry = (d: number, b: number, e: number) => mapEntries(d, b, (entries) => entries.filter((_, ei) => ei !== e));
  const addEntry = (d: number, b: number) => library[0] && mapEntries(d, b, (entries) => [
    ...entries,
    { exercise_id: library[0].id, sets: 3, reps: '10', rest_seconds: 60, target_weight_kg: null },
  ]);

  // Los ejercicios dados de baja que la rutina conserva siguen siendo elegibles.
  const options = new Map(library.map((exercise) => [exercise.id, exercise]));
  [view?.routine, view?.draft].forEach((source) => source?.days.forEach((day) => day.blocks.forEach((block) => block.exercises.forEach((item) => {
    if (!options.has(item.exercise.id)) options.set(item.exercise.id, item.exercise);
  }))));

  const rowError = (path: string) => problems.find((item) => item.field.startsWith(path))?.message;
  const hasPending = view?.status === 'DRAFT_PENDING';
  const canConfirm = dirty || hasPending;

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando rutina…</main>;

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerStudents} className="profile-back"><ArrowLeft size={18} /> Volver a mis alumnos</Link>
      </header>

      <section className="profile-card rt-editor">
        <div className="profile-heading">
          <span>EDICIÓN POR ALUMNO</span>
          <h1>{form?.name ?? 'Rutina del alumno'}</h1>
          <p>Tus cambios quedan en borrador: el alumno sigue viendo la versión vigente hasta que confirmes.</p>
        </div>

        {(error || problems.length > 0) && (
          <div className="rt-alert" role="alert" tabIndex={-1} ref={summaryRef}>
            <AlertTriangle size={20} aria-hidden />
            <div>
              <strong>{error || 'Hay un problema con la rutina'}</strong>
              {problems.length > 0 && <ul>{problems.map((item) => <li key={`${item.field}${item.message}`}>{item.message}</li>)}</ul>}
              <p>Corregí o quitá los ejercicios marcados y volvé a guardar.</p>
            </div>
          </div>
        )}
        {message && <p className="profile-success" role="status"><CheckCircle2 size={18} aria-hidden /> {message}</p>}

        {form && view && (
          <form className="rt-form" onSubmit={(event) => event.preventDefault()}>
            <div className="rt-status" role="status">
              <span className={`rt-chip ${hasPending ? 'rt-chip--draft' : 'rt-chip--live'}`}>
                {hasPending ? 'Borrador sin confirmar' : 'Versión vigente'}
              </span>
              {dirty && <span className="rt-dirty">Cambios sin guardar</span>}
            </div>

            <fieldset className="rt-settings">
              <legend>Parámetros generales</legend>
              <label>Intensidad
                <select className="exercise-select" value={form.intensity} onChange={(event) => edit((c) => ({ ...c, intensity: event.target.value as RoutineIntensity }))}>
                  {INTENSITY_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
              </label>
              <label>Duración (semanas)
                <input type="number" inputMode="numeric" min={1} max={52} value={form.duration_weeks} onChange={(event) => edit((c) => ({ ...c, duration_weeks: Number(event.target.value) }))} />
              </label>
              <label>Volumen semanal deseado
                <input type="number" inputMode="numeric" min={1} max={7} placeholder="Sesiones por semana" value={form.desired_weekly_volume ?? ''} onChange={(event) => edit((c) => ({ ...c, desired_weekly_volume: event.target.value ? Number(event.target.value) : null }))} />
              </label>
              <label className="exercise-check">
                <input type="checkbox" checked={form.has_no_materials_alternative} onChange={(event) => edit((c) => ({ ...c, has_no_materials_alternative: event.target.checked }))} />
                Disponible “Sin materiales”
              </label>
            </fieldset>

            {form.days.map((day, d) => (
              <section className="rt-day" key={`${day.name}-${d}`} aria-labelledby={`rt-day-${d}`}>
                <h2 id={`rt-day-${d}`}>{day.name}</h2>
                {day.blocks.map((block, b) => (
                  <div className="rt-block" key={`${block.name}-${b}`}>
                    <h3>{block.name}<small>{block.exercises.length} ejercicios</small></h3>
                    {block.exercises.map((entry, e) => {
                      const failure = rowError(rowPath(d, b, e));
                      const id = `rt-${d}-${b}-${e}`;
                      return (
                        <div className={`rt-row${failure ? ' rt-row--invalid' : ''}`} key={`${entry.exercise_id}-${e}`}>
                          <label className="rt-row__exercise">Ejercicio
                            <select className="exercise-select" aria-invalid={Boolean(failure)} aria-describedby={failure ? `${id}-err` : undefined} value={entry.exercise_id} onChange={(event) => updateEntry(d, b, e, { exercise_id: event.target.value })}>
                              {[...options.values()].map((exercise) => <option key={exercise.id} value={exercise.id}>{exercise.name}</option>)}
                            </select>
                          </label>
                          <label>Series
                            <input type="number" inputMode="numeric" min={1} max={20} value={entry.sets} onChange={(event) => updateEntry(d, b, e, { sets: Number(event.target.value) })} />
                          </label>
                          <label>Repeticiones
                            <input type="text" maxLength={50} value={entry.reps} onChange={(event) => updateEntry(d, b, e, { reps: event.target.value })} />
                          </label>
                          <label>Descanso (s)
                            <input type="number" inputMode="numeric" min={0} max={600} value={entry.rest_seconds} onChange={(event) => updateEntry(d, b, e, { rest_seconds: Number(event.target.value) })} />
                          </label>
                          <label>Carga (kg)
                            <input type="number" inputMode="decimal" min={0} step="0.5" value={entry.target_weight_kg ?? ''} onChange={(event) => updateEntry(d, b, e, { target_weight_kg: event.target.value ? Number(event.target.value) : null })} />
                          </label>
                          <button type="button" className="plan-cancel rt-row__remove" onClick={() => removeEntry(d, b, e)} disabled={block.exercises.length === 1} aria-label={`Quitar ejercicio ${e + 1} de ${block.name}`}>
                            <Trash2 size={18} aria-hidden />
                          </button>
                          {failure && <p className="rt-row__error" id={`${id}-err`}><AlertTriangle size={16} aria-hidden /> {failure}</p>}
                        </div>
                      );
                    })}
                    <button type="button" className="plan-cancel" onClick={() => addEntry(d, b)} disabled={block.exercises.length >= 30 || !library[0]}>
                      <Plus size={18} aria-hidden /> Agregar ejercicio
                    </button>
                  </div>
                ))}
              </section>
            ))}

            <div className="rt-actions">
              <button type="button" className="profile-save" onClick={() => void confirm()} disabled={Boolean(busy) || !canConfirm}>
                <CheckCircle2 size={18} aria-hidden /> {busy === 'confirm' ? 'Publicando…' : 'Confirmar y publicar'}
              </button>
              <button type="button" className="plan-cancel" onClick={() => void saveDraft()} disabled={Boolean(busy) || !dirty}>
                <Save size={18} aria-hidden /> {busy === 'save' ? 'Guardando…' : 'Guardar borrador'}
              </button>
              {hasPending && (
                <button type="button" className="plan-cancel" onClick={() => void discard()} disabled={Boolean(busy)}>
                  <Undo2 size={18} aria-hidden /> {busy === 'discard' ? 'Descartando…' : 'Descartar borrador'}
                </button>
              )}
            </div>
          </form>
        )}
      </section>
    </main>
  );
}
