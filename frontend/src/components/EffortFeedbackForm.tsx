import { isAxiosError } from 'axios';
import { useId, useState } from 'react';
import { saveSessionEffortFeedback } from '../services/routineTemplateService';
import type { EffortFeedback, EffortFeedbackCategory, WorkoutSession } from '../types/routineTemplate';
import { EFFORT_FEEDBACK_CATEGORIES } from '../types/routineTemplate';
import '../styles/effort-feedback.css';

const COMMENT_MAX_LENGTH = 500;

interface EffortFeedbackFormProps {
  relationshipId: string;
  session: WorkoutSession;
  onSaved: (feedback: EffortFeedback) => void;
}

export function categoryLabel(category: EffortFeedbackCategory): string {
  return EFFORT_FEEDBACK_CATEGORIES.find((item) => item.value === category)?.label ?? category;
}

/** US-64: devolución del entrenador sobre una sesión con RPE reportado (una por sesión, editable). */
export function EffortFeedbackForm({ relationshipId, session, onSaved }: EffortFeedbackFormProps) {
  const existing = session.effort_feedback ?? null;
  const [editing, setEditing] = useState(false);
  const [category, setCategory] = useState<EffortFeedbackCategory | null>(existing?.category ?? null);
  const [comment, setComment] = useState(existing?.comment ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const groupId = useId();

  const startEditing = () => {
    setCategory(existing?.category ?? null);
    setComment(existing?.comment ?? '');
    setError('');
    setEditing(true);
  };

  const save = async () => {
    if (!category) {
      setError('Elegí una devolución antes de guardar.');
      return;
    }
    setSaving(true);
    setError('');
    try {
      const saved = await saveSessionEffortFeedback(relationshipId, session.id, {
        category,
        comment: comment.trim() ? comment.trim() : null,
      });
      onSaved(saved);
      setEditing(false);
    } catch (caught) {
      const detail = isAxiosError(caught) ? (caught.response?.data as { detail?: string } | undefined)?.detail : undefined;
      setError(detail ?? 'No pudimos guardar la devolución. Intentá nuevamente.');
    } finally {
      setSaving(false);
    }
  };

  if (!editing) {
    return (
      <div className="effort-feedback-form effort-feedback-form--summary">
        {existing ? (
          <p>
            <strong>Tu devolución: {categoryLabel(existing.category)}</strong>
            {existing.comment && <span> · {existing.comment}</span>}
            <span className="effort-feedback-form__seen">{existing.seen_at ? 'Vista por el alumno' : 'Sin ver todavía'}</span>
          </p>
        ) : null}
        <button type="button" className="effort-feedback-form__toggle" onClick={startEditing}>
          {existing ? 'Editar devolución' : 'Dejar devolución'}
        </button>
      </div>
    );
  }

  return (
    <div className="effort-feedback-form">
      <fieldset>
        <legend>Devolución sobre el esfuerzo (RPE {session.rpe}/10)</legend>
        <div className="effort-feedback-form__options">
          {EFFORT_FEEDBACK_CATEGORIES.map((option) => (
            <label key={option.value} className={category === option.value ? 'is-selected' : ''}>
              <input
                type="radio"
                name={`effort-${groupId}`}
                value={option.value}
                checked={category === option.value}
                onChange={() => setCategory(option.value)}
              />
              {option.label}
            </label>
          ))}
        </div>
      </fieldset>
      <label className="effort-feedback-form__comment">
        Comentario (opcional)
        <textarea
          value={comment}
          maxLength={COMMENT_MAX_LENGTH}
          rows={3}
          onChange={(event) => setComment(event.target.value)}
          placeholder="Ej.: en el press podés subir 2,5 kg la próxima."
        />
        <span className="effort-feedback-form__counter">{comment.length}/{COMMENT_MAX_LENGTH}</span>
      </label>
      {error && <p className="form-alert" role="alert">{error}</p>}
      <div className="effort-feedback-form__actions">
        <button type="button" className="profile-save" onClick={() => void save()} disabled={saving}>
          {saving ? 'Guardando…' : 'Enviar devolución'}
        </button>
        <button type="button" className="effort-feedback-form__toggle" onClick={() => setEditing(false)} disabled={saving}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
