import { ChevronDown, ChevronUp, MessageCircleQuestion, Pin } from 'lucide-react';
import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react';
import { getApiErrorInfo } from '../services/errorMessage';
import { createTechnicalQuery, getExerciseQueries } from '../services/conversationService';
import type { ExerciseQueryThread } from '../types/conversation';
import { MESSAGE_MAX_LENGTH, formatMessageTime } from '../utils/messageFormat';
import '../styles/messages.css';

interface ExerciseQueriesPanelProps {
  relationshipId: string;
  exerciseId: string;
  exerciseName: string;
  sets: number;
  sessionId: string | null;
}

/** US-62 escenarios 1 y 4: consultar sobre el ejercicio y ver el historial de consultas y respuestas. */
export function ExerciseQueriesPanel({ relationshipId, exerciseId, exerciseName, sets, sessionId }: ExerciseQueriesPanelProps) {
  const [open, setOpen] = useState(false);
  const [threads, setThreads] = useState<ExerciseQueryThread[] | null>(null);
  const [loadError, setLoadError] = useState('');
  const [body, setBody] = useState('');
  const [setNumber, setSetNumber] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);
  const requestSeqRef = useRef(0);

  useEffect(() => {
    requestSeqRef.current += 1;
    setThreads(null);
    setLoadError('');
    setSent(false);
    setError('');
  }, [relationshipId, exerciseId]);

  const load = useCallback(async () => {
    const seq = ++requestSeqRef.current;
    try {
      const loaded = await getExerciseQueries(relationshipId, exerciseId);
      if (requestSeqRef.current === seq) {
        setThreads(loaded);
        setLoadError('');
      }
    } catch {
      if (requestSeqRef.current === seq) {
        setLoadError('No pudimos cargar las consultas de este ejercicio.');
      }
    }
  }, [relationshipId, exerciseId]);

  useEffect(() => {
    if (open && threads === null) void load();
  }, [open, threads, load]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = body.trim();
    if (!text || text.length > MESSAGE_MAX_LENGTH) {
      setError('Escribí tu consulta (hasta 2000 caracteres).');
      return;
    }
    setSending(true);
    setError('');
    try {
      await createTechnicalQuery(relationshipId, {
        exercise_id: exerciseId,
        body: text,
        session_id: sessionId,
        set_number: setNumber ? Number(setNumber) : null,
      });
      setBody('');
      setSetNumber('');
      setSent(true);
      await load();
    } catch (requestError) {
      setError(getApiErrorInfo(requestError, 'No pudimos enviar la consulta. Intentá nuevamente.').message);
    } finally {
      setSending(false);
    }
  }

  const panelId = `exercise-queries-${exerciseId}`;
  const count = threads?.length ?? 0;
  return (
    <div className="exercise-queries">
      <button
        type="button"
        className="exercise-queries__toggle"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        <MessageCircleQuestion size={16} aria-hidden="true" />
        Consultar a mi entrenador{threads && count > 0 ? ` (${count})` : ''}
        {open ? <ChevronUp size={16} aria-hidden="true" /> : <ChevronDown size={16} aria-hidden="true" />}
      </button>
      {open && (
        <div id={panelId} className="exercise-queries__panel">
          {loadError && <p className="form-alert" role="alert">{loadError}</p>}
          {threads && threads.length > 0 && (
            <ol className="exercise-queries__history" aria-label={`Consultas sobre ${exerciseName}`}>
              {threads.map((thread) => (
                <li key={thread.query.id}>
                  <p className="exercise-queries__question">
                    <strong>Vos</strong>
                    {thread.query.set_number ? ` · serie ${thread.query.set_number}` : ''} ·{' '}
                    <time dateTime={thread.query.created_at}>{formatMessageTime(thread.query.created_at)}</time>
                  </p>
                  <p>{thread.query.body}</p>
                  {thread.replies.length === 0 ? (
                    <p className="exercise-queries__pending">Esperando respuesta de tu entrenador.</p>
                  ) : (
                    thread.replies.map((replyMessage) => (
                      <div key={replyMessage.id} className="exercise-queries__reply">
                        <p className="exercise-queries__question">
                          <strong>{replyMessage.sender_name}</strong> ·{' '}
                          <time dateTime={replyMessage.created_at}>{formatMessageTime(replyMessage.created_at)}</time>
                          {replyMessage.technical_note && (
                            <span className="message__chip message__chip--done"><Pin size={12} aria-hidden="true" /> Nota técnica</span>
                          )}
                        </p>
                        <p>{replyMessage.body}</p>
                      </div>
                    ))
                  )}
                </li>
              ))}
            </ol>
          )}
          {threads && threads.length === 0 && <p className="exercise-queries__empty">Todavía no hiciste consultas sobre este ejercicio.</p>}

          <form className="exercise-queries__form" onSubmit={handleSubmit} noValidate>
            <label htmlFor={`${panelId}-body`}>Tu duda o comentario sobre {exerciseName}</label>
            <textarea
              id={`${panelId}-body`}
              value={body}
              onChange={(event) => { setBody(event.target.value); setSent(false); }}
              rows={3}
              maxLength={MESSAGE_MAX_LENGTH}
              placeholder="Por ejemplo: siento la zona lumbar en la bajada, ¿lo estoy haciendo bien?"
              disabled={sending}
              aria-invalid={Boolean(error)}
              aria-describedby={error ? `${panelId}-error` : undefined}
            />
            {error && <small className="field-error" id={`${panelId}-error`} role="alert">{error}</small>}
            <label htmlFor={`${panelId}-set`}>Serie (opcional)</label>
            <select id={`${panelId}-set`} value={setNumber} onChange={(event) => setSetNumber(event.target.value)} disabled={sending}>
              <option value="">Sin serie en particular</option>
              {Array.from({ length: Math.min(Math.max(sets, 1), 50) }, (_, index) => (
                <option key={index + 1} value={index + 1}>Serie {index + 1}</option>
              ))}
            </select>
            <button type="submit" className="exercise-queries__send" disabled={sending}>
              {sending ? 'Enviando…' : 'Enviar consulta'}
            </button>
            {sent && <p className="exercise-queries__sent" role="status">Consulta enviada. Tu entrenador recibió una notificación.</p>}
          </form>
        </div>
      )}
    </div>
  );
}
