import { ArrowLeft, Send, CheckCircle } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getTrainerPublicDetail, sendTrainingRequest } from '../services/discoveryService';
import type { TrainerPublicDetail, TrainingPlanPublic } from '../types/discovery';
import '../styles/discovery.css';

export function TrainerRequestPage() {
  const { trainerId } = useParams<{ trainerId: string }>();
  const [searchParams] = useSearchParams();
  const planId = searchParams.get('plan');
  const navigate = useNavigate();

  const [detail, setDetail] = useState<TrainerPublicDetail | null>(null);
  const [plan, setPlan] = useState<TrainingPlanPublic | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!trainerId) return;
    getTrainerPublicDetail(trainerId)
      .then(d => {
        setDetail(d);
        if (planId) {
          const found = d.plans.find(p => p.id === planId);
          setPlan(found ?? null);
        }
      })
      .catch(() => setError('No se pudo cargar la información del entrenador.'))
      .finally(() => setLoading(false));
  }, [trainerId, planId]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!trainerId || !plan) return;
    setSubmitting(true);
    setError('');
    try {
      await sendTrainingRequest({
        trainer_id: trainerId,
        plan_id: plan.id,
        student_message: message.trim() || null,
      });
      setSuccess(true);
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(msg ?? 'Error al enviar la solicitud.');
    } finally {
      setSubmitting(false);
    }
  }

  if (loading) return <main className="discovery-shell"><p className="discovery-loading">Cargando…</p></main>;

  if (success) {
    return (
      <main className="discovery-shell">
        <section className="request-success">
          <CheckCircle size={48} className="success-icon" />
          <h2>Tu solicitud fue enviada</h2>
          <p>El entrenador la revisará pronto.</p>
          <div className="request-success__actions">
            <Link to={ROUTES.studentRequests} className="filter-btn">Ver mis solicitudes</Link>
            <Link to={ROUTES.trainerSearch} className="back-link">Buscar más entrenadores</Link>
          </div>
        </section>
      </main>
    );
  }

  if (!detail || !plan) {
    return (
      <main className="discovery-shell">
        <p className="form-alert" role="alert">{error || 'Entrenador o plan no encontrado.'}</p>
        <Link to={ROUTES.trainerSearch} className="back-link"><ArrowLeft size={16} /> Volver</Link>
      </main>
    );
  }

  return (
    <main className="discovery-shell">
      <header className="discovery-header">
        <Link to={`/entrenadores/${trainerId}`} className="back-link"><ArrowLeft size={16} /> Volver al perfil</Link>
        <h1><Send size={20} /> Enviar solicitud</h1>
      </header>

      <section className="request-summary">
        <div className="request-summary__trainer">
          <h3>{detail.full_name ?? 'Entrenador'}</h3>
          {detail.specialty && <span className="trainer-detail__specialty">{detail.specialty}</span>}
        </div>
        <div className="request-summary__plan">
          <h4>{plan.title}</h4>
          <span>${plan.monthly_price.toLocaleString('es-AR')} {plan.currency}/mes</span>
        </div>
      </section>

      <form className="request-form" onSubmit={handleSubmit}>
        <label htmlFor="student-message">Mensaje de presentación (opcional)</label>
        <textarea
          id="student-message"
          value={message}
          onChange={e => setMessage(e.target.value)}
          placeholder="Contale al entrenador sobre tus objetivos y motivación…"
          rows={4}
          maxLength={1000}
        />
        {error && <p className="form-alert" role="alert">{error}</p>}
        <button type="submit" className="filter-btn request-submit" disabled={submitting}>
          {submitting ? 'Enviando…' : 'Enviar solicitud'}
        </button>
      </form>
    </main>
  );
}
