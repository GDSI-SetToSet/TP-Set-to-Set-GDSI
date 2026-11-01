import axios from 'axios';
import { ArrowLeft, CheckCircle2, Pencil, Plus, Save, Users, X } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { QuotaBadge } from '../components/QuotaBadge';
import { ROUTES } from '../constants/routes';
import { getOwnTrainerProfile, updateOwnTrainerProfile, updateOwnTrainerQuota } from '../services/trainerService';
import { phoneError } from '../utils/phone';
import { parseTrainerSpecialties, TRAINER_SPECIALTIES } from '../constants/trainerSpecialties';
import type { TrainerProfile, TrainerProfileUpdate } from '../types/trainer';
import '../styles/profile-choice-fields.css';

type FormState = Record<keyof TrainerProfileUpdate, string>;
const EMPTY_FORM: FormState = { full_name: '', contact_phone: '', specialty: '', bio: '', certifications: '' };
function serializeSpecialties(values: string[]): string {
  return [...new Set(values.filter(Boolean))].join(' | ');
}
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
  const [specialties, setSpecialties] = useState<string[]>(['']);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isEditing, setIsEditing] = useState(false);
  const [quota, setQuota] = useState('');
  const [savingQuota, setSavingQuota] = useState(false);
  const [quotaMessage, setQuotaMessage] = useState('');
  const [quotaFailure, setQuotaFailure] = useState('');

  useEffect(() => {
    getOwnTrainerProfile()
      .then((data) => {
        setProfile(data);
        setQuota(String(data.max_students));
        setSpecialties(parseTrainerSpecialties(data.specialty).length ? parseTrainerSpecialties(data.specialty) : ['']);
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

  function updateSpecialty(index: number, value: string) {
    const next = specialties.map((specialty, itemIndex) => itemIndex === index ? value : specialty);
    setSpecialties(next);
    updateField('specialty', serializeSpecialties(next));
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
      setSpecialties(parseTrainerSpecialties(updated.specialty).length ? parseTrainerSpecialties(updated.specialty) : ['']);
      setMessage(updated.status === 'PUBLISHED' ? 'Perfil guardado y publicado.' : 'Avance guardado. Tu perfil continúa en borrador.');
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

  function cancelEditing() {
    if (!profile) return;
    setForm({
      full_name: profile.full_name ?? '',
      contact_phone: profile.contact_phone ?? '',
      specialty: profile.specialty ?? '',
      bio: profile.bio ?? '',
      certifications: profile.certifications ?? '',
    });
    setSpecialties(parseTrainerSpecialties(profile.specialty).length ? parseTrainerSpecialties(profile.specialty) : ['']);
    setQuota(String(profile.max_students));
    setFieldErrors({});
    setError('');
    setMessage('');
    setQuotaMessage('');
    setQuotaFailure('');
    setIsEditing(false);
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando perfil…</main>;

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
        <span className={`profile-status profile-status--${profile?.status.toLowerCase()}`}>
          {profile?.status === 'PUBLISHED' ? 'Perfil publicado' : 'Perfil en borrador'}
        </span>
        {isEditing ? (
          <button type="button" className="profile-edit-toggle" onClick={cancelEditing}><X size={17} /> Cancelar</button>
        ) : (
          <button type="button" className="profile-edit-toggle" onClick={() => setIsEditing(true)}><Pencil size={17} /> Editar información</button>
        )}
      </header>

      <div className="profile-dashboard">
      <section className="profile-card">
        <div className="profile-heading">
          <span>PERFIL PROFESIONAL</span>
          <h1>Contales cómo entrenás</h1>
          <p>{isEditing ? 'Para publicar tu perfil necesitás nombre, teléfono y especialidad.' : 'Tu presentación profesional y disponibilidad para nuevos alumnos.'}</p>
        </div>

        {isEditing ? <form className="profile-form" onSubmit={handleSubmit} noValidate>
          <label>Nombre completo
            <input value={form.full_name} onChange={(event) => updateField('full_name', event.target.value)} maxLength={150} aria-invalid={Boolean(fieldErrors.full_name)} />
            {fieldErrors.full_name && <small className="field-error">{fieldErrors.full_name}</small>}
          </label>
          <label className="trainer-profile-phone">Teléfono / WhatsApp
            <input value={form.contact_phone} onChange={(event) => updateField('contact_phone', event.target.value)} placeholder="+5491155551234" aria-invalid={Boolean(phoneRangeError || fieldErrors.contact_phone)} />
            {(phoneRangeError || fieldErrors.contact_phone) && <small className="field-error">{phoneRangeError || fieldErrors.contact_phone}</small>}
          </label>
          <section className="trainer-specialty-editor" aria-labelledby="trainer-specialty-title">
            <div className="trainer-specialty-editor__heading">
              <h2 id="trainer-specialty-title">Especialidades</h2>
              <p>Elegí una o más áreas para que los alumnos encuentren tu perfil.</p>
            </div>
            <div className="profile-choice-list">
              {specialties.map((specialty, index) => (
                <div className="profile-choice-row trainer-specialty-row" key={index}>
                  <label className="profile-choice-field">
                    {index === 0 ? 'Especialidad principal' : `Especialidad ${index + 1}`}
                    <select
                      className="profile-choice-select"
                      value={specialty}
                      onChange={(event) => updateSpecialty(index, event.target.value)}
                      aria-invalid={Boolean(fieldErrors.specialty)}
                    >
                      <option value="" disabled>Elegí una especialidad</option>
                      {TRAINER_SPECIALTIES.map((option) => (
                        <option key={option} value={option} disabled={specialties.some((selected, selectedIndex) => selected === option && selectedIndex !== index)}>
                          {option}
                        </option>
                      ))}
                      {specialty && !TRAINER_SPECIALTIES.includes(specialty as typeof TRAINER_SPECIALTIES[number]) && (
                        <option value={specialty}>Valor actual: {specialty}</option>
                      )}
                    </select>
                  </label>
                  <div className="profile-choice-actions">
                    {index > 0 && (
                      <button type="button" className="profile-choice-remove" aria-label="Quitar especialidad" onClick={() => {
                        const next = specialties.filter((_, itemIndex) => itemIndex !== index);
                        setSpecialties(next);
                        updateField('specialty', serializeSpecialties(next));
                      }}><X size={18} /></button>
                    )}
                    {index === specialties.length - 1 && (
                      <button
                        type="button"
                        className="profile-choice-add"
                        aria-label="Agregar especialidad"
                        title="Agregar especialidad"
                        disabled={specialties.length >= TRAINER_SPECIALTIES.length}
                        onClick={() => setSpecialties((current) => [...current, ''])}
                      ><Plus size={20} /></button>
                    )}
                  </div>
                </div>
              ))}
              {fieldErrors.specialty && <small className="field-error">{fieldErrors.specialty}</small>}
            </div>
          </section>
          <label>Biografía y metodología
            <textarea value={form.bio} onChange={(event) => updateField('bio', event.target.value)} rows={5} />
          </label>
          <label>Certificaciones
            <textarea value={form.certifications} onChange={(event) => updateField('certifications', event.target.value)} rows={3} />
          </label>
          <button className="profile-save" type="submit" disabled={saving || Boolean(phoneRangeError)}><Save size={18} /> {saving ? 'Guardando…' : 'Guardar perfil'}</button>
        </form> : (
          <dl className="profile-details">
            <div><dt>Nombre completo</dt><dd>{profile?.full_name || 'Sin completar'}</dd></div>
            <div><dt>Teléfono / WhatsApp</dt><dd>{profile?.contact_phone || 'Sin completar'}</dd></div>
            <div className="profile-details__wide"><dt>Especialidades</dt><dd>
              {parseTrainerSpecialties(profile?.specialty).length ? (
                <ul className="trainer-specialty-pills">{parseTrainerSpecialties(profile?.specialty).map((specialty) => <li className="trainer-specialty-pill" key={specialty}>{specialty}</li>)}</ul>
              ) : 'Sin completar'}
            </dd></div>
            <div className="profile-details__wide"><dt>Biografía y metodología</dt><dd>{profile?.bio || 'Todavía no agregaste una biografía.'}</dd></div>
            <div className="profile-details__wide"><dt>Certificaciones</dt><dd>{profile?.certifications || 'Todavía no agregaste certificaciones.'}</dd></div>
          </dl>
        )}
        {error && <p className="form-alert" role="alert">{error}</p>}
        {message && <p className="profile-success" role="status"><CheckCircle2 size={18} /> {message}</p>}
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
        {isEditing ? <form className="profile-form quota-form" onSubmit={handleQuotaSubmit} noValidate>
          <label>Tope de alumnos
            <input type="number" inputMode="numeric" min={MIN_QUOTA} max={MAX_QUOTA} step={1} value={quota} onChange={(event) => { setQuota(event.target.value); setQuotaMessage(''); }} aria-invalid={Boolean(quotaRangeError)} aria-describedby="quota-help" />
            {quotaRangeError
              ? <small className="field-error">{quotaRangeError}</small>
              : <small id="quota-help" className="quota-help">Alumnos activos: {profile?.active_students_count ?? 0}</small>}
          </label>
          {quotaFailure && <p className="form-alert" role="alert">{quotaFailure}</p>}
          {quotaMessage && <p className="profile-success" role="status"><CheckCircle2 size={18} /> {quotaMessage}</p>}
          <button className="profile-save" type="submit" disabled={savingQuota || Boolean(quotaRangeError)}><Users size={18} /> {savingQuota ? 'Guardando…' : 'Guardar cupos'}</button>
        </form> : (
          <div className="quota-overview">
            <div><span>Tope de alumnos</span><strong>{profile?.max_students ?? 0}</strong></div>
            <div><span>Alumnos activos</span><strong>{profile?.active_students_count ?? 0}</strong></div>
            <div><span>Cupos disponibles</span><strong>{profile?.available_slots ?? 0}</strong></div>
            <p>Al alcanzar el tope, vas a dejar de recibir solicitudes nuevas.</p>
          </div>
        )}
      </section>
      </div>
    </main>
  );
}
