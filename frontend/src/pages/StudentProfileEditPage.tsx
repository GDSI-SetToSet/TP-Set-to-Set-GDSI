import axios from 'axios';
import { ArrowLeft, CheckCircle2, Save } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getOwnStudentProfile, updateOwnStudentProfile } from '../services/studentService';
import { FITNESS_GOALS, type FitnessGoal, type StudentProfile, type StudentProfileUpdate } from '../types/student';

type TextField = Exclude<keyof StudentProfileUpdate, 'fitness_goals'>;
type FormState = Record<TextField, string>;
const EMPTY_FORM: FormState = { first_name: '', last_name: '', birth_date: '', contact_phone: '', profile_picture: '', bio: '', personal_motivation: '' };

function toForm(data: StudentProfile): FormState {
  return {
    first_name: data.first_name ?? '',
    last_name: data.last_name ?? '',
    birth_date: data.birth_date ? data.birth_date.split('T')[0] : '',
    contact_phone: data.contact_phone ?? '',
    profile_picture: data.profile_picture ?? '',
    bio: data.bio ?? '',
    personal_motivation: data.personal_motivation ?? '',
  };
}

interface ProblemDetails {
  detail?: string;
  errors?: { field: string; message: string }[];
}

export function StudentProfileEditPage() {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [goals, setGoals] = useState<FitnessGoal[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    getOwnStudentProfile()
      .then((data) => {
        setProfile(data);
        setForm(toForm(data));
        setGoals(data.fitness_goals);
      })
      .catch(() => setError('No pudimos cargar tu perfil. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  function toggleGoal(goal: FitnessGoal) {
    setGoals((current) => (current.includes(goal) ? current.filter((item) => item !== goal) : [...current, goal]));
    setFieldErrors((current) => ({ ...current, fitness_goals: '' }));
  }

  function updateField(field: TextField, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: '' }));
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setSaving(true);
    setMessage('');
    setError('');
    setFieldErrors({});
    
    const changedFields: Record<string, string | null> = {};
    Object.entries(form).forEach(([key, value]) => {
      const field = key as TextField;
      const trimmed = value.trim();
      
      if (field === 'birth_date' && trimmed) {
          changedFields[field] = `${trimmed}T00:00:00Z`;
      } else if (trimmed) {
          changedFields[field] = trimmed;
      } else if (profile?.[field]) {
          changedFields[field] = null;
      }
    });

    const payload = { ...changedFields, fitness_goals: goals } as StudentProfileUpdate;
    
    try {
      const updated = await updateOwnStudentProfile(payload);
      setProfile(updated);
      setForm(toForm(updated));
      setGoals(updated.fitness_goals);
      setMessage(updated.status === 'PUBLISHED' ? 'Perfil guardado y publicado.' : 'Avance guardado. Tu perfil continúa en borrador.');
    } catch (caught) {
      if (axios.isAxiosError<ProblemDetails>(caught)) {
        const fields = Object.fromEntries((caught.response?.data?.errors ?? []).map((item) => [item.field, item.message]));
        setFieldErrors(fields);
        setError(caught.response?.data?.detail ?? 'Revisá los datos ingresados.');
      } else {
        setError('No pudimos guardar los cambios. Intentá nuevamente.');
      }
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando perfil…</main>;

  return (
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
        <span className={`profile-status profile-status--${profile?.status.toLowerCase()}`}>
          {profile?.status === 'PUBLISHED' ? 'Perfil publicado' : 'Perfil en borrador'}
        </span>
      </header>

      <section className="profile-card">
        <div className="profile-heading">
          <span>PERFIL PERSONAL</span>
          <h1>Contanos sobre vos</h1>
          <p>Podés guardar avances. Para publicar necesitás nombre, apellido, fecha de nacimiento, teléfono y al menos un objetivo.</p>
        </div>

        <form className="profile-form" onSubmit={handleSubmit} noValidate>
          <div className="profile-grid">
            <label>Nombre
              <input value={form.first_name} onChange={(event) => updateField('first_name', event.target.value)} maxLength={100} aria-invalid={Boolean(fieldErrors.first_name)} />
              {fieldErrors.first_name && <small className="field-error">{fieldErrors.first_name}</small>}
            </label>
            <label>Apellido
              <input value={form.last_name} onChange={(event) => updateField('last_name', event.target.value)} maxLength={100} aria-invalid={Boolean(fieldErrors.last_name)} />
              {fieldErrors.last_name && <small className="field-error">{fieldErrors.last_name}</small>}
            </label>
          </div>
          <div className="profile-grid">
            <label>Teléfono / WhatsApp
              <input value={form.contact_phone} onChange={(event) => updateField('contact_phone', event.target.value)} placeholder="+5491155551234" aria-invalid={Boolean(fieldErrors.contact_phone)} />
              {fieldErrors.contact_phone && <small className="field-error">{fieldErrors.contact_phone}</small>}
            </label>
            <label>Fecha de nacimiento
              <input type="date" value={form.birth_date} onChange={(event) => updateField('birth_date', event.target.value)} aria-invalid={Boolean(fieldErrors.birth_date)} />
              {fieldErrors.birth_date && <small className="field-error">{fieldErrors.birth_date}</small>}
            </label>
          </div>
          <fieldset>
            <legend>Objetivos de entrenamiento</legend>
            {(Object.entries(FITNESS_GOALS) as [FitnessGoal, string][]).map(([goal, label]) => (
              <label key={goal}>
                <input type="checkbox" checked={goals.includes(goal)} onChange={() => toggleGoal(goal)} /> {label}
              </label>
            ))}
            {goals.length === 0 && <small className="field-error">Elegí al menos un objetivo para publicar tu perfil.</small>}
            {fieldErrors.fitness_goals && <small className="field-error">{fieldErrors.fitness_goals}</small>}
          </fieldset>
          <label>Motivación personal
            <textarea value={form.personal_motivation} onChange={(event) => updateField('personal_motivation', event.target.value)} rows={3} placeholder="Opcional: ¿qué te motiva a entrenar?" />
          </label>
          <label>Biografía
            <textarea value={form.bio} onChange={(event) => updateField('bio', event.target.value)} rows={4} placeholder="Opcional: Contale a tus entrenadores un poco más sobre vos" />
          </label>
          {error && <p className="form-alert" role="alert">{error}</p>}
          {message && <p className="profile-success" role="status"><CheckCircle2 size={18} /> {message}</p>}
          <button className="profile-save" type="submit" disabled={saving}><Save size={18} /> {saving ? 'Guardando…' : 'Guardar perfil'}</button>
        </form>
      </section>
    </main>
  );
}