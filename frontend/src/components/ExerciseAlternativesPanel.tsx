import { useRef, useState } from 'react';
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
  const [busy, setBusy] = useState(false);
  const trigger = useRef<HTMLButtonElement>(null);

  const toggle = async () => {
    if (open) return setOpen(false);
    setError('');
    setBusy(true);
    try {
      setResult(await getAlternatives(exerciseId));
      setOpen(true);
    } catch {
      setError('No pudimos cargar las alternativas. Probá de nuevo.');
    } finally {
      setBusy(false);
    }
  };

  const save = async (alternative: ExerciseAlternative | null, skip = false) => {
    setError('');
    setBusy(true);
    try {
      await saveReplacement({ day_name: dayName, original_exercise_id: exerciseId, replacement_exercise_id: alternative?.exercise_id ?? null });
      // con variante segura, lo que el alumno hace (y registra) es la variante
      onChosen(alternative?.variant ? { ...alternative, exercise_id: alternative.variant.exercise_id, name: alternative.variant.name, variant: null } : alternative);
      setOpen(false);
      if (skip) onSkip();
      else trigger.current?.focus(); // el panel se cierra: devolver el foco al disparador
    } catch {
      setError('No pudimos registrar el reemplazo. Probá de nuevo.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="exercise-alternatives">
      {chosen && <p role="status"><strong>Hoy hacés: {chosen.name}</strong> (solo en esta sesión)</p>}
      <button ref={trigger} className="plan-cancel" type="button" aria-expanded={open} aria-busy={busy} disabled={busy} onClick={toggle}>
        {busy && !open ? 'Cargando alternativas…' : 'Sustituir ejercicio'}
      </button>
      {error && <p role="alert">{error}</p>}
      {open && result && (
        <div>
          {result.alternatives.length === 0 ? (
            <p role="status">No hay alternativas disponibles para este ejercicio. Podés saltearlo; tu entrenador lo verá al revisar la sesión.</p>
          ) : (
            <ul>
              {result.alternatives.map((alt) => (
                <li key={alt.exercise_id}>
                  <button type="button" className="plan-cancel" aria-pressed={chosen?.exercise_id === (alt.variant?.exercise_id ?? alt.exercise_id)} disabled={busy} onClick={() => save(alt)}>
                    {alt.name} · {alt.equipment_needed}
                    {alt.variant && <small> Se registra su variante segura: {alt.variant.name}</small>}
                  </button>
                </li>
              ))}
            </ul>
          )}
          {chosen && <button type="button" className="plan-cancel" disabled={busy} onClick={() => save(null)}>Volver al ejercicio original</button>}
          {result.can_skip && <button type="button" className="plan-cancel" disabled={busy} onClick={() => save(null, true)}>Saltear ejercicio</button>}
        </div>
      )}
    </div>
  );
}
