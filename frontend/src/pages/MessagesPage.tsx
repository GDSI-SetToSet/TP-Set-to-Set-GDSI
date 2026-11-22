import { ArrowLeft, MessageSquare } from 'lucide-react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ConversationThread } from '../components/ConversationThread';
import { USER_ROLES } from '../constants/auth';
import { ROUTES } from '../constants/routes';
import { useAuth } from '../context/AuthContext';
import { listConversations } from '../services/conversationService';
import type { ConversationSummary } from '../types/conversation';
import { POLL_INTERVAL_MS, formatMessageTime } from '../utils/messageFormat';
import '../styles/messages.css';

/** US-21: lista de conversaciones (una por vínculo) y el hilo seleccionado (`?relationshipId=`). */
export function MessagesPage() {
  const { user } = useAuth();
  const isTrainer = user?.role === USER_ROLES.trainer;
  const [searchParams, setSearchParams] = useSearchParams();
  const selectedId = searchParams.get('relationshipId');
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const requestRef = useRef(0);

  const loadList = useCallback(async () => {
    const requestId = ++requestRef.current;
    try {
      const loaded = await listConversations();
      if (requestRef.current === requestId) {
        setConversations(loaded);
        setError('');
      }
    } catch {
      if (requestRef.current === requestId) setError('No pudimos cargar tus conversaciones. Intentá nuevamente.');
    } finally {
      if (requestRef.current === requestId) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadList();
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void loadList();
    }, POLL_INTERVAL_MS);
    return () => window.clearInterval(timer);
  }, [loadList]);

  const homeRoute = isTrainer ? ROUTES.trainerHome : ROUTES.studentHome;

  return (
    <main className={`profile-shell${isTrainer ? ' profile-shell--trainer' : ''}`}>
      <header className="profile-header">
        <Link to={homeRoute} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>

      <section className={`profile-card messages${selectedId ? ' messages--thread-open' : ''}`}>
        <div className="profile-heading messages__heading">
          <span>COMUNICACIÓN</span>
          <h1>Mensajes</h1>
          <p>
            {isTrainer
              ? 'Coordiná cambios y respondé dudas de tus alumnos sin salir de la app.'
              : 'Coordiná cambios y resolvé dudas con tus entrenadores sin salir de la app.'}
          </p>
        </div>

        <div className="messages__layout">
          <nav className="messages__list" aria-label="Conversaciones">
            {loading ? (
              <p role="status">Cargando conversaciones…</p>
            ) : error ? (
              <p className="form-alert" role="alert">{error}</p>
            ) : conversations.length === 0 ? (
              <p className="plan-empty">
                {isTrainer ? 'Todavía no tenés alumnos activos.' : 'Todavía no tenés entrenadores activos.'}
              </p>
            ) : (
              <ul>
                {conversations.map((conversation) => {
                  const selected = conversation.relationship_id === selectedId;
                  return (
                    <li key={conversation.relationship_id}>
                      <button
                        type="button"
                        className={`messages__item${selected ? ' is-selected' : ''}`}
                        aria-current={selected ? 'true' : undefined}
                        onClick={() => setSearchParams({ relationshipId: conversation.relationship_id })}
                      >
                        <span className="messages__item-top">
                          <strong>{conversation.counterpart_name}</strong>
                          {conversation.last_message && (
                            <time dateTime={conversation.last_message.created_at}>
                              {formatMessageTime(conversation.last_message.created_at)}
                            </time>
                          )}
                        </span>
                        <span className="messages__preview">
                          {conversation.last_message
                            ? `${conversation.last_message.is_mine ? 'Vos: ' : ''}${conversation.last_message.kind === 'TECHNICAL_QUERY' ? 'Consulta técnica · ' : ''}${conversation.last_message.body}`
                            : 'Sin mensajes todavía'}
                        </span>
                        <span className="messages__item-bottom">
                          {conversation.status !== 'ACTIVE' && <span className="messages__ended">Vínculo terminado</span>}
                          {conversation.unread_count > 0 && (
                            <span className="messages__unread" aria-label={`${conversation.unread_count} sin leer`}>
                              {conversation.unread_count}
                            </span>
                          )}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </nav>

          <div className="messages__thread">
            {selectedId ? (
              <>
                <button type="button" className="messages__back" onClick={() => setSearchParams({})}>
                  <ArrowLeft size={16} aria-hidden="true" /> Conversaciones
                </button>
                <ConversationThread key={selectedId} relationshipId={selectedId} onActivity={loadList} />
              </>
            ) : (
              <div className="messages__placeholder">
                <MessageSquare size={28} aria-hidden="true" />
                <p>Elegí una conversación para ver los mensajes.</p>
              </div>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
