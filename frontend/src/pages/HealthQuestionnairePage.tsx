import axios from 'axios';
import { ArrowLeft, CheckCircle2, Pencil, Save } from 'lucide-react';
import { type FormEvent, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getOwnHealthQuestionnaire, saveHealthQuestionnaire } from '../services/studentHealthService';
import { HEALTH_QUESTIONS, type HealthQuestionKey } from '../types/student';
import '../styles/health-questionnaire.css';

type Answers = Partial<Record<HealthQuestionKey, boolean>>;
const QUESTION_KEYS = Object.keys(HEALTH_QUESTIONS) as HealthQuestionKey[];

export function HealthQuestionnairePage() {
  const navigate = useNavigate();
  const redirectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [savedAnswers, setSavedAnswers] = useState<Answers>({});
  const [other, setOther] = useState('');
  const [savedOther, setSavedOther] = useState('');
  const [isCompleted, setIsCompleted] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState('');
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    getOwnHealthQuestionnaire()
      .then((data) => {
        if (!data) return;
        const loadedAnswers = Object.fromEntries(QUESTION_KEYS.map((key) => [key, data[key]])) as Answers;
        const loadedOther = data.other_medical_conditions ?? '';
        setAnswers(loadedAnswers);
        setSavedAnswers(loadedAnswers);
        setOther(loadedOther);
        setSavedOther(loadedOther);
        setIsCompleted(true);
      })
      .catch(() => setError('No pudimos cargar tu cuestionario. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => () => {
    if (redirectTimeout.current !== null) clearTimeout(redirectTimeout.current);
  }, []);

  const allAnswered = QUESTION_KEYS.every((key) => answers[key] !== undefined);

  function startEditing() {
    setIsEditing(true);
    setMissing(false);
    setError('');
  }

  function cancelEditing() {
    setAnswers(savedAnswers);
    setOther(savedOther);
    setMissing(false);
    setError('');
    setIsEditing(false);
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');
    if (!allAnswered) {
      setMissing(true);
      return;
    }
    setIsSubmitting(true);
    try {
      const submittedAnswers = { ...answers } as Answers;
      const submittedOther = other.trim();
      await saveHealthQuestionnaire({ ...(submittedAnswers as Record<HealthQuestionKey, boolean>), other_medical_conditions: submittedOther || null });
      setSavedAnswers(submittedAnswers);
      setSavedOther(submittedOther);
      setIsCompleted(true);
      setIsEditing(false);
      setIsSubmitting(false);
      setIsSuccess(true);
      redirectTimeout.current = setTimeout(() => {
        navigate(ROUTES.studentHome);
        redirectTimeout.current = null;
      }, 1000);
    } catch (caught) {
      setError(axios.isAxiosError(caught) ? 'Revisá las respuestas ingresadas.' : 'No pudimos guardar el cuestionario. Intentá nuevamente.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando cuestionario…</main>;

  return (
    <>
    <main className="profile-shell">
      <header className="profile-header">
        <Link to={ROUTES.studentHome} className="profile-back"><ArrowLeft size={18} /> Volver al inicio</Link>
      </header>
      <section className="profile-card">
        <div className="profile-heading">
          <span>SALUD</span>
          <h1>Cuestionario de salud</h1>
          <p>{isCompleted && !isEditing ? 'Estas son las respuestas que compartís con tu entrenador.' : 'Respondé las cinco preguntas para que tu entrenador diseñe una rutina segura.'}</p>
        </div>
        {isCompleted && !isEditing ? (
          <section className="health-summary">
            <dl className="health-summary__grid" aria-label="Respuestas del cuestionario de salud">
              {QUESTION_KEYS.map((key) => (
                <div className="health-summary__item" key={key}>
                  <dt>{HEALTH_QUESTIONS[key]}</dt>
                  <dd>{answers[key] ? 'Sí' : 'No'}</dd>
                </div>
              ))}
              <div className="health-summary__item">
                <dt>Otras condiciones médicas</dt>
                <dd>{other.trim() || 'Ninguna informada'}</dd>
              </div>
            </dl>
            <div className="health-summary__actions">
              <button className="profile-save" type="button" onClick={startEditing}>
                <Pencil size={18} /> Editar
              </button>
            </div>
          </section>
        ) : (
        <form className="profile-form" onSubmit={handleSubmit} noValidate>
          {QUESTION_KEYS.map((key) => (
            <fieldset key={key}>
              <legend>{HEALTH_QUESTIONS[key]}</legend>
              {[true, false].map((value) => (
                <label key={String(value)}>
                  <input type="radio" name={key} checked={answers[key] === value} onChange={() => { setAnswers((current) => ({ ...current, [key]: value })); setMissing(false); }} /> {value ? 'Sí' : 'No'}
                </label>
              ))}
              {missing && answers[key] === undefined && <small className="field-error">Este campo es obligatorio</small>}
            </fieldset>
          ))}
          <label>Otras condiciones médicas
            <textarea value={other} onChange={(event) => setOther(event.target.value)} rows={3} placeholder="Opcional: patologías u observaciones que tu entrenador deba saber" />
          </label>
          {missing && <p className="form-alert" role="alert">Respondé todas las preguntas.</p>}
          {error && <p className="form-alert" role="alert">{error}</p>}
          <div className="plan-form__actions">
            <button className="profile-save" type="submit" disabled={isSubmitting}><Save size={18} /> {isSubmitting ? 'Guardando...' : 'Guardar cuestionario'}</button>
            {isCompleted && isEditing && <button className="health-questionnaire-cancel" type="button" onClick={cancelEditing} disabled={isSubmitting}>Cancelar</button>}
          </div>
        </form>
        )}
      </section>
    </main>
    {(isSubmitting || isSuccess) && (
      <div className="success-overlay" role="status" aria-live="polite" aria-atomic="true">
        <div className="success-overlay__card">
          {isSuccess ? (
            <>
              <span className="success-overlay__icon"><CheckCircle2 size={32} aria-hidden="true" /></span>
              <h2>¡Guardado con éxito!</h2>
              <p>Redirigiendo...</p>
            </>
          ) : (
            <>
              <span className="success-overlay__spinner" aria-hidden="true" />
              <h2>Guardando...</h2>
            </>
          )}
        </div>
      </div>
    )}
    </>
  );
}
