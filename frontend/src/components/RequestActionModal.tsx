import { type FormEvent, useState } from 'react';

export type RequestActionType = 'accept' | 'reject';

interface RequestActionModalProps {
  action: RequestActionType;
  studentName: string;
  planTitle: string;
  submitting: boolean;
  error: string;
  onConfirm: (message: string | null) => Promise<void>;
  onClose: () => void;
}

export function RequestActionModal({
  action,
  studentName,
  planTitle,
  submitting,
  error,
  onConfirm,
  onClose,
}: RequestActionModalProps) {
  const [text, setText] = useState('');

  const isAccept = action === 'accept';
  const title = isAccept ? 'Aceptar solicitud de entrenamiento' : 'Rechazar solicitud de entrenamiento';
  const subtitle = isAccept
    ? `Vas a vincular a ${studentName} en el paquete "${planTitle}" y ocupar un cupo activo.`
    : `Vas a rechazar la solicitud de ${studentName} para el paquete "${planTitle}".`;
  const label = isAccept
    ? 'Mensaje de bienvenida (opcional)'
    : 'Motivo explicativo del rechazo (opcional)';
  const placeholder = isAccept
    ? '¡Bienvenido/a al equipo! En breve coordinamos tu evaluación inicial…'
    : 'Podés indicarle al alumno el motivo por el cual no podés tomar su solicitud…';

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;
    const trimmed = text.trim();
    await onConfirm(trimmed ? trimmed : null);
  }

  return (
    <div className="request-modal-backdrop" role="dialog" aria-modal="true" aria-labelledby="request-modal-title">
      <div className="request-modal">
        <div className="profile-heading">
          <span>{isAccept ? 'CONFIRMAR ALTA' : 'CONFIRMAR RECHAZO'}</span>
          <h2 id="request-modal-title">{title}</h2>
          <p>{subtitle}</p>
        </div>

        <form className="profile-form request-modal__form" onSubmit={handleSubmit}>
          <label>
            {label}
            <textarea
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={placeholder}
              rows={4}
              maxLength={1000}
              disabled={submitting}
            />
          </label>

          {error && (
            <p className="form-alert" role="alert">
              {error}
            </p>
          )}

          <div className="inbox-card__actions">
            <button
              type="submit"
              className={
                isAccept ? 'profile-save' : 'inbox-action-btn inbox-action-btn--reject'
              }
              disabled={submitting}
            >
              {submitting
                ? isAccept
                  ? 'Aceptando…'
                  : 'Rechazando…'
                : isAccept
                  ? 'Confirmar aceptación'
                  : 'Confirmar rechazo'}
            </button>
            <button
              type="button"
              className="inbox-refresh-btn"
              onClick={onClose}
              disabled={submitting}
            >
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
