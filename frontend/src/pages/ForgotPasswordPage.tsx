import { ArrowRight, Mail } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { AuthLayout } from '../components/AuthLayout';
import { AUTH_API_PATHS, PASSWORD_RESET_REQUESTED_MESSAGE } from '../constants/auth';
import { ROUTES } from '../constants/routes';
import { api } from '../services/api';
import { getApiErrorInfo } from '../services/errorMessage';

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      await api.post(AUTH_API_PATHS.forgotPassword, { email });
      setSent(true);
    } catch (requestError) {
      setError(getApiErrorInfo(requestError, 'Ingresá un email válido.').message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout eyebrow="RECUPERÁ TU ACCESO" title="Olvidé mi contraseña" subtitle="Ingresá tu email y te enviamos un enlace para definir una nueva.">
      {sent ? (
        <div className="form-alert form-alert--success" role="status">{PASSWORD_RESET_REQUESTED_MESSAGE} El enlace vence en 1 hora.</div>
      ) : (
        <form className="auth-form" onSubmit={handleSubmit} noValidate>
          <div className="field">
            <label htmlFor="forgot-email">Email</label>
            <div className="input-wrap"><Mail size={18} className="input-icon" /><input id="forgot-email" name="email" type="email" value={email} onChange={(event) => { setEmail(event.target.value); setError(''); }} placeholder="nombre@ejemplo.com" autoComplete="email" required /></div>
          </div>
          {error && <div className="form-alert auth-form-alert" role="alert">{error}</div>}
          <button className="submit-button" type="submit" disabled={busy}>{busy ? 'Enviando…' : 'Enviar enlace'}<ArrowRight size={18} /></button>
        </form>
      )}
      <p className="auth-switch">¿Te acordaste? <Link to={ROUTES.login}>Volver a iniciar sesión</Link></p>
    </AuthLayout>
  );
}
