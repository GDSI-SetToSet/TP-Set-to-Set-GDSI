import { ArrowLeft, MessageSquare, RefreshCw, Stethoscope } from 'lucide-react';
import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getApiErrorInfo } from '../services/errorMessage';
import { getPendingTechnicalQueries, sendMessage } from '../services/conversationService';
import type { MessageView, PendingQueriesGroup } from '../types/conversation';
import { MESSAGE_MAX_LENGTH, formatMessageTime, queryContext } from '../utils/messageFormat';
import '../styles/messages.css';

function QueryReplyForm({ relationshipId, query, onReplied }: { relationshipId: string; query: MessageView; onReplied: () => void }) {
  const [body, setBody] = useState('');
  const [pin, setPin] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const text = body.trim();
    if (!text || text.length > MESSAGE_MAX_LENGTH) {
      setError('Escribí tu respuesta (hasta 2000 caracteres).');
      return;
    }
    setSending(true);
    setError('');
    try {
      await sendMessage(relationshipId, { body: text, reply_to_message_id: query.id, pin_as_technical_note: pin });
      onReplied();
    } catch (requestError) {
      setError(getApiErrorInfo(requestError, 'No pudimos enviar la respuesta. Intentá nuevamente.').message);
      setSending(false);
    }
  }

  const fieldId = `reply-${query.id}`;
  return (
    <form className="query-card__form" onSubmit={handleSubmit} noValidate>
      <label htmlFor={fieldId}>Tu respuesta</label>
      <textarea
        id={fieldId}
        value={body}
        onChange={(event) => setBody(event.target.value)}
        rows={3}
        maxLength={MESSAGE_MAX_LENGTH}
        disabled={sending}
        aria-invalid={Boolean(error)}
        aria-describedby={error ? `${fieldId}-error` : undefined}
      />
      {error && <small className="field-error" id={`${fieldId}-error`} role="alert">{error}</small>}
      <label className="conversation__pin">
        <input type="checkbox" checked={pin} onChange={(event) => setPin(event.target.checked)} disabled={sending} />
        Fijar como nota técnica (el alumno la verá al iniciar el ejercicio en su próxima sesión)
      </label>
      <button type="submit" className="profile-save" disabled={sending}>
        {sending ? 'Enviando…' : 'Responder'}
      </button>
    </form>
  );
}

/** US-62 escenario 2: consultas técnicas pendientes, agrupadas por alumno. */
export function TrainerTechnicalQueriesPage() {
  const [groups, setGroups] = useState<PendingQueriesGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      setGroups(await getPendingTechnicalQueries());
    } catch {
      setError('No pudimos cargar las consultas técnicas. Intentá nuevamente.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const total = groups.reduce((sum, group) => sum + group.queries.length, 0);

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>
      <section className="profile-card technical-queries">
        <div className="profile-heading">
          <span>SEGUIMIENTO</span>
          <h1>Consultas técnicas</h1>
          <p>Dudas de tus alumnos sobre ejercicios de su rutina que todavía no respondiste.</p>
        </div>
        <div className="technical-queries__toolbar">
          <p role="status">{loading ? '' : total === 1 ? '1 consulta pendiente' : `${total} consultas pendientes`}</p>
          <button type="button" className="inbox-refresh-btn" onClick={() => void load()} disabled={loading}>
            <RefreshCw size={16} aria-hidden="true" /> Actualizar
          </button>
        </div>
        {notice && <p className="form-alert form-alert--success" role="status">{notice}</p>}
        {loading ? (
          <p role="status">Cargando consultas…</p>
        ) : error ? (
          <p className="form-alert" role="alert">{error}</p>
        ) : groups.length === 0 ? (
          <p className="plan-empty">No tenés consultas técnicas pendientes.</p>
        ) : (
          groups.map((group) => (
            <section key={group.relationship_id} className="technical-queries__group" aria-labelledby={`group-${group.relationship_id}`}>
              <div className="technical-queries__group-header">
                <h2 id={`group-${group.relationship_id}`}>{group.student_name}</h2>
                <Link
                  className="technical-queries__chat-link"
                  to={`${ROUTES.trainerMessages}?relationshipId=${encodeURIComponent(group.relationship_id)}`}
                >
                  <MessageSquare size={16} aria-hidden="true" /> Ver conversación
                </Link>
              </div>
              <ul className="technical-queries__list">
                {group.queries.map((query) => (
                  <li key={query.id} className="query-card">
                    <p className="query-card__context">
                      <Stethoscope size={15} aria-hidden="true" />
                      <strong>{queryContext(query.exercise, query.set_number)}</strong>
                      <time dateTime={query.created_at}>{formatMessageTime(query.created_at)}</time>
                    </p>
                    <p className="query-card__body">{query.body}</p>
                    <QueryReplyForm
                      relationshipId={group.relationship_id}
                      query={query}
                      onReplied={() => {
                        setNotice(`Respuesta enviada a ${group.student_name}.`);
                        void load();
                      }}
                    />
                  </li>
                ))}
              </ul>
            </section>
          ))
        )}
      </section>
    </main>
  );
}
