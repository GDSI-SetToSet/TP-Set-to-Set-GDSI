import { Dumbbell, LogOut, Sparkles } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useState } from 'react';
import { USER_ROLES } from '../constants/auth';
import { useAuth } from '../context/AuthContext';
import { homePath, ROUTES } from '../constants/routes';

export function HomePage() {
  const { user, logout } = useAuth();
  const [error, setError] = useState('');
  const greeting = user?.role === USER_ROLES.trainer ? 'Tu espacio de entrenador' : 'Tu espacio de entrenamiento';

  async function handleLogout() {
    try {
      await logout();
    } catch {
      setError('No pudimos cerrar la sesión en el servidor. Tu sesión local se cerró.');
    }
  }

  return (
    <main className="home-shell">
      <header className="home-header">
        <Link className="brand" to={homePath(user?.role ?? USER_ROLES.student)}><span className="brand__icon"><Sparkles size={19} /></span><span>set<span className="brand__accent">to</span>set</span></Link>
        <button type="button" className="logout-button" onClick={handleLogout}><LogOut size={17} /> Cerrar sesión</button>
      </header>
      <section className="welcome-card">
        <span className="welcome-kicker">CUENTA ACTIVA <span className="online-dot" /></span>
        <h1>{greeting}</h1>
        <p>Ingresaste como <strong>{user?.email}</strong>.</p>
        <div className="role-badge">{user?.role === USER_ROLES.trainer ? 'Entrenador/a' : 'Alumno/a'}</div>
        {user?.role === USER_ROLES.trainer && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.trainerProfile}>Completar mi perfil</Link>}
        {user?.role === USER_ROLES.student && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.studentProfile}>Completar mi perfil</Link>}
        {user?.role === USER_ROLES.student && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.studentHealth}>Cuestionario de salud</Link>}
        {user?.role === USER_ROLES.student && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.studentProtectedZones}>Zonas a proteger</Link>}
        {user?.role === USER_ROLES.student && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.studentMedical}>Apto médico</Link>}
        {error && <p className="form-alert" role="alert">{error}</p>}
        <div className="welcome-next"><span>Este es el primer paso de Set to Set.</span><Dumbbell size={18} /></div>
      </section>
    </main>
  );
}
