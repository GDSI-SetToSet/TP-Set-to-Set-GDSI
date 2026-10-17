import { ArrowRight, Check, Dumbbell, Mail, UserRound } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { AuthLayout } from '../components/AuthLayout';
import { PasswordInput } from '../components/PasswordInput';
import { USER_ROLES } from '../constants/auth';
import { ROUTES } from '../constants/routes';
import { useAuth } from '../context/AuthContext';
import { getApiErrorMessage } from '../services/errorMessage';
import { homePath } from '../constants/routes';
import type { UserRole } from '../types/auth';

export function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [role, setRole] = useState<UserRole>(USER_ROLES.student);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmation, setConfirmation] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homePath(user.role)} replace />;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    if (password !== confirmation) {
      setError('Las contraseñas no coinciden.');
      return;
    }
    setBusy(true);
    try {
      const registeredUser = await register(email, password, role);
      navigate(homePath(registeredUser.role), { replace: true });
    } catch (requestError) {
      setError(getApiErrorMessage(requestError, 'No pudimos crear tu cuenta. Intentá de nuevo.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthLayout eyebrow="EMPEZÁ HOY" title="Creá tu cuenta" subtitle="Un espacio para entrenar con seguimiento y acompañamiento.">
      <form className="auth-form register-form" onSubmit={handleSubmit} noValidate>
        <fieldset className="role-select">
          <legend>Quiero registrarme como</legend>
          <div className="role-options">
            <button type="button" className={`role-option${role === USER_ROLES.student ? ' role-option--active' : ''}`} onClick={() => setRole(USER_ROLES.student)} aria-pressed={role === USER_ROLES.student}>
              <span className="role-icon"><UserRound size={19} /></span><span><b>Alumno/a</b><small>Quiero encontrar mi ritmo</small></span>{role === USER_ROLES.student && <Check size={17} className="role-check" />}
            </button>
            <button type="button" className={`role-option${role === USER_ROLES.trainer ? ' role-option--active' : ''}`} onClick={() => setRole(USER_ROLES.trainer)} aria-pressed={role === USER_ROLES.trainer}>
              <span className="role-icon"><Dumbbell size={19} /></span><span><b>Entrenador/a</b><small>Quiero acompañar a otros</small></span>{role === USER_ROLES.trainer && <Check size={17} className="role-check" />}
            </button>
          </div>
        </fieldset>
        <div className="field">
          <label htmlFor="register-email">Email</label>
          <div className="input-wrap"><Mail size={18} className="input-icon" /><input id="register-email" name="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="nombre@ejemplo.com" autoComplete="email" required /></div>
        </div>
        <PasswordInput id="register-password" value={password} onChange={setPassword} autoComplete="new-password" />
        <PasswordInput id="register-confirmation" name="confirmation" label="Repetí tu contraseña" value={confirmation} onChange={setConfirmation} autoComplete="new-password" showHint={false} />
        {error && <div className="form-alert" role="alert">{error}</div>}
        <button className="submit-button" type="submit" disabled={busy}>{busy ? 'Creando cuenta…' : 'Crear cuenta'}<ArrowRight size={18} /></button>
      </form>
      <p className="auth-switch">¿Ya tenés cuenta? <Link to={ROUTES.login}>Iniciar sesión</Link></p>
    </AuthLayout>
  );
}
