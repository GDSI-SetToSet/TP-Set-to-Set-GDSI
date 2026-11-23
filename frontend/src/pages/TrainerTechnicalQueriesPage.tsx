import { ArrowLeft, MessageSquare, Pin, RefreshCw, Stethoscope } from 'lucide-react';
import { type FormEvent, useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getApiErrorInfo } from '../services/errorMessage';
import {
  getPendingTechnicalQueries,
  getTechnicalQueriesHistory,
  sendMessage,
} from '../services/conversationService';
import type {
  MessageView,
  PendingQueriesGroup,
  TrainerQueryHistoryGroup,
} from '../types/conversation';
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

/** US-62 escenarios 2 y 4: consultas técnicas pendientes e historial por ejercicio, agrupadas por alumno. */
export function TrainerTechnicalQueriesPage() {
  const [activeTab, setActiveTab] = useState<'pending' | 'history'>('pending');
  const [groups, setGroups] = useState<PendingQueriesGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [historyGroups, setHistoryGroups] = useState<TrainerQueryHistoryGroup[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyError, setHistoryError] = useState('');
  const [notice, setNotice] = useState('');

  const loadPending = useCallback(async () => {
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

  const loadHistory = useCallback(async () => {
    setHistoryLoading(true);
    setHistoryError('');
    try {
      setHistoryGroups(await getTechnicalQueriesHistory());
      setHistoryLoaded(true);
    } catch {
      setHistoryError('No pudimos cargar el historial de consultas. Intentá nuevamente.');
    } finally {
      setHistoryLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadPending();
  }, [loadPending]);

  useEffect(() => {
    if (activeTab === 'history' && !historyLoaded) {
      void loadHistory();
    }
  }, [activeTab, historyLoaded, loadHistory]);

  const totalPending = groups.reduce((sum, group) => sum + group.queries.length, 0);
  const totalThreads = historyGroups.reduce((sum, group) => sum + group.threads.length, 0);
  const currentBusy = activeTab === 'pending' ? loading : historyLoading;

  return (
    <main className="profile-shell profile-shell--trainer">
      <header className="profile-header">
        <Link to={ROUTES.trainerHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>
      <section className="profile-card technical-queries">
        <div className="profile-heading">
          <span>SEGUIMIENTO</span>
          <h1>Consultas técnicas</h1>
          <p>Dudas de tus alumnos sobre ejercicios de su rutina e historial de consultas y respuestas.</p>
        </div>

        <div className="technical-queries__tabs" role="tablist" aria-label="Vista de consultas técnicas">
          <button
            type="button"
            role="tab"
            id="tab-queries-pending"
            aria-selected={activeTab === 'pending'}
            className={`technical-queries__tab${activeTab === 'pending' ? ' is-active' : ''}`}
            onClick={() => setActiveTab('pending')}
          >
            Pendientes ({totalPending})
          </button>
          <button
            type="button"
            role="tab"
            id="tab-queries-history"
            aria-selected={activeTab === 'history'}
            className={`technical-queries__tab${activeTab === 'history' ? ' is-active' : ''}`}
            onClick={() => setActiveTab('history')}
          >
            Historial{historyLoaded ? ` (${totalThreads})` : ''}
          </button>
        </div>

        <div className="technical-queries__toolbar">
          <p role="status">
            {currentBusy
              ? ''
              : activeTab === 'pending'
                ? (totalPending === 1 ? '1 consulta pendiente' : `${totalPending} consultas pendientes`)
                : (totalThreads === 1 ? '1 consulta en el historial' : `${totalThreads} consultas en el historial`)}
          </p>
          <button
            type="button"
            className="inbox-refresh-btn"
            onClick={() => {
              if (activeTab === 'pending') {
                void loadPending();
              } else {
                void loadHistory();
              }
            }}
            disabled={currentBusy}
          >
            <RefreshCw size={16} aria-hidden="true" /> Actualizar
          </button>
        </div>

        {notice && <p className="form-alert form-alert--success" role="status">{notice}</p>}

        {activeTab === 'pending' ? (
          loading ? (
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
                          void loadPending();
                          if (historyLoaded) void loadHistory();
                        }}
                      />
                    </li>
                  ))}
                </ul>
              </section>
            ))
          )
        ) : historyLoading ? (
          <p role="status">Cargando historial…</p>
        ) : historyError ? (
          <p className="form-alert" role="alert">{historyError}</p>
        ) : historyGroups.length === 0 ? (
          <p className="plan-empty">Todavía no hay consultas técnicas registradas.</p>
        ) : (
          historyGroups.map((group) => (
            <section key={group.relationship_id} className="technical-queries__group" aria-labelledby={`history-group-${group.relationship_id}`}>
              <div className="technical-queries__group-header">
                <h2 id={`history-group-${group.relationship_id}`}>{group.student_name}</h2>
                <Link
                  className="technical-queries__chat-link"
                  to={`${ROUTES.trainerMessages}?relationshipId=${encodeURIComponent(group.relationship_id)}`}
                >
                  <MessageSquare size={16} aria-hidden="true" /> Ver conversación
                </Link>
              </div>
              <ul className="technical-queries__list">
                {group.threads.map((thread) => (
                  <li key={thread.query.id} className="query-card">
                    <p className="query-card__context">
                      <Stethoscope size={15} aria-hidden="true" />
                      <strong>{queryContext(thread.query.exercise, thread.query.set_number)}</strong>
                      <time dateTime={thread.query.created_at}>{formatMessageTime(thread.query.created_at)}</time>
                    </p>
                    <p className="query-card__body">{thread.query.body}</p>
                    {thread.replies.length === 0 ? (
                      <p className="exercise-queries__pending">Sin respuesta registrada todavía.</p>
                    ) : (
                      <div className="technical-queries__history-replies">
                        {thread.replies.map((replyMessage) => (
                          <div key={replyMessage.id}>
                            <p className="technical-queries__reply-meta">
                              <strong>{replyMessage.sender_name}</strong>
                              <time dateTime={replyMessage.created_at}>{formatMessageTime(replyMessage.created_at)}</time>
                              {replyMessage.technical_note && (
                                <span className="message__chip message__chip--done">
                                  <Pin size={12} aria-hidden="true" /> Nota técnica
                                </span>
                              )}
                            </p>
                            <p className="query-card__body">{replyMessage.body}</p>
                          </div>
                        ))}
                      </div>
                    )}
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
