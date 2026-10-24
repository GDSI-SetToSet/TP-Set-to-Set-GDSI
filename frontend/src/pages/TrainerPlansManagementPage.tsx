import axios from 'axios';
import { ArrowLeft, CheckCircle2, Save } from 'lucide-react';
import { type FormEvent, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { PlanCard } from '../components/PlanCard';
import { ROUTES } from '../constants/routes';
import { archiveTrainingPlan, createTrainingPlan, getOwnTrainingPlans, updateTrainingPlan } from '../services/trainerService';
import type { TrainingPlan } from '../types/trainer';

const MIN_PRICE = 0;
const MAX_PRICE = 1_000_000;
const REQUIRED_MESSAGE = 'Este campo es obligatorio';
const PRICE_RANGE_MESSAGE = 'La tarifa debe estar entre $0 y $1.000.000';

interface FormState {
  title: string;
  description: string;
  monthly_price: string;
}

const EMPTY_FORM: FormState = { title: '', description: '', monthly_price: '' };

interface ProblemDetails {
  detail?: string;
  errors?: { field: string; message: string }[];
}

function priceError(value: string): string {
  if (!value.trim()) return '';
  const price = Number(value);
  return Number.isNaN(price) || price < MIN_PRICE || price > MAX_PRICE ? PRICE_RANGE_MESSAGE : '';
}

export function TrainerPlansManagementPage() {
  const [plans, setPlans] = useState<TrainingPlan[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    getOwnTrainingPlans()
      .then(setPlans)
      .catch(() => setError('No pudimos cargar tus paquetes. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  // La tarifa fuera de rango se marca mientras se escribe y bloquea el botón "Guardar" (US-03, escenario 3).
  const rangeError = priceError(form.monthly_price);

  function updateField(field: keyof FormState, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
    setFieldErrors((current) => ({ ...current, [field]: '' }));
  }

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFieldErrors({});
  }

  function startEditing(plan: TrainingPlan) {
    setEditingId(plan.id);
    setForm({ title: plan.title, description: plan.description ?? '', monthly_price: String(plan.monthly_price) });
    setFieldErrors({});
    setMessage('');
    setError('');
  }

  function handleError(caught: unknown) {
    if (axios.isAxiosError<ProblemDetails>(caught)) {
      const fields = Object.fromEntries((caught.response?.data?.errors ?? []).map((item) => [item.field, item.message]));
      setFieldErrors(fields);
      setError(caught.response?.data?.detail ?? 'Revisá los datos ingresados.');
    } else {
      setError('No pudimos guardar los cambios. Intentá nuevamente.');
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setMessage('');
    setError('');
    const missing: Record<string, string> = {};
    if (!form.title.trim()) missing.title = REQUIRED_MESSAGE;
    if (!form.monthly_price.trim()) missing.monthly_price = REQUIRED_MESSAGE;
    setFieldErrors(missing);
    if (Object.keys(missing).length > 0 || rangeError) return;

    const payload = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      monthly_price: Number(form.monthly_price),
    };
    setSaving(true);
    try {
      if (editingId) {
        const updated = await updateTrainingPlan(editingId, payload);
        setPlans((current) => current.map((plan) => (plan.id === updated.id ? updated : plan)));
        setMessage('Paquete actualizado. El cambio aplica a solicitudes futuras.');
      } else {
        const created = await createTrainingPlan(payload);
        setPlans((current) => [...current, created]);
        setMessage('Paquete publicado.');
      }
      resetForm();
    } catch (caught) {
      handleError(caught);
    } finally {
      setSaving(false);
    }
  }

  async function handleArchive(plan: TrainingPlan) {
    if (!window.confirm(`¿Archivar "${plan.title}"? Dejará de mostrarse a nuevos alumnos.`)) return;
    setSaving(true);
    setMessage('');
    setError('');
    try {
      const archived = await archiveTrainingPlan(plan.id);
      setPlans((current) => current.map((item) => (item.id === archived.id ? archived : item)));
      if (editingId === plan.id) resetForm();
      setMessage('Paquete archivado. Los alumnos con vínculo activo conservan su arancel.');
    } catch (caught) {
      handleError(caught);
    } finally {
      setSaving(false);
    }
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando paquetes…</main>;

  const titleError = fieldErrors.title;
  const monthlyPriceError = rangeError || fieldErrors.monthly_price;

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className="profile-card">
        <div className="profile-heading">
          <span>PAQUETES Y TARIFAS</span>
          <h1>Tus paquetes mensuales</h1>
          <p>Los alumnos ven tus paquetes publicados en tu perfil. Editar o archivar un paquete solo afecta a solicitudes futuras.</p>
        </div>

        <form className="profile-form" onSubmit={handleSubmit} noValidate>
          <label>Título
            <input value={form.title} onChange={(event) => updateField('title', event.target.value)} maxLength={100} aria-invalid={Boolean(titleError)} />
            {titleError && <small className="field-error">{titleError}</small>}
          </label>
          <label>Tarifa mensual (ARS)
            <input type="number" inputMode="decimal" min={MIN_PRICE} max={MAX_PRICE} step="0.01" value={form.monthly_price} onChange={(event) => updateField('monthly_price', event.target.value)} placeholder="28000" aria-invalid={Boolean(monthlyPriceError)} />
            {monthlyPriceError && <small className="field-error">{monthlyPriceError}</small>}
          </label>
          <label>Descripción
            <textarea value={form.description} onChange={(event) => updateField('description', event.target.value)} rows={3} placeholder="Servicios incluidos, frecuencia, seguimiento…" />
          </label>
          {error && <p className="form-alert" role="alert">{error}</p>}
          {message && <p className="profile-success" role="status"><CheckCircle2 size={18} /> {message}</p>}
          <div className="plan-form__actions">
            <button className="profile-save" type="submit" disabled={saving || Boolean(rangeError)}>
              <Save size={18} /> {saving ? 'Guardando…' : editingId ? 'Guardar cambios' : 'Guardar'}
            </button>
            {editingId && <button className="plan-cancel" type="button" onClick={resetForm} disabled={saving}>Cancelar</button>}
          </div>
        </form>
      </section>

      <section className="plan-list" aria-label="Paquetes cargados">
        {plans.length === 0
          ? <p className="plan-empty">Todavía no publicaste paquetes.</p>
          : plans.map((plan) => <PlanCard key={plan.id} plan={plan} busy={saving} onEdit={startEditing} onArchive={handleArchive} />)}
      </section>
    </main>
  );
}
