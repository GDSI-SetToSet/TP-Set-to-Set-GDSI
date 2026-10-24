import axios from 'axios';
import { ArrowLeft, CheckCircle2, Save, Users } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { QuotaBadge } from '../components/QuotaBadge';
import { ROUTES } from '../constants/routes';
import { getOwnTrainerProfile, updateOwnTrainerProfile, updateOwnTrainerQuota } from '../services/trainerService';
import { phoneError } from '../utils/phone';
import type { TrainerProfile, TrainerProfileUpdate } from '../types/trainer';

type FormState = Record<keyof TrainerProfileUpdate, string>;
const EMPTY_FORM: FormState = { full_name: '', contact_phone: '', specialty: '', bio: '', certifications: '' };
const MIN_QUOTA = 0;
const MAX_QUOTA = 100;
const QUOTA_RANGE_MESSAGE = 'Los cupos deben estar entre 0 y 100';

function quotaError(value: string): string {
  if (!value.trim()) return '';
  const quota = Number(value);
  return Number.isInteger(quota) && quota >= MIN_QUOTA && quota <= MAX_QUOTA ? '' : QUOTA_RANGE_MESSAGE;
}

interface ProblemDetails {
  detail?: string;
  errors?: { field: string; message: string }[];
}

export function TrainerProfileEditPage() {
  const [profile, setProfile] = useState<TrainerProfile | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [quota, setQuota] = useState('');
  const [savingQuota, setSavingQuota] = useState(false);
  const [quotaMessage, setQuotaMessage] = useState('');
  const [quotaFailure, setQuotaFailure] = useState('');

  useEffect(() => {
    getOwnTrainerProfile()
      .then((data) => {
        setProfile(data);
        setQuota(String(data.max_students));
        setForm({
          full_name: data.full_name ?? '',
          contact_phone: data.contact_phone ?? '',
          specialty: data.specialty ?? '',
          bio: data.bio ?? '',
          certifications: data.certifications ?? '',
        });
      })
      .catch(() => setError('No pudimos cargar tu perfil. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  function updateField(field: keyof FormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: '' }));
  }

  const phoneRangeError = phoneError(form.contact_phone, 8);

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
      if (trimmed) changedFields[field] = trimmed;
      else if (profile?.[field]) changedFields[field] = null;
    });
    const payload = changedFields as TrainerProfileUpdate;
    try {
      const updated = await updateOwnTrainerProfile(payload);
      setProfile(updated);
      setForm({
        full_name: updated.full_name ?? '',
        contact_phone: updated.contact_phone ?? '',
        specialty: updated.specialty ?? '',
        bio: updated.bio ?? '',
        certifications: updated.certifications ?? '',
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

  // Un tope fuera de rango se marca mientras se escribe y bloquea "Guardar cupos" (US-04, escenario 3).
  const quotaRangeError = quotaError(quota);

  async function handleQuotaSubmit(event: FormEvent) {
    event.preventDefault();
    if (quotaRangeError) return;
    setSavingQuota(true);
    setQuotaMessage('');
    setQuotaFailure('');
    try {
      const updated = await updateOwnTrainerQuota(quota.trim() ? Number(quota) : null);
      setProfile((current) => current && {
        ...current,
        max_students: updated.max_students,
        active_students_count: updated.active_students,
        available_slots: updated.available_slots,
        has_available_quota: updated.has_available_quota,
      });
      setQuota(String(updated.max_students));
      setQuotaMessage(updated.active_students > updated.max_students
        ? 'Cupos guardados. Tenés más alumnos activos que el nuevo tope: no vas a recibir solicitudes hasta liberar cupos.'
        : 'Cupos guardados.');
    } catch {
      setQuotaFailure('No pudimos guardar los cupos. Intentá nuevamente.');
    } finally {
      setSavingQuota(false);
    }
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando perfil…</main>;

  return (
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
        <span className={`profile-status profile-status--${profile?.status.toLowerCase()}`}>
          {profile?.status === 'PUBLISHED' ? 'Perfil publicado' : 'Perfil en borrador'}
        </span>
      </header>

      <section className="profile-card">
        <div className="profile-heading">
          <span>PERFIL PROFESIONAL</span>
          <h1>Contales cómo entrenás</h1>
          <p>Podés guardar avances. Para publicar necesitás nombre, teléfono y especialidad.</p>
        </div>

        <form className="profile-form" onSubmit={handleSubmit} noValidate>
          <label>Nombre completo
            <input value={form.full_name} onChange={(event) => updateField('full_name', event.target.value)} maxLength={150} aria-invalid={Boolean(fieldErrors.full_name)} />
            {fieldErrors.full_name && <small className="field-error">{fieldErrors.full_name}</small>}
          </label>
          <div className="profile-grid">
            <label>Teléfono / WhatsApp
              <input value={form.contact_phone} onChange={(event) => updateField('contact_phone', event.target.value)} placeholder="+5491155551234" aria-invalid={Boolean(phoneRangeError || fieldErrors.contact_phone)} />
              {(phoneRangeError || fieldErrors.contact_phone) && <small className="field-error">{phoneRangeError || fieldErrors.contact_phone}</small>}
            </label>
            <label>Especialidad principal
              <input value={form.specialty} onChange={(event) => updateField('specialty', event.target.value)} maxLength={100} aria-invalid={Boolean(fieldErrors.specialty)} />
              {fieldErrors.specialty && <small className="field-error">{fieldErrors.specialty}</small>}
            </label>
          </div>
          <label>Biografía y metodología
            <textarea value={form.bio} onChange={(event) => updateField('bio', event.target.value)} rows={5} />
          </label>
          <label>Certificaciones
            <textarea value={form.certifications} onChange={(event) => updateField('certifications', event.target.value)} rows={3} />
          </label>
          {error && <p className="form-alert" role="alert">{error}</p>}
          {message && <p className="profile-success" role="status"><CheckCircle2 size={18} /> {message}</p>}
          <button className="profile-save" type="submit" disabled={saving || Boolean(phoneRangeError)}><Save size={18} /> {saving ? 'Guardando…' : 'Guardar perfil'}</button>
        </form>
      </section>

      <section className="profile-card quota-card" aria-labelledby="quota-title">
        <div className="quota-card__header">
          <div className="profile-heading">
            <span>CUPOS</span>
            <h2 id="quota-title">¿Cuántos alumnos podés tomar?</h2>
            <p>Al llegar al tope dejás de recibir solicitudes nuevas. Si lo dejás vacío se guarda en 0.</p>
          </div>
          {profile && <QuotaBadge availableSlots={profile.available_slots} hasAvailableQuota={profile.has_available_quota} />}
        </div>
        <form className="profile-form quota-form" onSubmit={handleQuotaSubmit} noValidate>
          <label>Tope de alumnos
            <input type="number" inputMode="numeric" min={MIN_QUOTA} max={MAX_QUOTA} step={1} value={quota} onChange={(event) => { setQuota(event.target.value); setQuotaMessage(''); }} aria-invalid={Boolean(quotaRangeError)} aria-describedby="quota-help" />
            {quotaRangeError
              ? <small className="field-error">{quotaRangeError}</small>
              : <small id="quota-help" className="quota-help">Alumnos activos: {profile?.active_students_count ?? 0}</small>}
          </label>
          {quotaFailure && <p className="form-alert" role="alert">{quotaFailure}</p>}
          {quotaMessage && <p className="profile-success" role="status"><CheckCircle2 size={18} /> {quotaMessage}</p>}
          <button className="profile-save" type="submit" disabled={savingQuota || Boolean(quotaRangeError)}><Users size={18} /> {savingQuota ? 'Guardando…' : 'Guardar cupos'}</button>
        </form>
      </section>
    </main>
  );
}
