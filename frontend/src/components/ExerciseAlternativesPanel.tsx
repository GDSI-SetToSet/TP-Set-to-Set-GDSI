import { useState } from 'react';
import { getAlternatives, saveReplacement } from '../services/exerciseAlternativeService';
import type { AlternativesResponse, ExerciseAlternative } from '../types/exerciseAlternative';

interface Props {
  exerciseId: string;
  dayName: string;
  chosen: ExerciseAlternative | null;
  /** null = volver al ejercicio original; la elección vale solo para la sesión en curso. */
  onChosen: (alternative: ExerciseAlternative | null) => void;
  onSkip: () => void;
}

/** US-54: el alumno pide alternativas del mismo grupo muscular y elige una o saltea el ejercicio. */
export function ExerciseAlternativesPanel({ exerciseId, dayName, chosen, onChosen, onSkip }: Props) {
  const [result, setResult] = useState<AlternativesResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState('');

  const toggle = async () => {
    if (open) return setOpen(false);
    setError('');
    try {
      setResult(await getAlternatives(exerciseId));
      setOpen(true);
    } catch {
      setError('No pudimos cargar las alternativas. Probá de nuevo.');
    }
  };

  const save = async (alternative: ExerciseAlternative | null, skip = false) => {
    setError('');
    try {
      await saveReplacement({ day_name: dayName, original_exercise_id: exerciseId, replacement_exercise_id: alternative?.exercise_id ?? null });
      onChosen(alternative);
      setOpen(false);
      if (skip) onSkip();
    } catch {
      setError('No pudimos registrar el reemplazo. Probá de nuevo.');
    }
  };

  return (
    <div className="exercise-alternatives">
      {chosen && <p role="status"><strong>Hoy hacés: {chosen.name}</strong></p>}
      <button className="plan-cancel" type="button" aria-expanded={open} onClick={toggle}>Sustituir ejercicio</button>
      {error && <p role="alert">{error}</p>}
      {open && result && (
        <div>
          {result.alternatives.length === 0 ? (
            <p role="status">No hay alternativas disponibles para este ejercicio. Podés saltearlo; tu entrenador lo verá al revisar la sesión.</p>
          ) : (
            <ul>
              {result.alternatives.map((alt) => (
                <li key={alt.exercise_id}>
                  <button type="button" className="plan-cancel" onClick={() => save(alt)}>
                    {alt.name} · {alt.equipment_needed}{alt.variant ? ` (variante segura: ${alt.variant.name})` : ''}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {chosen && <button type="button" className="plan-cancel" onClick={() => save(null)}>Volver al ejercicio original</button>}
          {result.can_skip && <button type="button" className="plan-cancel" onClick={() => save(null, true)}>Saltear ejercicio</button>}
        </div>
      )}
    </div>
  );
}
