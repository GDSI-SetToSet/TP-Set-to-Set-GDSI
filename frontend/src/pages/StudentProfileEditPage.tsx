import axios from 'axios';
import { ArrowLeft, CheckCircle2, Pencil, Save, X } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getOwnStudentProfile, updateOwnStudentProfile } from '../services/studentService';
import { phoneError } from '../utils/phone';
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
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isEditing, setIsEditing] = useState(false);

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

  const phoneRangeError = phoneError(form.contact_phone, 10);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setIsSubmitting(true);
    setError('');
    setFieldErrors({});
    try {
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
      const updated = await updateOwnStudentProfile(payload);
      setProfile(updated);
      setForm(toForm(updated));
      setGoals(updated.fitness_goals);
      setIsSubmitting(false);
      setIsSuccess(true);
      setIsEditing(false);
    } catch (caught) {
      if (axios.isAxiosError<ProblemDetails>(caught)) {
        const fields = Object.fromEntries((caught.response?.data?.errors ?? []).map((item) => [item.field, item.message]));
        setFieldErrors(fields);
        setError(caught.response?.data?.detail ?? 'Revisá los datos ingresados.');
      } else {
        setError('No pudimos guardar los cambios. Intentá nuevamente.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  function cancelEditing() {
    if (!profile) return;
    setForm(toForm(profile));
    setGoals(profile.fitness_goals);
    setFieldErrors({});
    setError('');
    setIsSuccess(false);
    setIsEditing(false);
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando perfil…</main>;

  return (
    <>
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
        <span className={`profile-status profile-status--${profile?.status.toLowerCase()}`}>
          {profile?.status === 'PUBLISHED' ? 'Perfil publicado' : 'Perfil en borrador'}
        </span>
        {isEditing ? (
          <button type="button" className="profile-edit-toggle" onClick={cancelEditing}><X size={17} /> Cancelar</button>
        ) : (
          <button type="button" className="profile-edit-toggle" onClick={() => { setIsSuccess(false); setIsEditing(true); }}><Pencil size={17} /> Editar información</button>
        )}
      </header>

      <section className="profile-card">
        <div className="profile-heading">
          <span>PERFIL PERSONAL</span>
          <h1>Contanos sobre vos</h1>
          <p>{isEditing ? 'Actualizá tus datos personales y objetivos de entrenamiento.' : 'Tu información personal y los objetivos que compartís con tus entrenadores.'}</p>
        </div>

        {isEditing ? <form className="profile-form" onSubmit={handleSubmit} noValidate>
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
              <input value={form.contact_phone} onChange={(event) => updateField('contact_phone', event.target.value)} placeholder="+5491155551234" aria-invalid={Boolean(phoneRangeError || fieldErrors.contact_phone)} />
              {(phoneRangeError || fieldErrors.contact_phone) && <small className="field-error">{phoneRangeError || fieldErrors.contact_phone}</small>}
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
          <button className="profile-save" type="submit" disabled={isSubmitting || Boolean(phoneRangeError)}><Save size={18} /> {isSubmitting ? 'Guardando...' : 'Guardar perfil'}</button>
        </form> : (
          <dl className="profile-details">
            <div><dt>Nombre</dt><dd>{profile?.first_name || 'Sin completar'}</dd></div>
            <div><dt>Apellido</dt><dd>{profile?.last_name || 'Sin completar'}</dd></div>
            <div><dt>Teléfono / WhatsApp</dt><dd>{profile?.contact_phone || 'Sin completar'}</dd></div>
            <div><dt>Fecha de nacimiento</dt><dd>{profile?.birth_date ? new Date(profile.birth_date).toLocaleDateString('es-AR', { timeZone: 'UTC' }) : 'Sin completar'}</dd></div>
            <div className="profile-details__wide">
              <dt>Objetivos de entrenamiento</dt>
              <dd>
                {profile?.fitness_goals.length ? (
                  <ul className="profile-goal-list">{profile.fitness_goals.map((goal) => <li key={goal}>{FITNESS_GOALS[goal]}</li>)}</ul>
                ) : 'Todavía no agregaste objetivos.'}
              </dd>
            </div>
            <div className="profile-details__wide"><dt>Motivación personal</dt><dd>{profile?.personal_motivation || 'Sin completar'}</dd></div>
            <div className="profile-details__wide"><dt>Biografía</dt><dd>{profile?.bio || 'Sin completar'}</dd></div>
          </dl>
        )}
        {error && <p className="form-alert" role="alert">{error}</p>}
        {isSuccess && <p className="profile-success" role="status"><CheckCircle2 size={18} /> Perfil guardado correctamente.</p>}
      </section>
    </main>
    </>
  );
}