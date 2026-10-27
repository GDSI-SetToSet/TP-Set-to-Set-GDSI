import { Calendar, CheckCircle2, Clock, Dumbbell, Mail, MessageSquare, Phone, UserCheck } from 'lucide-react';
import type { ActivePlanResponse } from '../types/discovery';

interface ActivePlanCardProps {
  plan: ActivePlanResponse;
  onRoutineClick?: () => void;
}

export function ActivePlanCard({ plan, onRoutineClick }: ActivePlanCardProps) {
  const isPending = plan.status === 'PENDING';
  if ((!plan.has_active_plan && !isPending) || !plan.trainer) {
    return null;
  }

  const { trainer, plan: contractedPlan, routine, welcome_message, agreed_monthly_price, agreed_currency, start_date } = plan;

  const displayDate = isPending ? plan.requested_at : start_date;
  const formattedDate = displayDate
    ? new Date(displayDate).toLocaleDateString('es-AR', {
        day: '2-digit',
        month: 'long',
        year: 'numeric',
      })
    : '';

  return (
    <article
      className={`active-plan-card${isPending ? ' active-plan-card--pending' : ''}`}
      aria-label={isPending ? 'Solicitud de plan pendiente' : 'Plan de entrenamiento activo'}
    >
      <header className="active-plan-card__header">
        <div className={`active-plan-card__badge${isPending ? ' active-plan-card__badge--pending' : ''}`}>
          {isPending ? <Clock size={16} /> : <CheckCircle2 size={16} />}
          <span>{isPending ? 'Solicitud Pendiente' : 'Vínculo Activo'}</span>
        </div>
        {formattedDate && (
          <span className="active-plan-card__start-date">
            <Calendar size={14} /> {isPending ? 'Enviada' : 'Desde'} {formattedDate}
          </span>
        )}
      </header>

      <div className="active-plan-card__content">
        <section className="active-plan-card__trainer-info">
          <div className="active-plan-card__trainer-avatar">
            <UserCheck size={32} />
          </div>
          <div>
            <h3 className="active-plan-card__trainer-name">{trainer.full_name || 'Entrenador asignado'}</h3>
            <p className="active-plan-card__specialty">{trainer.specialty || 'Entrenador personal'}</p>
            <div className="active-plan-card__contacts">
              {trainer.email && (
                <span className="active-plan-card__contact-item">
                  <Mail size={13} /> {trainer.email}
                </span>
              )}
              {trainer.phone && (
                <span className="active-plan-card__contact-item">
                  <Phone size={13} /> {trainer.phone}
                </span>
              )}
            </div>
          </div>
        </section>

        <section className="active-plan-card__plan-info">
          <div className="active-plan-card__plan-header">
            <div>
              <span className="active-plan-card__kicker">Plan contratado</span>
              <h4 className="active-plan-card__plan-title">{contractedPlan?.title || 'Entrenamiento personalizado'}</h4>
            </div>
            <div className="active-plan-card__price">
              ${agreed_monthly_price?.toLocaleString('es-AR')} {agreed_currency}
              <span className="active-plan-card__price-sub">/mes</span>
            </div>
          </div>
        </section>

        {!isPending && welcome_message && (
          <section className="active-plan-card__welcome" aria-label="Mensaje de bienvenida">
            <div className="active-plan-card__welcome-header">
              <MessageSquare size={16} />
              <span>Mensaje de bienvenida de tu entrenador</span>
            </div>
            <blockquote className="active-plan-card__welcome-text">
              “{welcome_message}”
            </blockquote>
          </section>
        )}

        <section
          className="active-plan-card__routine-status"
          aria-label={isPending ? 'Estado de la solicitud' : 'Estado de la rutina'}
        >
          {isPending ? (
            <div className="active-plan-card__request-pending" role="status">
              <Clock size={20} className="active-plan-card__pending-icon" />
              <p>
                Solicitud enviada. Esperando a que el entrenador apruebe tu solicitud para este plan.
              </p>
            </div>
          ) : routine && routine.is_available ? (
            <div className="active-plan-card__routine-available">
              <div>
                <span className="active-plan-card__kicker">Tu rutina actual</span>
                <h4 className="active-plan-card__routine-title">{routine.name}</h4>
              </div>
              <button
                type="button"
                className="active-plan-card__routine-btn"
                onClick={onRoutineClick}
              >
                <Dumbbell size={16} /> Ver mi rutina
              </button>
            </div>
          ) : (
            <div className="active-plan-card__routine-pending">
              <Clock size={20} className="active-plan-card__pending-icon" />
              <div>
                <strong>Rutina en preparación</strong>
                <p>Tu entrenador está diseñando tu primera rutina. Recibirás una notificación en cuanto esté publicada.</p>
              </div>
            </div>
          )}
        </section>
      </div>
    </article>
  );
}
