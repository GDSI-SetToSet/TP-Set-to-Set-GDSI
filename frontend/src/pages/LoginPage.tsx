import { ArrowRight, Mail } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { AuthLayout } from '../components/AuthLayout';
import { PasswordInput } from '../components/PasswordInput';
import { INVALID_CREDENTIALS_MESSAGE, LOGIN_LOCKOUT_MESSAGE, LOGIN_LOCKOUT_SECONDS, PASSWORD_RESET_SUCCESS_MESSAGE } from '../constants/auth';
import { ROUTES, homePath } from '../constants/routes';
import { useAuth } from '../context/AuthContext';
import { getApiErrorInfo } from '../services/errorMessage';
import { useLoginLockout } from '../hooks/useLoginLockout';

function formatLockoutDuration(seconds: number): string {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${minutes}:${String(remainingSeconds).padStart(2, '0')}`;
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const passwordWasReset = (location.state as { passwordReset?: boolean } | null)?.passwordReset === true;
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const { remainingSeconds, startLockout } = useLoginLockout(email);
  const isLocked = remainingSeconds > 0;
  const formError = isLocked
    ? `${LOGIN_LOCKOUT_MESSAGE} Podés volver a intentarlo en ${formatLockoutDuration(remainingSeconds)}.`
    : error;

  if (user) return <Navigate to={homePath(user.role)} replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isLocked) return;
    setError('');
    setBusy(true);
    try {
      const signedInUser = await login(email, password);
      navigate(homePath(signedInUser.role), { replace: true });
    } catch (requestError) {
      const apiError = getApiErrorInfo(requestError, INVALID_CREDENTIALS_MESSAGE);
      if (apiError.status === undefined) {
        setError('No pudimos conectar con el servidor. Verificá que el backend esté iniciado.');
      } else if (apiError.status === 423) {
        startLockout(apiError.retryAfterSeconds ?? LOGIN_LOCKOUT_SECONDS);
        setError('');
      } else {
        setError(apiError.message);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout eyebrow="QUÉ BUENO VERTE" title="Iniciá sesión" subtitle="Entrá a tu espacio y seguí con tu próximo objetivo.">
      {passwordWasReset && !formError && <div className="form-alert form-alert--success auth-form-notice" role="status">{PASSWORD_RESET_SUCCESS_MESSAGE}</div>}
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        <div className="field">
          <label htmlFor="login-email">Email</label>
          <div className="input-wrap"><Mail size={18} className="input-icon" /><input id="login-email" name="email" type="email" value={email} onChange={(event) => { setEmail(event.target.value); setError(''); }} placeholder="nombre@ejemplo.com" autoComplete="email" required /></div>
        </div>
        <PasswordInput id="login-password" value={password} onChange={setPassword} autoComplete="current-password" />
        <Link className="forgot-password-link" to={ROUTES.forgotPassword}>Olvidé mi contraseña</Link>
        {formError && <div className="form-alert auth-form-alert" role="alert">{formError}</div>}
        <button className="submit-button" type="submit" disabled={busy || isLocked}>
          {isLocked ? `Reintentar en ${formatLockoutDuration(remainingSeconds)}` : busy ? 'Ingresando…' : 'Iniciar sesión'}
          {!isLocked && <ArrowRight size={18} />}
        </button>
      </form>
      <p className="auth-switch">¿Todavía no tenés cuenta? <Link to={ROUTES.register}>Crear cuenta</Link></p>
      <p className="auth-note">El mensaje de error no revela si el email o la contraseña fueron incorrectos.</p>
    </AuthLayout>
  );
}
