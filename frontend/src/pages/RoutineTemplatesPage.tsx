import axios from 'axios';
import { ArrowLeft, CheckCircle2, Plus, Save, Trash2 } from 'lucide-react';
import { type FormEvent, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { RoutineTemplateCard } from '../components/RoutineTemplateCard';
import { RoutineAssignmentPanel } from '../components/RoutineAssignmentPanel';
import { ROUTES } from '../constants/routes';
import { getExercises } from '../services/exerciseService';
import { createRoutineTemplate, getRoutineTemplates, updateRoutineTemplate } from '../services/routineTemplateService';
import { EXERCISE_CATEGORIES, type Exercise } from '../types/exercise';
import { ROUTINE_INTENSITIES, type RoutineIntensity, type RoutineTemplate, type RoutineTemplateInput } from '../types/routineTemplate';

const REQUIRED_MESSAGE = 'Este campo es obligatorio';
const MAX_DAYS = 7;
const MAX_BLOCKS = 10;
const MAX_EXERCISES = 30;
const INTENSITY_OPTIONS = Object.entries(ROUTINE_INTENSITIES) as [RoutineIntensity, string][];

interface EntryForm {
  key: number;
  exercise_id: string;
  sets: string;
  reps: string;
  rest_seconds: string;
  target_weight_kg: string;
}

interface BlockForm {
  key: number;
  name: string;
  estimated_duration_minutes: string;
  exercises: EntryForm[];
}

interface DayForm {
  key: number;
  name: string;
  blocks: BlockForm[];
}

interface FormState {
  name: string;
  duration_weeks: string;
  intensity: RoutineIntensity | '';
  has_no_materials_alternative: boolean;
  days: DayForm[];
}

interface ProblemDetails {
  detail?: string;
  errors?: { field: string; message: string }[];
}

let nextKey = 0;
const newKey = () => (nextKey += 1);

function emptyEntry(): EntryForm {
  return { key: newKey(), exercise_id: '', sets: '', reps: '', rest_seconds: '', target_weight_kg: '' };
}

function emptyBlock(position: number): BlockForm {
  return { key: newKey(), name: position === 1 ? 'Principal' : `Bloque ${position}`, estimated_duration_minutes: '', exercises: [emptyEntry()] };
}

function emptyDay(position: number): DayForm {
  return { key: newKey(), name: `Día ${position}`, blocks: [emptyBlock(1)] };
}

function emptyForm(): FormState {
  return { name: '', duration_weeks: '', intensity: '', has_no_materials_alternative: false, days: [emptyDay(1)] };
}

function formFromTemplate(template: RoutineTemplate): FormState {
  return {
    name: template.name,
    duration_weeks: String(template.duration_weeks),
    intensity: template.intensity,
    has_no_materials_alternative: template.has_no_materials_alternative,
    days: template.days.map((day) => ({
      key: newKey(),
      name: day.name,
      blocks: day.blocks.map((block) => ({
        key: newKey(),
        name: block.name,
        estimated_duration_minutes: String(block.estimated_duration_minutes || ''),
        exercises: block.exercises.map((item) => ({
          key: newKey(),
          exercise_id: item.exercise.id,
          sets: String(item.sets),
          reps: item.reps,
          rest_seconds: String(item.rest_seconds),
          target_weight_kg: item.target_weight_kg === null ? '' : String(item.target_weight_kg),
        })),
      })),
    })),
  };
}

function missingFields(form: FormState): Record<string, string> {
  const missing: string[] = [];
  if (!form.name.trim()) missing.push('name');
  if (!form.duration_weeks.trim()) missing.push('duration_weeks');
  if (!form.intensity) missing.push('intensity');
  form.days.forEach((day, dayIndex) => {
    if (!day.name.trim()) missing.push(`days.${dayIndex}.name`);
    day.blocks.forEach((block, blockIndex) => {
      const blockPath = `days.${dayIndex}.blocks.${blockIndex}`;
      if (!block.name.trim()) missing.push(`${blockPath}.name`);
      if (!block.estimated_duration_minutes.trim()) missing.push(`${blockPath}.estimated_duration_minutes`);
      block.exercises.forEach((entry, entryIndex) => {
        (['exercise_id', 'sets', 'reps', 'rest_seconds'] as const).forEach((field) => {
          if (!entry[field].trim()) missing.push(`${blockPath}.exercises.${entryIndex}.${field}`);
        });
      });
    });
  });
  return Object.fromEntries(missing.map((field) => [field, REQUIRED_MESSAGE]));
}

function toPayload(form: FormState, intensity: RoutineIntensity): RoutineTemplateInput {
  return {
    name: form.name,
    duration_weeks: Number(form.duration_weeks),
    intensity,
    has_no_materials_alternative: form.has_no_materials_alternative,
    days: form.days.map((day) => ({
      name: day.name,
      blocks: day.blocks.map((block) => ({
        name: block.name,
        estimated_duration_minutes: Number(block.estimated_duration_minutes),
        exercises: block.exercises.map((entry) => ({
          exercise_id: entry.exercise_id,
          sets: Number(entry.sets),
          reps: entry.reps,
          rest_seconds: Number(entry.rest_seconds),
          target_weight_kg: entry.target_weight_kg.trim() ? Number(entry.target_weight_kg) : null,
        })),
      })),
    })),
  };
}

export function RoutineTemplatesPage() {
  const [templates, setTemplates] = useState<RoutineTemplate[]>([]);
  const [library, setLibrary] = useState<Exercise[]>([]);
  const [form, setForm] = useState<FormState>(emptyForm);
  const [editing, setEditing] = useState<RoutineTemplate | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    Promise.all([getRoutineTemplates(), getExercises()])
      .then(([loadedTemplates, loadedExercises]) => {
        setTemplates(loadedTemplates);
        setLibrary(loadedExercises);
      })
      .catch(() => setError('No pudimos cargar tus rutinas. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  // Al editar se suman los ejercicios dados de baja que la rutina conserva (spec 005, casos borde).
  const exerciseOptions = useMemo(() => {
    const options = new Map(library.map((exercise) => [exercise.id, exercise]));
    editing?.days.forEach((day) => day.blocks.forEach((block) => block.exercises.forEach((item) => {
      if (!options.has(item.exercise.id)) options.set(item.exercise.id, item.exercise);
    })));
    return [...options.values()];
  }, [library, editing]);

  function updateDay(dayIndex: number, change: (day: DayForm) => DayForm) {
    setForm((current) => ({ ...current, days: current.days.map((day, index) => (index === dayIndex ? change(day) : day)) }));
  }

  function updateBlock(dayIndex: number, blockIndex: number, change: (block: BlockForm) => BlockForm) {
    updateDay(dayIndex, (day) => ({ ...day, blocks: day.blocks.map((block, index) => (index === blockIndex ? change(block) : block)) }));
  }

  function updateEntry(dayIndex: number, blockIndex: number, entryIndex: number, change: Partial<EntryForm>) {
    updateBlock(dayIndex, blockIndex, (block) => ({
      ...block,
      exercises: block.exercises.map((entry, index) => (index === entryIndex ? { ...entry, ...change } : entry)),
    }));
  }

  // Quitar días, bloques o ejercicios corre las posiciones, así que se limpian los errores marcados.
  function removeDay(dayIndex: number) {
    setForm((current) => ({ ...current, days: current.days.filter((_, index) => index !== dayIndex) }));
    setFieldErrors({});
  }

  function removeBlock(dayIndex: number, blockIndex: number) {
    updateDay(dayIndex, (day) => ({ ...day, blocks: day.blocks.filter((_, index) => index !== blockIndex) }));
    setFieldErrors({});
  }

  function removeEntry(dayIndex: number, blockIndex: number, entryIndex: number) {
    updateBlock(dayIndex, blockIndex, (block) => ({ ...block, exercises: block.exercises.filter((_, index) => index !== entryIndex) }));
    setFieldErrors({});
  }

  function resetForm() {
    setForm(emptyForm());
    setEditing(null);
    setFieldErrors({});
  }

  function startEditing(template: RoutineTemplate) {
    setEditing(template);
    setForm(formFromTemplate(template));
    setFieldErrors({});
    setMessage('');
    setError('');
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function handleError(caught: unknown) {
    if (axios.isAxiosError<ProblemDetails>(caught)) {
      setFieldErrors(Object.fromEntries((caught.response?.data?.errors ?? []).map((item) => [item.field, item.message])));
      setError(caught.response?.data?.detail ?? 'Revisá los datos ingresados.');
    } else {
      setError('No pudimos guardar los cambios. Intentá nuevamente.');
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    setError('');
    const missing = missingFields(form);
    setFieldErrors(missing);
    if (Object.keys(missing).length > 0 || !form.intensity) {
      setError('Completá los datos marcados para guardar la rutina.');
      return;
    }

    const payload = toPayload(form, form.intensity);
    setSaving(true);
    try {
      if (editing) {
        const updated = await updateRoutineTemplate(editing.id, payload);
        setTemplates((current) => current.map((template) => (template.id === updated.id ? updated : template)));
        setMessage('Rutina actualizada.');
      } else {
        const created = await createRoutineTemplate(payload);
        setTemplates((current) => [...current, created]);
        setMessage('Rutina creada. Ya está disponible para tus alumnos activos.');
      }
      resetForm();
    } catch (caught) {
      handleError(caught);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando rutinas…</main>;

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className="profile-card">
        <div className="profile-heading">
          <span>RUTINAS GENÉRICAS</span>
          <h1>Tus rutinas</h1>
          <p>Armá rutinas con tu biblioteca. Tus alumnos con vínculo activo las ven en modo lectura.</p>
        </div>

        {library.length === 0 && !editing ? (
          <p className="plan-empty">Necesitás ejercicios para armar una rutina. <Link to={ROUTES.trainerExercises}>Cargalos en tu biblioteca</Link>.</p>
        ) : (
          <form className="profile-form" onSubmit={handleSubmit} noValidate>
            <label>Nombre de la rutina
              <input value={form.name} onChange={(event) => setForm((current) => ({ ...current, name: event.target.value }))} maxLength={150} aria-invalid={Boolean(fieldErrors.name)} />
              {fieldErrors.name && <small className="field-error">{fieldErrors.name}</small>}
            </label>
            <label>Duración (semanas)
              <input type="number" inputMode="numeric" min={1} max={52} value={form.duration_weeks} onChange={(event) => setForm((current) => ({ ...current, duration_weeks: event.target.value }))} aria-invalid={Boolean(fieldErrors.duration_weeks)} />
              {fieldErrors.duration_weeks && <small className="field-error">{fieldErrors.duration_weeks}</small>}
            </label>
            <label>Intensidad
              <select className="exercise-select" value={form.intensity} onChange={(event) => setForm((current) => ({ ...current, intensity: event.target.value as RoutineIntensity | '' }))} aria-invalid={Boolean(fieldErrors.intensity)}>
                <option value="">Elegí una intensidad</option>
                {INTENSITY_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
              {fieldErrors.intensity && <small className="field-error">{fieldErrors.intensity}</small>}
            </label>
            <label className="exercise-check">
              <input type="checkbox" checked={form.has_no_materials_alternative} onChange={(event) => setForm((current) => ({ ...current, has_no_materials_alternative: event.target.checked }))} />
              Apta "Sin materiales" (todos los ejercicios deben tener esa alternativa)
            </label>

            {form.days.map((day, dayIndex) => (
              <fieldset key={day.key} className="routine-day">
                <legend>Día {dayIndex + 1}</legend>
                <label>Nombre del día
                  <input aria-label={`Nombre del día ${dayIndex + 1}`} value={day.name} onChange={(event) => updateDay(dayIndex, (current) => ({ ...current, name: event.target.value }))} maxLength={100} />
                  {fieldErrors[`days.${dayIndex}.name`] && <small className="field-error">{fieldErrors[`days.${dayIndex}.name`]}</small>}
                </label>

                {day.blocks.map((block, blockIndex) => {
                  const blockPath = `days.${dayIndex}.blocks.${blockIndex}`;
                  return (
                    <div key={block.key} className="routine-block">
                      <label>Nombre del bloque
                        <input value={block.name} onChange={(event) => updateBlock(dayIndex, blockIndex, (current) => ({ ...current, name: event.target.value }))} maxLength={100} />
                        {fieldErrors[`${blockPath}.name`] && <small className="field-error">{fieldErrors[`${blockPath}.name`]}</small>}
                      </label>
                      <label>Duración estimada (minutos)
                        <input type="number" inputMode="numeric" min={1} max={600} value={block.estimated_duration_minutes} onChange={(event) => updateBlock(dayIndex, blockIndex, (current) => ({ ...current, estimated_duration_minutes: event.target.value }))} aria-invalid={Boolean(fieldErrors[`${blockPath}.estimated_duration_minutes`])} />
                        {fieldErrors[`${blockPath}.estimated_duration_minutes`] && <small className="field-error">{fieldErrors[`${blockPath}.estimated_duration_minutes`]}</small>}
                      </label>

                      {block.exercises.map((entry, entryIndex) => {
                        const entryPath = `${blockPath}.exercises.${entryIndex}`;
                        return (
                          <div key={entry.key} className="routine-entry">
                            <label className="routine-entry__exercise">Ejercicio
                              <select className="exercise-select" value={entry.exercise_id} onChange={(event) => updateEntry(dayIndex, blockIndex, entryIndex, { exercise_id: event.target.value })} aria-invalid={Boolean(fieldErrors[`${entryPath}.exercise_id`])}>
                                <option value="">Elegí un ejercicio</option>
                                {exerciseOptions.map((exercise) => (
                                  <option key={exercise.id} value={exercise.id}>{exercise.name} ({EXERCISE_CATEGORIES[exercise.category]})</option>
                                ))}
                              </select>
                              {fieldErrors[`${entryPath}.exercise_id`] && <small className="field-error">{fieldErrors[`${entryPath}.exercise_id`]}</small>}
                            </label>
                            <label>Series
                              <input type="number" inputMode="numeric" min={1} max={20} value={entry.sets} onChange={(event) => updateEntry(dayIndex, blockIndex, entryIndex, { sets: event.target.value })} aria-invalid={Boolean(fieldErrors[`${entryPath}.sets`])} />
                              {fieldErrors[`${entryPath}.sets`] && <small className="field-error">{fieldErrors[`${entryPath}.sets`]}</small>}
                            </label>
                            <label>Repeticiones
                              <input value={entry.reps} onChange={(event) => updateEntry(dayIndex, blockIndex, entryIndex, { reps: event.target.value })} maxLength={50} placeholder="8-10" aria-invalid={Boolean(fieldErrors[`${entryPath}.reps`])} />
                              {fieldErrors[`${entryPath}.reps`] && <small className="field-error">{fieldErrors[`${entryPath}.reps`]}</small>}
                            </label>
                            <label>Descanso (seg)
                              <input type="number" inputMode="numeric" min={0} max={600} value={entry.rest_seconds} onChange={(event) => updateEntry(dayIndex, blockIndex, entryIndex, { rest_seconds: event.target.value })} aria-invalid={Boolean(fieldErrors[`${entryPath}.rest_seconds`])} />
                              {fieldErrors[`${entryPath}.rest_seconds`] && <small className="field-error">{fieldErrors[`${entryPath}.rest_seconds`]}</small>}
                            </label>
                            <label>Peso objetivo (kg)
                              <input type="number" inputMode="decimal" min={0} max={9999.99} step="0.25" value={entry.target_weight_kg} onChange={(event) => updateEntry(dayIndex, blockIndex, entryIndex, { target_weight_kg: event.target.value })} aria-invalid={Boolean(fieldErrors[`${entryPath}.target_weight_kg`])} />
                              {fieldErrors[`${entryPath}.target_weight_kg`] && <small className="field-error">{fieldErrors[`${entryPath}.target_weight_kg`]}</small>}
                            </label>
                            {block.exercises.length > 1 && (
                              <button type="button" className="plan-cancel routine-entry__remove" onClick={() => removeEntry(dayIndex, blockIndex, entryIndex)} aria-label="Quitar ejercicio"><Trash2 size={16} /></button>
                            )}
                          </div>
                        );
                      })}

                      <div className="routine-actions">
                        {block.exercises.length < MAX_EXERCISES && (
                          <button type="button" className="plan-cancel" onClick={() => updateBlock(dayIndex, blockIndex, (current) => ({ ...current, exercises: [...current.exercises, emptyEntry()] }))}><Plus size={16} /> Agregar ejercicio</button>
                        )}
                        {day.blocks.length > 1 && (
                          <button type="button" className="plan-cancel" onClick={() => removeBlock(dayIndex, blockIndex)}><Trash2 size={16} /> Quitar bloque</button>
                        )}
                      </div>
                    </div>
                  );
                })}

                <div className="routine-actions">
                  {day.blocks.length < MAX_BLOCKS && (
                    <button type="button" className="plan-cancel" onClick={() => updateDay(dayIndex, (current) => ({ ...current, blocks: [...current.blocks, emptyBlock(current.blocks.length + 1)] }))}><Plus size={16} /> Agregar bloque</button>
                  )}
                  {form.days.length > 1 && (
                    <button type="button" className="plan-cancel" onClick={() => removeDay(dayIndex)}><Trash2 size={16} /> Quitar día</button>
                  )}
                </div>
              </fieldset>
            ))}

            {form.days.length < MAX_DAYS && (
              <div className="routine-actions">
                <button type="button" className="plan-cancel" onClick={() => setForm((current) => ({ ...current, days: [...current.days, emptyDay(current.days.length + 1)] }))}><Plus size={16} /> Agregar día</button>
              </div>
            )}

            {error && <p className="form-alert" role="alert">{error}</p>}
            {message && <p className="profile-success" role="status"><CheckCircle2 size={18} /> {message}</p>}
            <div className="plan-form__actions">
              <button className="profile-save" type="submit" disabled={saving}>
                <Save size={18} /> {saving ? 'Guardando…' : editing ? 'Guardar cambios' : 'Guardar'}
              </button>
              {editing && <button className="plan-cancel" type="button" onClick={resetForm} disabled={saving}>Cancelar</button>}
            </div>
          </form>
        )}
      </section>

      <RoutineAssignmentPanel templates={templates} />

      <section className="plan-list" aria-label="Rutinas cargadas">
        {templates.length === 0
          ? <p className="plan-empty">Todavía no creaste rutinas.</p>
          : templates.map((template) => <RoutineTemplateCard key={template.id} template={template} busy={saving} onEdit={startEditing} />)}
      </section>
    </main>
  );
}
