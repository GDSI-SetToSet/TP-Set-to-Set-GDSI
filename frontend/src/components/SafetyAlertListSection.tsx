import { useEffect, useRef, useState } from 'react';
import { CheckCircle2, ShieldAlert } from 'lucide-react';
import { reviewSafetyAlert } from '../services/safetyAlertService';
import type { SafetyAlertAction, SafetyAlertView } from '../types/safetyAlert';
import {
  SAFETY_ALERT_ACTION_OPTIONS,
  executeAlertReviewSubmit,
  formatSafetyAlertSummary,
  getReviewSubmitButtonState,
} from '../utils/safetyAlerts.mjs';

interface SafetyAlertListSectionProps {
  studentName: string;
  alerts: SafetyAlertView[];
  loading: boolean;
  error: string;
  onRetry: () => void;
  onReviewed: (updatedAlert: SafetyAlertView) => void;
  highlightedAlertId?: string | null;
}

export function SafetyAlertListSection({
  studentName,
  alerts,
  loading,
  error,
  onRetry,
  onReviewed,
  highlightedAlertId,
}: SafetyAlertListSectionProps) {
  const [selectedActions, setSelectedActions] = useState<Record<string, SafetyAlertAction | ''>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  const [submitErrorByAlert, setSubmitErrorByAlert] = useState<Record<string, string>>({});
  const mountedRef = useRef(true);
  const inFlightRef = useRef(false);

  useEffect(() => {
    mountedRef.current = true;
    inFlightRef.current = false;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  async function handleReview(alert: SafetyAlertView) {
    const actionTaken = selectedActions[alert.id] ?? '';
    await executeAlertReviewSubmit({
      alertId: alert.id,
      actionTaken,
      trainerNote: notes[alert.id] ?? '',
      inFlightGuard: inFlightRef,
      isMounted: () => mountedRef.current,
      reviewAlert: reviewSafetyAlert,
      setSubmittingId,
      clearAlertError: (alertId) => setSubmitErrorByAlert((current) => ({ ...current, [alertId]: '' })),
      setAlertError: (alertId, message) => setSubmitErrorByAlert((current) => ({
        ...current,
        [alertId]: message,
      })),
      onReviewed,
      onSuccessCleanup: (alertId) => {
        setSelectedActions((current) => {
          const next = { ...current };
          delete next[alertId];
          return next;
        });
        setNotes((current) => {
          const next = { ...current };
          delete next[alertId];
          return next;
        });
      },
    });
  }

  return (
    <section
      className="safety-alerts-panel"
      aria-label={`Alertas de seguridad de ${studentName}`}
    >
      <div className="safety-alerts-panel__heading">
        <strong>
          <ShieldAlert size={16} aria-hidden="true" />
          Alertas de seguridad
        </strong>
        {loading && <span>Cargando alertas…</span>}
      </div>

      {error ? (
        <div className="form-alert" role="alert">
          <p>{error}</p>
          <button type="button" className="safety-alerts-panel__retry" onClick={onRetry}>
            Reintentar
          </button>
        </div>
      ) : !loading && alerts.length === 0 ? (
        <p className="plan-empty routine-assignment__empty">
          No hay alertas de seguridad registradas para este alumno.
        </p>
      ) : (
        <ul className="safety-alerts-panel__list">
          {alerts.map((alert) => {
            const summary = formatSafetyAlertSummary(alert);
            const isHighlighted = alert.id === highlightedAlertId;
            const selectedAction = selectedActions[alert.id] ?? '';
            const draftNote = notes[alert.id] ?? '';
            const submitError = submitErrorByAlert[alert.id] ?? '';
            const isPending = alert.status === 'PENDING';

            return (
              <li
                key={alert.id}
                id={`safety-alert-${alert.id}`}
                className={`safety-alerts-panel__item safety-alerts-panel__item--${alert.status.toLowerCase()}${isHighlighted ? ' safety-alerts-panel__item--highlighted' : ''}`}
              >
                <div className="safety-alerts-panel__meta">
                  <span className={`safety-alerts-panel__type safety-alerts-panel__type--${alert.alert_type.toLowerCase()}`}>
                    {summary.typeLabel}
                  </span>
                  <span className={`safety-alerts-panel__status safety-alerts-panel__status--${alert.status.toLowerCase()}`}>
                    {summary.statusLabel}
                  </span>
                  <time dateTime={alert.created_at}>
                    {new Intl.DateTimeFormat('es-AR', {
                      dateStyle: 'short',
                      timeStyle: 'short',
                    }).format(new Date(alert.created_at))}
                  </time>
                </div>

                {summary.detailText && (
                  <p className="safety-alerts-panel__detail">{summary.detailText}</p>
                )}

                {isPending ? (
                  <div className="safety-alerts-panel__review-box">
                    <fieldset className="safety-alerts-panel__actions">
                      <legend>¿Qué acción tomaste?</legend>
                      <div className="safety-alerts-panel__action-options">
                        {SAFETY_ALERT_ACTION_OPTIONS.map((option) => (
                          <label
                            key={option.value}
                            className={`safety-alerts-panel__option${selectedAction === option.value ? ' is-selected' : ''}`}
                          >
                            <input
                              type="radio"
                              name={`safety-alert-action-${alert.id}`}
                              value={option.value}
                              checked={selectedAction === option.value}
                              onChange={() => setSelectedActions((current) => ({
                                ...current,
                                [alert.id]: option.value,
                              }))}
                            />
                            <span>{option.label}</span>
                          </label>
                        ))}
                      </div>
                    </fieldset>

                    <label className="safety-alerts-panel__note">
                      <span>Nota de seguimiento (opcional)</span>
                      <textarea
                        rows={2}
                        maxLength={500}
                        value={draftNote}
                        onChange={(event) => setNotes((current) => ({
                          ...current,
                          [alert.id]: event.target.value,
                        }))}
                        placeholder="Ej: Redujimos cargas esta semana o ajustamos el reemplazo."
                      />
                      <span className="safety-alerts-panel__counter">{draftNote.length} / 500</span>
                    </label>

                    {alert.alert_type === 'PAIN' && (
                      <p className="safety-alerts-panel__hint">
                        El alumno verá la confirmación de esta revisión al iniciar su próxima sesión.
                      </p>
                    )}

                    {submitError && (
                      <p className="form-alert" role="alert">{submitError}</p>
                    )}

                    {(() => {
                      const submitButtonState = getReviewSubmitButtonState(alert.id, selectedAction, submittingId);
                      return (
                        <button
                          type="button"
                          className="safety-alerts-panel__submit"
                          disabled={submitButtonState.disabled}
                          onClick={() => void handleReview(alert)}
                        >
                          {submitButtonState.label}
                        </button>
                      );
                    })()}
                  </div>
                ) : (
                  <div className="safety-alerts-panel__reviewed-summary">
                    <p>
                      <CheckCircle2 size={15} aria-hidden="true" />
                      <strong>Acción tomada:</strong> {summary.actionLabel}
                    </p>
                    {summary.note && <p className="safety-alerts-panel__reviewed-note">{summary.note}</p>}
                    {alert.alert_type === 'PAIN' && (
                      <span className="safety-alerts-panel__seen-state">
                        {alert.student_seen_at
                          ? 'Vista por el alumno en su sesión.'
                          : 'Pendiente de visualización en la próxima sesión del alumno.'}
                      </span>
                    )}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
