import { ArrowRight, Mail } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { AuthLayout } from '../components/AuthLayout';
import { PasswordInput } from '../components/PasswordInput';
import { useAuth } from '../context/AuthContext';
import { ROUTES } from '../constants/routes';
import { getApiErrorMessage } from '../services/errorMessage';
import { homePath } from '../constants/routes';

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homePath(user.role)} replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    setBusy(true);
    try {
      const signedInUser = await login(email, password);
      navigate(homePath(signedInUser.role), { replace: true });
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'No pudimos iniciar sesión. Revisá tus datos e intentá de nuevo.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout eyebrow="QUÉ BUENO VERTE" title="Iniciá sesión" subtitle="Entrá a tu espacio y seguí con tu próximo objetivo.">
      <form className="auth-form" onSubmit={handleSubmit} noValidate>
        {error && <div className="form-alert" role="alert">{error}</div>}
        <div className="field">
          <label htmlFor="login-email">Email</label>
          <div className="input-wrap"><Mail size={18} className="input-icon" /><input id="login-email" name="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="nombre@ejemplo.com" autoComplete="email" required /></div>
        </div>
        <PasswordInput id="login-password" value={password} onChange={setPassword} autoComplete="current-password" />
        <button className="submit-button" type="submit" disabled={busy}>{busy ? 'Ingresando…' : 'Iniciar sesión'}<ArrowRight size={18} /></button>
      </form>
      <p className="auth-switch">¿Todavía no tenés cuenta? <Link to={ROUTES.register}>Crear cuenta</Link></p>
      <p className="auth-note">El mensaje de error no revela si el email o la contraseña fueron incorrectos.</p>
    </AuthLayout>
  );
}
