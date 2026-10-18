import { ArrowRight } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { AuthLayout } from '../components/AuthLayout';
import { PasswordInput } from '../components/PasswordInput';
import { AUTH_API_PATHS, INVALID_RESET_TOKEN_MESSAGE, PASSWORD_REQUIREMENTS_MESSAGE } from '../constants/auth';
import { ROUTES } from '../constants/routes';
import { api } from '../services/api';
import { getApiErrorInfo } from '../services/errorMessage';
import { meetsPasswordRequirements } from '../services/passwordValidation';

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token') ?? '';
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState(token ? '' : INVALID_RESET_TOKEN_MESSAGE);
  const [tokenRejected, setTokenRejected] = useState(!token);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    if (password !== confirmation) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    if (!meetsPasswordRequirements(password)) {
      setError(PASSWORD_REQUIREMENTS_MESSAGE);
      return;
    }
    setBusy(true);
    try {
      await api.post(AUTH_API_PATHS.resetPassword, { token, new_password: password });
      navigate(ROUTES.login, { replace: true, state: { passwordReset: true } });
    } catch (requestError) {
      const message = getApiErrorInfo(requestError, INVALID_RESET_TOKEN_MESSAGE).message;
      setError(message);
      setTokenRejected(message === INVALID_RESET_TOKEN_MESSAGE);
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout eyebrow="RECUPERÁ TU ACCESO" title="Definí tu nueva contraseña" subtitle="Al guardarla se cierran tus sesiones abiertas en todos los dispositivos.">
      {tokenRejected ? (
        <div className="form-alert" role="alert">{error}</div>
      ) : (
        <form className="auth-form register-form" onSubmit={handleSubmit} noValidate>
          <PasswordInput id="reset-password" label="Nueva contraseña" value={password} onChange={setPassword} autoComplete="new-password" />
          <PasswordInput id="reset-confirmation" name="confirmation" label="Repetí tu nueva contraseña" value={confirmation} onChange={setConfirmation} autoComplete="new-password" showHint={false} />
          {error && <div className="form-alert auth-form-alert" role="alert">{error}</div>}
          <button className="submit-button" type="submit" disabled={busy}>{busy ? 'Guardando…' : 'Guardar contraseña'}<ArrowRight size={18} /></button>
        </form>
      )}
      <p className="auth-switch">
        {tokenRejected ? <Link to={ROUTES.forgotPassword}>Solicitar un nuevo enlace</Link> : <Link to={ROUTES.login}>Volver a iniciar sesión</Link>}
      </p>
    </AuthLayout>
  );
}
