import { ChevronDown, ChevronUp, Pencil, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { EXERCISE_CATEGORIES, type Exercise } from '../types/exercise';

interface ExerciseCardProps {
  exercise: Exercise;
  busy: boolean;
  onEdit: (exercise: Exercise) => void;
  onDelete: (exercise: Exercise) => void;
}

export function ExerciseCard({ exercise, busy, onEdit, onDelete }: ExerciseCardProps) {
  const [open, setOpen] = useState(false);

  return (
    <article className="plan-card">
      <div className="plan-card__top">
        <h3>{exercise.name}</h3>
        <span className="plan-badge plan-badge--active">{EXERCISE_CATEGORIES[exercise.category]}</span>
      </div>
      <p className="exercise-card__muscle">{exercise.target_muscle_group}</p>
      {open && (
        <dl className="exercise-card__detail">
          <dt>Descripción</dt>
          <dd>{exercise.description}</dd>
          <dt>Elementos necesarios</dt>
          <dd>{exercise.equipment_needed}</dd>
          <dt>Alternativa "Sin materiales"</dt>
          <dd>{exercise.has_no_materials_alternative ? 'Sí' : 'No'}</dd>
          {exercise.video_url && (
            <>
              <dt>Video demostrativo</dt>
              <dd>
                <iframe
                  className="exercise-video"
                  src={exercise.video_url}
                  title={`Video demostrativo de ${exercise.name}`}
                  loading="lazy"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
                  allowFullScreen
                />
              </dd>
            </>
          )}
        </dl>
      )}
      <div className="plan-card__actions">
        <button type="button" onClick={() => setOpen((current) => !current)} aria-expanded={open}>
          {open ? <ChevronUp size={16} /> : <ChevronDown size={16} />} {open ? 'Ocultar' : 'Ver detalle'}
        </button>
        <button type="button" onClick={() => onEdit(exercise)} disabled={busy}><Pencil size={16} /> Editar</button>
        <button type="button" onClick={() => onDelete(exercise)} disabled={busy}><Trash2 size={16} /> Eliminar</button>
      </div>
    </article>
  );
}
