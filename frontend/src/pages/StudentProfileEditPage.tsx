import axios from 'axios';
import { ArrowLeft, CheckCircle2, Save } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getOwnStudentProfile, updateOwnStudentProfile } from '../services/studentService';
import type { StudentProfile, StudentProfileUpdate } from '../types/student';

type FormState = Record<keyof StudentProfileUpdate, string>;
const EMPTY_FORM: FormState = { full_name: '', birth_date: '', contact_phone: '', profile_picture: '', bio: '' };

interface ProblemDetails {
  detail?: string;
  errors?: { field: string; message: string }[];
}

export function StudentProfileEditPage() {
  const [profile, setProfile] = useState<StudentProfile | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    getOwnStudentProfile()
      .then((data) => {
        setProfile(data);
        setForm({
          full_name: data.full_name ?? '',
          birth_date: data.birth_date ? data.birth_date.split('T')[0] : '', 
          contact_phone: data.contact_phone ?? '',
          profile_picture: data.profile_picture ?? '',
          bio: data.bio ?? '',
        });
      })
      .catch(() => setError('No pudimos cargar tu perfil. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  function updateField(field: keyof FormState, value: string) {
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
      const field = key as keyof FormState;
      const trimmed = value.trim();
      
      if (field === 'birth_date' && trimmed) {
          changedFields[field] = `${trimmed}T00:00:00Z`;
      } else if (trimmed) {
          changedFields[field] = trimmed;
      } else if (profile?.[field]) {
          changedFields[field] = null;
      }
    });

    const payload = changedFields as StudentProfileUpdate;
    
    try {
      const updated = await updateOwnStudentProfile(payload);
      setProfile(updated);
      setForm({
        full_name: updated.full_name ?? '',
        birth_date: updated.birth_date ? updated.birth_date.split('T')[0] : '',
        contact_phone: updated.contact_phone ?? '',
        profile_picture: updated.profile_picture ?? '',
        bio: updated.bio ?? '',
      });
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
          <p>Podés guardar avances. Para publicar necesitás nombre, fecha de nacimiento y teléfono.</p>
        </div>

        <form className="profile-form" onSubmit={handleSubmit} noValidate>
          <label>Nombre completo
            <input value={form.full_name} onChange={(event) => updateField('full_name', event.target.value)} maxLength={150} aria-invalid={Boolean(fieldErrors.full_name)} />
            {fieldErrors.full_name && <small className="field-error">{fieldErrors.full_name}</small>}
          </label>
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