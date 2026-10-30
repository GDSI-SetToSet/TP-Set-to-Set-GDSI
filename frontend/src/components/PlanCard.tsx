import { Archive, Pencil } from 'lucide-react';
import type { TrainingPlan } from '../types/trainer';

interface PlanCardProps {
  plan: TrainingPlan;
  busy: boolean;
  onEdit: (plan: TrainingPlan) => void;
  onArchive: (plan: TrainingPlan) => void;
}

export function formatPrice(amount: number, currency: string): string {
  return new Intl.NumberFormat('es-AR', { style: 'currency', currency, maximumFractionDigits: 2 }).format(amount);
}

export function PlanCard({ plan, busy, onEdit, onArchive }: PlanCardProps) {
  return (
    <article className={`plan-card${plan.is_active ? '' : ' plan-card--archived'}`}>
      <div className="plan-card__top">
        <h3>{plan.title}</h3>
        <span className={`plan-badge plan-badge--${plan.is_active ? 'active' : 'archived'}`}>
          {plan.is_active ? 'Publicado' : 'Archivado'}
        </span>
      </div>
      <p className="plan-card__price">{formatPrice(plan.monthly_price, plan.currency)} <span>/ mes</span></p>
      {plan.description && <p className="plan-card__description">{plan.description}</p>}
      {plan.is_active && (
        <div className="plan-card__actions">
          <button type="button" onClick={() => onEdit(plan)} disabled={busy}><Pencil size={16} /> Editar</button>
          <button type="button" onClick={() => onArchive(plan)} disabled={busy}><Archive size={16} /> Archivar</button>
        </div>
      )}
    </article>
  );
}
