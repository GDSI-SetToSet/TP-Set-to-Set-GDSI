import { ChevronDown, ChevronUp, Pencil } from 'lucide-react';
import { useState } from 'react';
import { RoutineTemplateDetail } from './RoutineTemplateDetail';
import { ROUTINE_INTENSITIES, type RoutineTemplate } from '../types/routineTemplate';

interface RoutineTemplateCardProps {
  template: RoutineTemplate;
  busy?: boolean;
  onEdit?: (template: RoutineTemplate) => void;
}

export function RoutineTemplateCard({ template, busy = false, onEdit }: RoutineTemplateCardProps) {
  const [open, setOpen] = useState(false);

  return (
    <article className="plan-card routine-card">
      <div className="plan-card__top">
        <h3>{template.name}</h3>
        <span className="plan-badge plan-badge--active">{ROUTINE_INTENSITIES[template.intensity]}</span>
      </div>
      {!onEdit && template.trainer_name && <p className="exercise-card__muscle">Por {template.trainer_name}</p>}
      <p className="plan-card__description">{template.duration_weeks} semanas · {template.days.length} días · {template.exercise_count} ejercicios</p>
      {template.has_no_materials_alternative && <p className="routine-card__flag">Apta "Sin materiales"</p>}
      {open && <RoutineTemplateDetail template={template} />}
      <div className="plan-card__actions">
        <button type="button" onClick={() => setOpen((current) => !current)} aria-expanded={open}>
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />} {open ? 'Ocultar' : 'Ver detalle'}
        </button>
        {onEdit && <button type="button" onClick={() => onEdit(template)} disabled={busy}><Pencil size={16} /> Editar</button>}
      </div>
    </article>
  );
}
