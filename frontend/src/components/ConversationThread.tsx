import { CheckCheck, CornerDownRight, Pin, Send, Stethoscope, X } from 'lucide-react';
import { type FormEvent, type KeyboardEvent, useCallback, useEffect, useRef, useState } from 'react';
import { getApiErrorInfo } from '../services/errorMessage';
import { getConversation, markConversationRead, sendMessage } from '../services/conversationService';
import type { ConversationDetail, MessageView } from '../types/conversation';
import { MESSAGE_MAX_LENGTH, POLL_INTERVAL_MS, formatMessageTime, queryContext } from '../utils/messageFormat';

interface ConversationThreadProps {
  relationshipId: string;
  /** Avisa a la lista que cambió el último mensaje o los no leídos. */
  onActivity?: () => void;
}

/** US-21: historial completo, envío y lectura. US-62: tarjetas de consulta y respuesta del entrenador. */
export function ConversationThread({ relationshipId, onActivity }: ConversationThreadProps) {
  const [detail, setDetail] = useState<ConversationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [body, setBody] = useState('');
  const [replyTo, setReplyTo] = useState<MessageView | null>(null);
  const [pin, setPin] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState('');
  const logRef = useRef<HTMLOListElement>(null);
  const lastIdRef = useRef<string | null>(null);
  const requestRef = useRef(0);
  const onActivityRef = useRef(onActivity);
  onActivityRef.current = onActivity;

  const load = useCallback(async (initial = false) => {
    const requestId = ++requestRef.current;
    if (initial) setLoading(true);
    try {
      const loaded = await getConversation(relationshipId);
      if (requestRef.current !== requestId) return;
      setDetail(loaded);
      setError('');
      if (loaded.conversation.unread_count > 0) {
        await markConversationRead(relationshipId);
        onActivityRef.current?.();
      }
    } catch (requestError) {
      if (requestRef.current === requestId && initial) {
        setError(getApiErrorInfo(requestError, 'No pudimos cargar la conversación.').message);
      }
    } finally {
      if (requestRef.current === requestId && initial) setLoading(false);
    }
  }, [relationshipId]);

  useEffect(() => {
    setDetail(null);
    setReplyTo(null);
    setPin(false);
    setBody('');
    lastIdRef.current = null;
    void load(true);
    // Sin WebSockets: actualización cada 10 s y al volver a la pestaña.
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void load();
    }, POLL_INTERVAL_MS);
    function handleVisibility() {
      if (document.visibilityState === 'visible') void load();
    }
    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [load]);

  const messages = detail?.messages ?? [];
  const lastId = messages.length ? messages[messages.length - 1].id : null;
  // Baja al último mensaje cuando llega uno nuevo. Depende de `loading` porque en la carga
  // inicial el historial se dibuja recién cuando termina (antes no hay contenedor).
  useEffect(() => {
    if (!lastId || !logRef.current || lastId === lastIdRef.current) return;
    logRef.current.scrollTop = logRef.current.scrollHeight;
    lastIdRef.current = lastId;
  }, [lastId, loading]);

  const isTrainer = detail?.conversation.counterpart_role === 'STUDENT';
  const queriesById = new Map(messages.filter((m) => m.kind === 'TECHNICAL_QUERY').map((m) => [m.id, m]));

  async function handleSubmit(event?: FormEvent) {
    event?.preventDefault();
    const text = body.trim();
    if (sending) return;
    if (!text || text.length > MESSAGE_MAX_LENGTH) {
      setSendError('Escribí un mensaje (hasta 2000 caracteres).');
      return;
    }
    setSending(true);
    setSendError('');
    try {
      await sendMessage(relationshipId, {
        body: text,
        reply_to_message_id: replyTo?.id ?? null,
        pin_as_technical_note: Boolean(replyTo) && pin,
      });
      setBody('');
      setReplyTo(null);
      setPin(false);
      await load();
      onActivityRef.current?.();
    } catch (requestError) {
      setSendError(getApiErrorInfo(requestError, 'No pudimos enviar el mensaje. Intentá nuevamente.').message);
    } finally {
      setSending(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void handleSubmit();
    }
  }

  if (loading) return <p role="status" className="conversation__status">Cargando conversación…</p>;
  if (error) return <p className="form-alert" role="alert">{error}</p>;
  if (!detail) return null;

  const { conversation } = detail;

  return (
    <section className="conversation" aria-labelledby="conversation-title">
      <header className="conversation__header">
        <h2 id="conversation-title">{conversation.counterpart_name}</h2>
        <p>{conversation.counterpart_role === 'TRAINER' ? 'Tu entrenador' : 'Tu alumno'}{conversation.plan_title ? ` · ${conversation.plan_title}` : ''}</p>
      </header>

      <ol ref={logRef} className="conversation__log" role="log" aria-live="polite" aria-label={`Mensajes con ${conversation.counterpart_name}`}>
        {messages.length === 0 && (
          <li className="conversation__empty">Todavía no hay mensajes. Escribí el primero para coordinar con {conversation.counterpart_name}.</li>
        )}
        {messages.map((message) => {
          const query = message.reply_to_message_id ? queriesById.get(message.reply_to_message_id) : undefined;
          const isQuery = message.kind === 'TECHNICAL_QUERY';
          return (
            <li key={message.id} className={`message${message.is_mine ? ' message--mine' : ''}${isQuery ? ' message--query' : ''}`}>
              <div className="message__bubble">
                {isQuery && (
                  <p className="message__card">
                    <Stethoscope size={15} aria-hidden="true" />
                    <span><strong>Consulta técnica:</strong> {queryContext(message.exercise, message.set_number)}</span>
                    <span className={`message__chip${message.is_answered ? ' message__chip--done' : ''}`}>
                      {message.is_answered ? 'Respondida' : 'Pendiente'}
                    </span>
                  </p>
                )}
                {message.reply_to_message_id && (
                  <p className="message__context">
                    <CornerDownRight size={14} aria-hidden="true" />
                    Respuesta a la consulta sobre {query?.exercise?.name ?? 'un ejercicio'}
                  </p>
                )}
                <p className="message__body">{message.body}</p>
                {message.technical_note && (
                  <p className="message__note">
                    <Pin size={14} aria-hidden="true" />
                    {message.technical_note.acknowledged_at ? 'Nota técnica · el alumno la confirmó' : 'Nota técnica fijada para la próxima sesión'}
                  </p>
                )}
                <p className="message__meta">
                  {!message.is_mine && <span>{message.sender_name} · </span>}
                  <time dateTime={message.created_at}>{formatMessageTime(message.created_at)}</time>
                  {message.is_mine && message.read_at && (
                    <span className="message__read"> · <CheckCheck size={14} aria-hidden="true" /> Leído</span>
                  )}
                </p>
                {isTrainer && isQuery && conversation.can_send && (
                  <button
                    type="button"
                    className="message__reply-btn"
                    onClick={() => { setReplyTo(message); setPin(false); }}
                  >
                    <CornerDownRight size={15} aria-hidden="true" /> Responder
                  </button>
                )}
              </div>
            </li>
          );
        })}
      </ol>

      {conversation.can_send ? (
        <form className="conversation__composer" onSubmit={handleSubmit} noValidate>
          {replyTo && (
            <div className="conversation__replying">
              <p>
                Respondiendo la consulta sobre <strong>{queryContext(replyTo.exercise, replyTo.set_number)}</strong>
              </p>
              <label className="conversation__pin">
                <input type="checkbox" checked={pin} onChange={(event) => setPin(event.target.checked)} />
                Fijar como nota técnica (el alumno la verá al iniciar el ejercicio en su próxima sesión)
              </label>
              <button type="button" className="conversation__cancel-reply" onClick={() => setReplyTo(null)} aria-label="Cancelar respuesta">
                <X size={16} aria-hidden="true" />
              </button>
            </div>
          )}
          <label htmlFor={`composer-${relationshipId}`} className="visually-hidden">Mensaje</label>
          <div className="conversation__input-row">
            <textarea
              id={`composer-${relationshipId}`}
              value={body}
              onChange={(event) => setBody(event.target.value)}
              onKeyDown={handleKeyDown}
              rows={2}
              maxLength={MESSAGE_MAX_LENGTH}
              placeholder={replyTo ? 'Escribí tu respuesta…' : `Escribile a ${conversation.counterpart_name}…`}
              disabled={sending}
              aria-invalid={Boolean(sendError)}
              aria-describedby={`composer-hint-${relationshipId}`}
            />
            <button type="submit" className="conversation__send" disabled={sending || !body.trim()} aria-label="Enviar mensaje">
              <Send size={18} aria-hidden="true" />
            </button>
          </div>
          <p id={`composer-hint-${relationshipId}`} className="conversation__hint">
            {sendError ? <span className="field-error" role="alert">{sendError}</span> : 'Ctrl + Enter para enviar'}
            <span>{body.length}/{MESSAGE_MAX_LENGTH}</span>
          </p>
        </form>
      ) : (
        <p className="conversation__readonly" role="status">
          El vínculo de entrenamiento terminó: el historial queda disponible en modo lectura y no se pueden enviar mensajes.
        </p>
      )}
    </section>
  );
}
