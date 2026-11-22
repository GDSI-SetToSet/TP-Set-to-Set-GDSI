import { Medal, MessageCircle } from 'lucide-react';
import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { congratulateAchievement, getTrainerStudentAchievements } from '../services/achievementService';
import { getApiErrorInfo } from '../services/errorMessage';
import { getFieldErrors } from '../services/paymentService';
import type { AchievementItem, AchievementsOverview } from '../types/achievement';
import { formatAchievementDate } from '../utils/achievementFormat';
import '../styles/achievements.css';

const MAX = 300;

function CongratulateForm({ item, onSent }: { item: AchievementItem; onSent: () => void }) {
  const [open, setOpen] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const text = message.trim();
    if (!text || text.length > MAX) {
      setError('Escribí la felicitación (hasta 300 caracteres).');
      return;
    }
    setSending(true);
    setError('');
    try {
      await congratulateAchievement(item.id, text);
      onSent();
    } catch (requestError) {
      setError(getFieldErrors(requestError).message ?? getApiErrorInfo(requestError, 'No pudimos enviar la felicitación.').message);
      setSending(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className="trainer-achievements__open" onClick={() => setOpen(true)}>
        <MessageCircle size={16} aria-hidden="true" /> Felicitar
      </button>
    );
  }
  const id = `congratulation-${item.id}`;
  return (
    <form className="trainer-achievements__form" onSubmit={submit} noValidate>
      <label htmlFor={id}>Tu felicitación (la verá en su próxima sesión)</label>
      <textarea id={id} value={message} onChange={(event) => setMessage(event.target.value)} rows={2} maxLength={MAX}
        disabled={sending} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined} />
      {error && <small className="field-error" id={`${id}-error`} role="alert">{error}</small>}
      <div>
        <button type="submit" className="profile-save" disabled={sending}>{sending ? 'Enviando…' : 'Enviar'}</button>
        <button type="button" className="plan-cancel" onClick={() => setOpen(false)} disabled={sending}>Cancelar</button>
      </div>
    </form>
  );
}

/** US-67 escenario 4: logros del alumno en el detalle del entrenador, con la opción de felicitar. */
export function TrainerAchievements({ studentId }: { studentId: string }) {
  const [overview, setOverview] = useState<AchievementsOverview | null>(null);

  const load = useCallback(() => {
    getTrainerStudentAchievements(studentId).then(setOverview).catch(() => setOverview(null));
  }, [studentId]);

  useEffect(() => {
    setOverview(null);
    load();
  }, [load]);

  if (!overview) return null;
  return (
    <article className="trainer-achievements">
      <h3><Medal size={18} aria-hidden="true" />Logros</h3>
      {overview.unlocked.length === 0 ? (
        <p>Todavía no desbloqueó logros.</p>
      ) : (
        <ul>
          {overview.unlocked.map((item) => (
            <li key={item.id}>
              <div>
                <strong>{item.title}</strong>
                <small>Obtenido el {formatAchievementDate(item.unlocked_at)}</small>
                {item.congratulation && <p className="trainer-achievements__sent">Tu felicitación: “{item.congratulation.message}”</p>}
              </div>
              {!item.congratulation && <CongratulateForm item={item} onSent={load} />}
            </li>
          ))}
        </ul>
      )}
      {overview.locked.length > 0 && (
        <p className="trainer-achievements__locked">Faltan: {overview.locked.map((item) => `${item.title} (${item.current}/${item.target})`).join(', ')}.</p>
      )}
    </article>
  );
}
