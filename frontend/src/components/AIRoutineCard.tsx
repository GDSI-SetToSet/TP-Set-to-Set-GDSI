import { CheckCircle2, ChevronDown, ChevronUp, RotateCcw, Sparkles, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { RoutineTemplateDetail } from './RoutineTemplateDetail';
import type { TrainerAIRoutine } from '../types/assignedRoutine';

interface AIRoutineCardProps {
  routine: TrainerAIRoutine;
  busy?: boolean;
  onApprove: (routine: TrainerAIRoutine) => void;
  onReassign: (routine: TrainerAIRoutine) => void;
  onDelete: (routine: TrainerAIRoutine) => void;
}

function statusLabel(routine: TrainerAIRoutine): string {
  if (routine.status === 'PENDING_REVIEW') return 'Pendiente de revisión';
  return routine.is_assigned ? 'Asignada' : 'Aprobada';
}

export function AIRoutineCard({ routine, busy = false, onApprove, onReassign, onDelete }: AIRoutineCardProps) {
  const [open, setOpen] = useState(false);
  const isPending = routine.status === 'PENDING_REVIEW';

  return (
    <article className="plan-card routine-card">
      <div className="plan-card__top">
        <h3>{routine.name}</h3>
        <span className={`plan-badge ${isPending ? 'plan-badge--archived' : 'plan-badge--active'}`}>{statusLabel(routine)}</span>
      </div>
      <p className="routine-card__ai"><Sparkles size={15} /> Generada con IA para {routine.student_name}</p>
      <p className="plan-card__description">{routine.duration_weeks} semanas · {routine.days.length} días · {routine.exercise_count} ejercicios</p>
      {open && (
        <>
          {routine.adaptation_summary && <div className="ai-summary-box">{routine.adaptation_summary}</div>}
          <RoutineTemplateDetail template={routine} />
        </>
      )}
      <div className="plan-card__actions">
        <button type="button" onClick={() => setOpen((current) => !current)} aria-expanded={open}>
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />} {open ? 'Ocultar' : 'Ver detalle'}
        </button>
        {isPending && <button type="button" onClick={() => onApprove(routine)} disabled={busy}><CheckCircle2 size={16} /> Aprobar y asignar</button>}
        {!isPending && !routine.is_assigned && <button type="button" onClick={() => onReassign(routine)} disabled={busy}><RotateCcw size={16} /> Volver a asignar</button>}
        <button type="button" onClick={() => onDelete(routine)} disabled={busy}><Trash2 size={16} /> Eliminar</button>
      </div>
    </article>
  );
}
