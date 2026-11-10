import { useState } from 'react';
import { AlertCircle, AlertTriangle, CheckCircle, ShieldCheck, Video, X } from 'lucide-react';
import { BodyMapSelector } from './BodyMapSelector';
import { createBodyMapReport, updateReportAction } from '../services/bodyMapReportService';
import type { BodyMapReportResponse, ReportZoneInput } from '../types/bodyMapReport';
import { getVideoEmbedUrl } from '../utils/videoUrl';
import '../styles/body-map.css';

interface Props {
  exerciseId: string;
  exerciseName: string;
  sessionId: string | null;
  isOpen: boolean;
  onClose: () => void;
  onAcceptVariant: (variant: { id: string; name: string }) => void;
  onSkipExercise: () => void;
}

export function InExercisePainReportModal({
  exerciseId,
  exerciseName,
  sessionId,
  isOpen,
  onClose,
  onAcceptVariant,
  onSkipExercise,
}: Props) {
  const [selectedZones, setSelectedZones] = useState<ReportZoneInput[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState('');
  const [reportResult, setReportResult] = useState<BodyMapReportResponse | null>(null);

  if (!isOpen) return null;

  const handleConfirmReport = async () => {
    if (selectedZones.length === 0 || submitting) return;
    setErrorMessage('');
    setSubmitting(true);
    try {
      const res = await createBodyMapReport({
        context: 'IN_EXERCISE',
        exercise_id: exerciseId,
        session_id: sessionId,
        zones: selectedZones,
      });
      setReportResult(res);
    } catch {
      setErrorMessage('No pudimos guardar el reporte de dolor. Por favor, reintentá.');
    } finally {
      setSubmitting(false);
    }
  };

  const handleAcceptVariant = async () => {
    if (!reportResult?.safe_variant?.variant) return;
    const variant = reportResult.safe_variant.variant;
    try {
      await updateReportAction(reportResult.id, 'VARIANT_ACCEPTED');
    } catch {
      // No bloquea la acción local
    }
    onAcceptVariant({ id: variant.exercise_id, name: variant.name });
    handleClose();
  };

  const handleSkip = async () => {
    if (reportResult) {
      try {
        await updateReportAction(reportResult.id, 'EXERCISE_SKIPPED');
      } catch {
        // No bloquea la acción local
      }
    }
    onSkipExercise();
    handleClose();
  };

  const handleClose = () => {
    setSelectedZones([]);
    setReportResult(null);
    setErrorMessage('');
    onClose();
  };

  const hasPain = selectedZones.some((z) => z.intensity === 'PAIN');
  const safeVariant = reportResult?.safe_variant;
  const embedUrl = safeVariant?.variant?.video_url
    ? getVideoEmbedUrl(safeVariant.variant.video_url)
    : null;

  return (
    <div
      className="body-map-modal-overlay"
      role="dialog"
      aria-modal="true"
      aria-labelledby="in-exercise-pain-title"
    >
      <div className="body-map-modal-card">
        <header className="body-map-modal-header">
          <div className="body-map-modal-header__title">
            <AlertTriangle className="body-map-modal-header__icon" size={24} aria-hidden="true" />
            <div>
              <h3 id="in-exercise-pain-title">Reportar molestia o dolor</h3>
              <p className="body-map-modal-header__exercise">Ejercicio: {exerciseName}</p>
            </div>
          </div>
          <button
            type="button"
            className="body-map-modal-close"
            onClick={handleClose}
            aria-label="Cerrar ventana de reporte"
          >
            <X size={20} />
          </button>
        </header>

        <div className="body-map-modal-body">
          {!reportResult ? (
            <>
              <p className="body-map-modal-intro">
                Indicá en qué zonas sentís molestias o dolor durante este ejercicio. Evaluaremos si
                existe una <strong>variante segura</strong> o si es conveniente saltearlo para evitar
                lesiones.
              </p>

              <BodyMapSelector
                selectedZones={selectedZones}
                onChange={setSelectedZones}
                readOnly={submitting}
              />

              {hasPain && (
                <div className="body-map-alert-box body-map-alert-box--pain" role="status">
                  <AlertCircle size={18} aria-hidden="true" />
                  <p>
                    Al marcar <strong>Dolor</strong>, se enviará una notificación inmediata a tu
                    entrenador para su seguimiento.
                  </p>
                </div>
              )}

              {errorMessage && (
                <p className="form-alert" role="alert">
                  {errorMessage}
                </p>
              )}

              <div className="body-map-modal-actions">
                <button
                  type="button"
                  className="body-map-btn body-map-btn--primary"
                  disabled={selectedZones.length === 0 || submitting}
                  onClick={handleConfirmReport}
                >
                  {submitting ? 'Evaluando variante…' : 'Confirmar reporte'}
                </button>
                <button
                  type="button"
                  className="body-map-btn body-map-btn--secondary"
                  onClick={handleClose}
                  disabled={submitting}
                >
                  Cancelar
                </button>
              </div>
            </>
          ) : (
            <div className="body-map-result-container">
              <div className="body-map-result-badge body-map-result-badge--success" role="status">
                <CheckCircle size={20} />
                <span>Reporte registrado correctamente.</span>
              </div>

              {reportResult.zones.some((z) => z.intensity === 'PAIN') && (
                <div className="body-map-alert-box body-map-alert-box--pain" role="status">
                  <AlertCircle size={18} />
                  <span>Tu entrenador ya fue notificado de la alerta de dolor en este ejercicio.</span>
                </div>
              )}

              {/* Caso 1: Se encontró Variante Segura (US-53) */}
              {safeVariant?.status === 'VARIANT' && safeVariant.variant && (
                <div className="body-map-variant-box" role="region" aria-label="Variante segura">
                  <div className="body-map-variant-box__header">
                    <ShieldCheck size={22} className="body-map-variant-box__icon" />
                    <div>
                      <strong>Variante segura recomendada:</strong>
                      <h4>{safeVariant.variant.name}</h4>
                    </div>
                  </div>
                  {safeVariant.variant.description && (
                    <p className="body-map-variant-box__desc">{safeVariant.variant.description}</p>
                  )}
                  {embedUrl && (
                    <div className="body-map-variant-box__video">
                      <iframe
                        src={embedUrl}
                        title={`Demostración de ${safeVariant.variant.name}`}
                        allowFullScreen
                        loading="lazy"
                      />
                    </div>
                  )}
                  <p className="body-map-variant-box__notice">
                    Esta variante fue configurada por tu entrenador para proteger las zonas
                    comprometidas sin suspender el estímulo muscular.
                  </p>
                  <div className="body-map-modal-actions">
                    <button
                      type="button"
                      className="body-map-btn body-map-btn--variant"
                      onClick={handleAcceptVariant}
                    >
                      <ShieldCheck size={18} />
                      Entrenar variante segura
                    </button>
                    <button
                      type="button"
                      className="body-map-btn body-map-btn--secondary"
                      onClick={handleClose}
                    >
                      Continuar con ejercicio original
                    </button>
                  </div>
                </div>
              )}

              {/* Caso 2: Ejercicio Bloqueado sin variante segura (US-53) */}
              {safeVariant?.status === 'BLOCKED' && (
                <div className="body-map-blocked-box" role="status">
                  <AlertTriangle size={22} className="body-map-blocked-box__icon" />
                  <div>
                    <strong>Sin variante segura disponible</strong>
                    <p>{safeVariant.message}</p>
                  </div>
                  <div className="body-map-modal-actions">
                    <button
                      type="button"
                      className="body-map-btn body-map-btn--skip"
                      onClick={handleSkip}
                    >
                      Saltear este ejercicio
                    </button>
                    <button
                      type="button"
                      className="body-map-btn body-map-btn--secondary"
                      onClick={handleClose}
                    >
                      Continuar sin saltear
                    </button>
                  </div>
                </div>
              )}

              {/* Caso 3: Ejercicio seguro */}
              {safeVariant?.status === 'SAFE' && (
                <div className="body-map-safe-box" role="status">
                  <CheckCircle size={22} className="body-map-safe-box__icon" />
                  <div>
                    <strong>Zonas sin contraindicación biomecánica</strong>
                    <p>
                      El ejercicio no presenta contraindicación directa en las zonas seleccionadas,
                      pero si el dolor persiste, te sugerimos descansar o reducir la carga.
                    </p>
                  </div>
                  <div className="body-map-modal-actions">
                    <button
                      type="button"
                      className="body-map-btn body-map-btn--primary"
                      onClick={handleClose}
                    >
                      Continuar entrenamiento
                    </button>
                    <button
                      type="button"
                      className="body-map-btn body-map-btn--skip"
                      onClick={handleSkip}
                    >
                      Saltear ejercicio
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
