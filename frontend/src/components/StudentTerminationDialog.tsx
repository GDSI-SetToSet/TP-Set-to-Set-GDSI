import { type FormEvent, useRef, useState } from 'react';
import { getApiErrorInfo } from '../services/errorMessage';
import { getFieldErrors } from '../services/paymentService';
import { terminateStudent } from '../services/trainerStudentService';
import type { StudentTerminationResult, TerminationCategory } from '../types/trainerStudent';
import { useDialogFocus } from './useDialogFocus';

const DETAIL_MAX = 500;
const CATEGORY_MESSAGE = 'Elegí el motivo de la baja.';
const DETAIL_MESSAGE = 'Contá el motivo de la baja (hasta 500 caracteres).';

const CATEGORIES: { value: TerminationCategory; label: string }[] = [
  { value: 'FALTA_DE_PAGO', label: 'Falta de pago' },
  { value: 'RAZONES_PERSONALES', label: 'Razones personales' },
  { value: 'OTRO', label: 'Otro motivo' },
];

interface StudentTerminationDialogProps {
  studentId: string;
  studentName: string;
  onTerminated: (result: StudentTerminationResult) => void;
  onClose: () => void;
}

/** US-35: dar de baja al alumno indicando el motivo (escenarios 1–3). */
export function StudentTerminationDialog({ studentId, studentName, onTerminated, onClose }: StudentTerminationDialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null);
  const [category, setCategory] = useState<TerminationCategory | ''>('');
  const [detail, setDetail] = useState('');
  const [errors, setErrors] = useState<{ category?: string; detail?: string }>({});
  const [formError, setFormError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useDialogFocus(dialogRef, onClose, submitting);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (submitting) return;
    const text = detail.trim();
    const found: { category?: string; detail?: string } = {};
    if (!category) found.category = CATEGORY_MESSAGE;
    if (text.length > DETAIL_MAX || (category === 'OTRO' && !text)) found.detail = DETAIL_MESSAGE;
    setErrors(found);
    setFormError('');
    if (Object.keys(found).length > 0 || !category) return;

    setSubmitting(true);
    try {
      onTerminated(await terminateStudent(studentId, { category, detail: text || null }));
    } catch (error) {
      const fieldErrors = getFieldErrors(error);
      setErrors(fieldErrors);
      if (Object.keys(fieldErrors).length === 0) {
        setFormError(getApiErrorInfo(error, 'No pudimos dar de baja al alumno. Intentá nuevamente.').message);
      }
      setSubmitting(false);
    }
  }

  return (
    <div className="request-modal-backdrop" role="presentation">
      <div
        ref={dialogRef}
        className="request-modal termination-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="termination-dialog-title"
        aria-describedby="termination-dialog-effects"
      >
        <div className="profile-heading">
          <span>DAR DE BAJA</span>
          <h2 id="termination-dialog-title">{studentName}</h2>
        </div>
        <div id="termination-dialog-effects" className="termination-dialog__effects">
          <p>Al confirmar, la suscripción termina y no se puede deshacer:</p>
          <ul>
            <li>se libera un cupo y deja de figurar en tus alumnos activos y en Suscripciones;</li>
            <li>dejás de ver sus datos de salud y él deja de ver su rutina;</li>
            <li>el chat queda en modo lectura. Los pagos y mensajes se conservan.</li>
          </ul>
        </div>

        <form className="profile-form request-modal__form" onSubmit={handleSubmit} noValidate>
          <fieldset
            className="termination-dialog__categories"
            aria-invalid={Boolean(errors.category)}
            aria-describedby={errors.category ? 'termination-category-error' : undefined}
          >
            <legend>Motivo de la baja</legend>
            {CATEGORIES.map((option, index) => (
              <label key={option.value} className="termination-dialog__option">
                <input
                  type="radio"
                  name="termination-category"
                  value={option.value}
                  checked={category === option.value}
                  onChange={() => setCategory(option.value)}
                  disabled={submitting}
                  data-autofocus={index === 0 ? true : undefined}
                />
                {option.label}
              </label>
            ))}
            {errors.category && <small className="field-error" id="termination-category-error">{errors.category}</small>}
          </fieldset>

          <label>
            Detalle {category === 'OTRO' ? '(obligatorio)' : '(opcional)'}
            <textarea
              value={detail}
              onChange={(event) => setDetail(event.target.value)}
              rows={3}
              maxLength={DETAIL_MAX}
              disabled={submitting}
              aria-invalid={Boolean(errors.detail)}
              aria-describedby={`termination-detail-hint${errors.detail ? ' termination-detail-error' : ''}`}
            />
            <small className="termination-dialog__hint" id="termination-detail-hint">
              {studentName} verá este motivo en su notificación. {detail.length}/{DETAIL_MAX}
            </small>
            {errors.detail && <small className="field-error" id="termination-detail-error">{errors.detail}</small>}
          </label>

          {formError && <p className="form-alert" role="alert">{formError}</p>}

          <div className="termination-dialog__actions">
            <button type="submit" className="inbox-action-btn inbox-action-btn--reject" disabled={submitting}>
              {submitting ? 'Dando de baja…' : 'Confirmar baja'}
            </button>
            <button type="button" className="plan-cancel" onClick={onClose} disabled={submitting}>
              Cancelar
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
