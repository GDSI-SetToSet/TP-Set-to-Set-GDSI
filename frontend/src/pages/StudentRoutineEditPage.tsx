import axios from 'axios';
import { ArrowLeft, CheckCircle2, Plus, Save, Trash2 } from 'lucide-react';
import { useEffect, useState } from 'react';
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

export function StudentRoutineEditPage() {
  const { studentId = '' } = useParams();
  const [view, setView] = useState<StudentRoutineView | null>(null);
  const [form, setForm] = useState<RoutineDraftInput | null>(null);
  const [library, setLibrary] = useState<Exercise[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [problems, setProblems] = useState<string[]>([]);

  function load(next: StudentRoutineView) {
    setView(next);
    setForm(toInput(next.draft ?? next.routine, next.draft_version, next.desired_weekly_volume));
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

  function handleError(caught: unknown) {
    if (axios.isAxiosError<ProblemDetails>(caught)) {
      setProblems((caught.response?.data?.errors ?? []).map((item) => item.message));
      setError(caught.response?.data?.detail ?? 'Revisá los datos ingresados.');
    } else {
      setError('No pudimos completar la acción. Intentá nuevamente.');
    }
  }

  async function run(action: () => Promise<void>, success: string) {
    if (!form) return;
    setBusy(true);
    setError('');
    setProblems([]);
    setMessage('');
    try {
      await action();
      setMessage(success);
    } catch (caught) {
      handleError(caught);
    } finally {
      setBusy(false);
    }
  }

  const reload = async () => load(await getStudentRoutine(studentId));

  const saveDraft = () => run(async () => {
    await saveRoutineDraft(studentId, form!);
    await reload();
  }, 'Borrador guardado. El alumno sigue viendo la versión vigente.');

  const discard = () => run(async () => {
    await discardRoutineDraft(studentId);
    await reload();
  }, 'Borrador descartado.');

  // Confirmar publica el borrador guardado, así que primero se guardan los cambios en pantalla.
  const confirm = () => run(async () => {
    await saveRoutineDraft(studentId, form!);
    load(await confirmRoutineDraft(studentId));
  }, 'Cambios confirmados y publicados para el alumno.');

  function update(change: Partial<RoutineDraftInput>) {
    setForm((current) => (current ? { ...current, ...change } : current));
  }

  function updateEntry(d: number, b: number, e: number, change: Partial<RoutineDraftInput['days'][0]['blocks'][0]['exercises'][0]>) {
    setForm((current) => current && {
      ...current,
      days: current.days.map((day, di) => (di !== d ? day : {
        ...day,
        blocks: day.blocks.map((block, bi) => (bi !== b ? block : {
          ...block,
          exercises: block.exercises.map((entry, ei) => (ei === e ? { ...entry, ...change } : entry)),
        })),
      })),
    });
  }

  function removeEntry(d: number, b: number, e: number) {
    setForm((current) => current && {
      ...current,
      days: current.days.map((day, di) => (di !== d ? day : {
        ...day,
        blocks: day.blocks.map((block, bi) => (bi !== b ? block : {
          ...block, exercises: block.exercises.filter((_, ei) => ei !== e),
        })),
      })),
    });
  }

  function addEntry(d: number, b: number) {
    if (!library[0]) return;
    setForm((current) => current && {
      ...current,
      days: current.days.map((day, di) => (di !== d ? day : {
        ...day,
        blocks: day.blocks.map((block, bi) => (bi !== b ? block : {
          ...block,
          exercises: [...block.exercises, { exercise_id: library[0].id, sets: 3, reps: '10', rest_seconds: 60, target_weight_kg: null }],
        })),
      })),
    });
  }

  // Los ejercicios dados de baja que la rutina conserva siguen siendo elegibles.
  const options = new Map(library.map((exercise) => [exercise.id, exercise]));
  [view?.routine, view?.draft].forEach((source) => source?.days.forEach((day) => day.blocks.forEach((block) => block.exercises.forEach((item) => {
    if (!options.has(item.exercise.id)) options.set(item.exercise.id, item.exercise);
  }))));

  return (
    <main className="profile-page">
      <Link className="back-link" to={ROUTES.trainerRoutines}><ArrowLeft size={18} aria-hidden /> Volver a rutinas</Link>
      <div className="profile-heading">
        <span>EDICIÓN POR ALUMNO</span>
        <h1>Editar rutina del alumno</h1>
        <p>Los cambios quedan en borrador: el alumno sigue viendo la versión vigente hasta que confirmes.</p>
      </div>

      {loading && <p role="status">Cargando rutina…</p>}
      {error && <p className="form-alert" role="alert">{error}</p>}
      {problems.length > 0 && (
        <ul className="form-alert" role="alert">{problems.map((problem) => <li key={problem}>{problem}</li>)}</ul>
      )}
      {message && <p className="profile-success" role="status"><CheckCircle2 size={18} aria-hidden /> {message}</p>}

      {form && view && (
        <form className="profile-form" onSubmit={(event) => event.preventDefault()}>
          {view.status === 'DRAFT_PENDING' && <p role="status">Hay cambios en borrador sin confirmar.</p>}
          <label>Intensidad
            <select className="exercise-select" value={form.intensity} onChange={(event) => update({ intensity: event.target.value as RoutineIntensity })}>
              {INTENSITY_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <label>Duración (semanas)
            <input type="number" min={1} max={52} value={form.duration_weeks} onChange={(event) => update({ duration_weeks: Number(event.target.value) })} />
          </label>
          <label>Volumen semanal deseado (sesiones, 1 a 7)
            <input
              type="number"
              min={1}
              max={7}
              value={form.desired_weekly_volume ?? ''}
              onChange={(event) => update({ desired_weekly_volume: event.target.value ? Number(event.target.value) : null })}
            />
          </label>
          <label className="exercise-check">
            <input type="checkbox" checked={form.has_no_materials_alternative} onChange={(event) => update({ has_no_materials_alternative: event.target.checked })} />
            Disponible “Sin materiales”
          </label>

          {form.days.map((day, d) => day.blocks.map((block, b) => (
            <fieldset key={`${d}-${b}`}>
              <legend>{day.name} · {block.name}</legend>
              {block.exercises.map((entry, e) => (
                <div className="routine-assignment__row" key={`${entry.exercise_id}-${e}`}>
                  <label>Ejercicio
                    <select className="exercise-select" value={entry.exercise_id} onChange={(event) => updateEntry(d, b, e, { exercise_id: event.target.value })}>
                      {[...options.values()].map((exercise) => <option key={exercise.id} value={exercise.id}>{exercise.name}</option>)}
                    </select>
                  </label>
                  <label>Series
                    <input type="number" min={1} max={20} value={entry.sets} onChange={(event) => updateEntry(d, b, e, { sets: Number(event.target.value) })} />
                  </label>
                  <label>Repeticiones
                    <input type="text" maxLength={50} value={entry.reps} onChange={(event) => updateEntry(d, b, e, { reps: event.target.value })} />
                  </label>
                  <label>Descanso (s)
                    <input type="number" min={0} max={600} value={entry.rest_seconds} onChange={(event) => updateEntry(d, b, e, { rest_seconds: Number(event.target.value) })} />
                  </label>
                  <label>Carga (kg)
                    <input
                      type="number"
                      min={0}
                      step="0.5"
                      value={entry.target_weight_kg ?? ''}
                      onChange={(event) => updateEntry(d, b, e, { target_weight_kg: event.target.value ? Number(event.target.value) : null })}
                    />
                  </label>
                  <button type="button" className="profile-save" onClick={() => removeEntry(d, b, e)} disabled={block.exercises.length === 1} aria-label="Quitar ejercicio">
                    <Trash2 size={18} aria-hidden />
                  </button>
                </div>
              ))}
              <button type="button" className="profile-save" onClick={() => addEntry(d, b)} disabled={block.exercises.length >= 30 || !library[0]}>
                <Plus size={18} aria-hidden /> Agregar ejercicio
              </button>
            </fieldset>
          )))}

          <div className="profile-actions">
            <button type="button" className="profile-save" onClick={() => void saveDraft()} disabled={busy}><Save size={18} aria-hidden /> Guardar borrador</button>
            <button type="button" className="profile-save" onClick={() => void confirm()} disabled={busy}><CheckCircle2 size={18} aria-hidden /> Confirmar y publicar</button>
            {view.draft && <button type="button" className="profile-save" onClick={() => void discard()} disabled={busy}>Descartar borrador</button>}
          </div>
        </form>
      )}
    </main>
  );
}
