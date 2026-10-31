import axios from 'axios';
import { ArrowLeft, CheckCircle2, Save } from 'lucide-react';
import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ExerciseCard } from '../components/ExerciseCard';
import { ROUTES } from '../constants/routes';
import { createExercise, deleteExercise, getExercises, updateExercise } from '../services/exerciseService';
import { EXERCISE_CATEGORIES, type Exercise, type ExerciseCategory } from '../types/exercise';
import { getVideoEmbedUrl } from '../utils/videoUrl';

const REQUIRED_MESSAGE = 'Este campo es obligatorio';
const CATEGORY_OPTIONS = Object.entries(EXERCISE_CATEGORIES) as [ExerciseCategory, string][];

interface FormState {
  name: string;
  description: string;
  category: ExerciseCategory | '';
  target_muscle_group: string;
  equipment_needed: string;
  has_no_materials_alternative: boolean;
  video_url: string;
}

type TextField = Exclude<keyof FormState, 'has_no_materials_alternative'>;

const EMPTY_FORM: FormState = {
  name: '',
  description: '',
  category: '',
  target_muscle_group: '',
  equipment_needed: '',
  has_no_materials_alternative: false,
  video_url: '',
};
const REQUIRED_FIELDS: TextField[] = ['name', 'description', 'category', 'target_muscle_group', 'equipment_needed'];

interface ProblemDetails {
  detail?: string;
  errors?: { field: string; message: string }[];
}

export function ExerciseLibraryPage() {
  const [exercises, setExercises] = useState<Exercise[]>([]);
  const [muscles, setMuscles] = useState<string[]>([]);
  const [muscleFilter, setMuscleFilter] = useState('');
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const videoPreviewUrl = getVideoEmbedUrl(form.video_url);

  // El filtro se arma con la biblioteca completa para no perder opciones al elegir un músculo.
  const loadExercises = useCallback(async (muscle: string) => {
    const all = await getExercises();
    const available = [...new Set(all.map((exercise) => exercise.target_muscle_group))].sort((a, b) => a.localeCompare(b));
    const selected = available.includes(muscle) ? muscle : '';
    setMuscles(available);
    setMuscleFilter(selected);
    setExercises(selected ? await getExercises(selected) : all);
  }, []);

  useEffect(() => {
    loadExercises(muscleFilter)
      .catch(() => setError('No pudimos cargar tu biblioteca. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, [loadExercises, muscleFilter]);

  function updateField(field: TextField, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: '' }));
  }

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFieldErrors({});
  }

  function startEditing(exercise: Exercise) {
    setEditingId(exercise.id);
    setForm({
      name: exercise.name,
      description: exercise.description,
      category: exercise.category,
      target_muscle_group: exercise.target_muscle_group,
      equipment_needed: exercise.equipment_needed,
      has_no_materials_alternative: exercise.has_no_materials_alternative,
      video_url: exercise.video_url ?? '',
    });
    setFieldErrors({});
    setMessage('');
    setError('');
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
    const missing = Object.fromEntries(
      REQUIRED_FIELDS.filter((field) => !form[field].trim()).map((field) => [field, REQUIRED_MESSAGE]),
    );
    setFieldErrors(missing);
    if (Object.keys(missing).length > 0 || !form.category) return;

    const payload = { ...form, category: form.category, video_url: form.video_url.trim() || null };
    setSaving(true);
    try {
      if (editingId) {
        await updateExercise(editingId, payload);
        setMessage('Ejercicio actualizado.');
      } else {
        await createExercise(payload);
        setMessage('Ejercicio agregado a tu biblioteca.');
      }
      resetForm();
      await loadExercises(muscleFilter);
    } catch (caught) {
      handleError(caught);
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(exercise: Exercise) {
    if (!window.confirm(`¿Eliminar "${exercise.name}"? Las rutinas que ya lo incluyen lo conservan.`)) return;
    setSaving(true);
    setMessage('');
    setError('');
    try {
      await deleteExercise(exercise.id);
      if (editingId === exercise.id) resetForm();
      setMessage('Ejercicio eliminado de tu biblioteca.');
      await loadExercises(muscleFilter);
    } catch (caught) {
      handleError(caught);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando biblioteca…</main>;

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className="profile-card">
        <div className="profile-heading">
          <span>BIBLIOTECA</span>
          <h1>Tus ejercicios</h1>
          <p>Cargá los ejercicios que después vas a usar en las rutinas de tus alumnos.</p>
        </div>

        <form className="profile-form" onSubmit={handleSubmit} noValidate>
          <label>Nombre
            <input value={form.name} onChange={(event) => updateField('name', event.target.value)} maxLength={150} aria-invalid={Boolean(fieldErrors.name)} />
            {fieldErrors.name && <small className="field-error">{fieldErrors.name}</small>}
          </label>
          <label>Categoría
            <select className="exercise-select" value={form.category} onChange={(event) => updateField('category', event.target.value)} aria-invalid={Boolean(fieldErrors.category)}>
              <option value="">Elegí una categoría</option>
              {CATEGORY_OPTIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
            {fieldErrors.category && <small className="field-error">{fieldErrors.category}</small>}
          </label>
          <label>Músculo a trabajar
            <input value={form.target_muscle_group} onChange={(event) => updateField('target_muscle_group', event.target.value)} maxLength={100} placeholder="Cuádriceps" aria-invalid={Boolean(fieldErrors.target_muscle_group)} />
            {fieldErrors.target_muscle_group && <small className="field-error">{fieldErrors.target_muscle_group}</small>}
          </label>
          <label>Elementos necesarios
            <input value={form.equipment_needed} onChange={(event) => updateField('equipment_needed', event.target.value)} maxLength={150} placeholder="Mancuernas" aria-invalid={Boolean(fieldErrors.equipment_needed)} />
            {fieldErrors.equipment_needed && <small className="field-error">{fieldErrors.equipment_needed}</small>}
          </label>
          <label>Descripción
            <textarea value={form.description} onChange={(event) => updateField('description', event.target.value)} rows={3} aria-invalid={Boolean(fieldErrors.description)} />
            {fieldErrors.description && <small className="field-error">{fieldErrors.description}</small>}
          </label>
          <label>Video demostrativo (YouTube, Vimeo o Google Drive)
            <input
              type="text"
              value={form.video_url}
              onChange={(event) => updateField('video_url', event.target.value)}
              maxLength={500}
              placeholder="https://youtu.be/..."
              aria-invalid={Boolean(fieldErrors.video_url)}
              aria-describedby={fieldErrors.video_url ? 'exercise-video-error' : 'exercise-video-help'}
            />
            {fieldErrors.video_url
              ? <small id="exercise-video-error" className="field-error">{fieldErrors.video_url}</small>
              : <small id="exercise-video-help">Dejá el campo vacío para quitar el video.</small>}
          </label>
          {videoPreviewUrl && (
            <iframe
              className="exercise-video"
              src={videoPreviewUrl}
              title="Vista previa del video demostrativo"
              loading="lazy"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowFullScreen
            />
          )}
          <label className="exercise-check">
            <input type="checkbox" checked={form.has_no_materials_alternative} onChange={(event) => setForm((current) => ({ ...current, has_no_materials_alternative: event.target.checked }))} />
            Tiene alternativa "Sin materiales"
          </label>
          {error && <p className="form-alert" role="alert">{error}</p>}
          {message && <p className="profile-success" role="status"><CheckCircle2 size={18} /> {message}</p>}
          <div className="plan-form__actions">
            <button className="profile-save" type="submit" disabled={saving}>
              <Save size={18} /> {saving ? 'Guardando…' : editingId ? 'Guardar cambios' : 'Guardar'}
            </button>
            {editingId && <button className="plan-cancel" type="button" onClick={resetForm} disabled={saving}>Cancelar</button>}
          </div>
        </form>
      </section>

      <section className="exercise-filter" aria-label="Filtros de la biblioteca">
        <label>Filtrar por músculo
          <select className="exercise-select" value={muscleFilter} onChange={(event) => setMuscleFilter(event.target.value)}>
            <option value="">Todos los músculos</option>
            {muscles.map((muscle) => <option key={muscle} value={muscle}>{muscle}</option>)}
          </select>
        </label>
      </section>

      <section className="plan-list" aria-label="Ejercicios cargados">
        {exercises.length === 0
          ? <p className="plan-empty">Todavía no cargaste ejercicios.</p>
          : exercises.map((exercise) => <ExerciseCard key={exercise.id} exercise={exercise} busy={saving} onEdit={startEditing} onDelete={handleDelete} />)}
      </section>
    </main>
  );
}
