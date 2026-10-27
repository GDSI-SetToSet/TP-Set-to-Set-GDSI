import axios from 'axios';
import { ArrowLeft, CheckCircle2, Save } from 'lucide-react';
import { type FormEvent, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ROUTES } from '../constants/routes';
import { getOwnHealthQuestionnaire, saveHealthQuestionnaire } from '../services/studentHealthService';
import { HEALTH_QUESTIONS, type HealthQuestionKey } from '../types/student';

type Answers = Partial<Record<HealthQuestionKey, boolean>>;
const QUESTION_KEYS = Object.keys(HEALTH_QUESTIONS) as HealthQuestionKey[];

export function HealthQuestionnairePage() {
  const navigate = useNavigate();
  const redirectTimeout = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [answers, setAnswers] = useState<Answers>({});
  const [other, setOther] = useState('');
  const [loading, setLoading] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [error, setError] = useState('');
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    getOwnHealthQuestionnaire()
      .then((data) => {
        if (!data) return;
        setAnswers(Object.fromEntries(QUESTION_KEYS.map((key) => [key, data[key]])));
        setOther(data.other_medical_conditions ?? '');
      })
      .catch(() => setError('No pudimos cargar tu cuestionario. Intentá nuevamente.'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => () => {
    if (redirectTimeout.current !== null) clearTimeout(redirectTimeout.current);
  }, []);

  const allAnswered = QUESTION_KEYS.every((key) => answers[key] !== undefined);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError('');
    if (!allAnswered) {
      setMissing(true);
      return;
    }
    setIsSubmitting(true);
    try {
      await saveHealthQuestionnaire({ ...(answers as Record<HealthQuestionKey, boolean>), other_medical_conditions: other.trim() || null });
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
          <p>Respondé las cinco preguntas para que tu entrenador diseñe una rutina segura. Tus objetivos se cargan en tu perfil.</p>
        </div>
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
          <button className="profile-save" type="submit" disabled={isSubmitting}><Save size={18} /> {isSubmitting ? 'Guardando...' : 'Guardar cuestionario'}</button>
        </form>
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
