import { MessageSquareText } from 'lucide-react';
import type { EffortFeedback } from '../types/routineTemplate';
import { categoryLabel } from './EffortFeedbackForm';
import '../styles/effort-feedback.css';

interface EffortFeedbackListProps {
  items: EffortFeedback[];
  emptyMessage?: string;
  highlightUnseen?: boolean;
}

/** US-64: devoluciones del entrenador para el alumno (historial o avisos nuevos). */
export function EffortFeedbackList({ items, emptyMessage, highlightUnseen = false }: EffortFeedbackListProps) {
  if (items.length === 0) {
    return emptyMessage ? <p className="plan-empty">{emptyMessage}</p> : null;
  }
  return (
    <ul className="effort-feedback-list">
      {items.map((item) => (
        <li key={item.id} className={`effort-feedback-list__item effort-feedback-list__item--${item.category.toLowerCase()}`}>
          <MessageSquareText size={18} aria-hidden="true" />
          <div>
            <strong>
              {categoryLabel(item.category)}
              {highlightUnseen && !item.seen_at && <span className="effort-feedback-list__new">Nueva</span>}
            </strong>
            {item.comment && <p>{item.comment}</p>}
            <span className="effort-feedback-list__meta">
              {item.day_name} · <time dateTime={item.session_started_at}>{new Date(item.session_started_at).toLocaleDateString('es-AR')}</time>
              {item.rpe !== null && ` · reportaste RPE ${item.rpe}/10`}
            </span>
          </div>
        </li>
      ))}
    </ul>
  );
}
