import { AlertTriangle, ArrowRight } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { listStudentSubscriptions, listSubscriptions } from '../services/paymentService';
import type { SubscriptionSummary } from '../types/payment';
import { dueDescription, formatIsoDate } from '../utils/subscriptionFormat';
import '../styles/subscriptions.css';

/**
 * US-71 escenarios 2 y 4: aviso en el inicio.
 * Alumno: suscripciones por vencer (0–5 días) o vencidas. Entrenador: vencidas y pagos por confirmar.
 */
export function SubscriptionAlert({ role }: { role: 'TRAINER' | 'STUDENT' }) {
  const [items, setItems] = useState<SubscriptionSummary[]>([]);

  useEffect(() => {
    let active = true;
    const request = role === 'TRAINER' ? listSubscriptions() : listStudentSubscriptions();
    request.then((loaded) => { if (active) setItems(loaded); }).catch(() => undefined);
    return () => { active = false; };
  }, [role]);

  if (role === 'TRAINER') {
    const expired = items.filter((item) => item.status === 'VENCIDA').length;
    const pending = items.reduce((sum, item) => sum + item.pending_payment_count, 0);
    if (expired === 0 && pending === 0) return null;
    const parts = [
      expired > 0 ? (expired === 1 ? '1 suscripción vencida' : `${expired} suscripciones vencidas`) : null,
      pending > 0 ? (pending === 1 ? '1 pago informado por confirmar' : `${pending} pagos informados por confirmar`) : null,
    ].filter(Boolean);
    return (
      <div className={`subscription-alert${expired > 0 ? ' subscription-alert--expired' : ''}`} role="status">
        <AlertTriangle size={20} aria-hidden="true" />
        <p>Tenés {parts.join(' y ')}.</p>
        <Link to={ROUTES.trainerSubscriptions} className="subscription-alert__link">
          Ver suscripciones <ArrowRight size={16} aria-hidden="true" />
        </Link>
      </div>
    );
  }

  const urgent = items.filter((item) => item.status !== 'AL_DIA');
  if (urgent.length === 0) return null;
  const expired = urgent.some((item) => item.status === 'VENCIDA');
  return (
    <div className={`subscription-alert${expired ? ' subscription-alert--expired' : ''}`} role="alert">
      <AlertTriangle size={20} aria-hidden="true" />
      <div>
        {urgent.map((item) => (
          <p key={item.relationship_id}>
            Tu suscripción con {item.trainer_name} vence el <strong>{formatIsoDate(item.due_date)}</strong> ({dueDescription(item).toLowerCase()}).
            {item.status === 'VENCIDA' && ' Tu rutina está bloqueada hasta que tu entrenador confirme un pago.'}
            {item.pending_payment_count > 0 && ' Ya informaste un pago: falta que tu entrenador lo confirme.'}
          </p>
        ))}
      </div>
      <Link to={ROUTES.studentActivePlans} className="subscription-alert__link">
        Informar pago <ArrowRight size={16} aria-hidden="true" />
      </Link>
    </div>
  );
}
