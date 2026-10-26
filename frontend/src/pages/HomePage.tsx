import { Dumbbell, Inbox, LogOut, Sparkles } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { USER_ROLES } from '../constants/auth';
import { useAuth } from '../context/AuthContext';
import { homePath, ROUTES } from '../constants/routes';
import { getActivePlans, getTrainerRequests } from '../services/discoveryService';
import type { ActivePlansResponse } from '../types/discovery';
import { NotificationBell } from '../components/NotificationBell';
import type { NotificationItem } from '../types/discovery';

export function HomePage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  const [pendingRequestsCount, setPendingRequestsCount] = useState<number>(0);
  const [activePlans, setActivePlans] = useState<ActivePlansResponse>([]);
  const greeting = user?.role === USER_ROLES.trainer ? 'Tu espacio de entrenador' : 'Tu espacio de entrenamiento';

  useEffect(() => {
    let active = true;
    if (user?.role === USER_ROLES.trainer) {
      getTrainerRequests('PENDING')
        .then((requests) => {
          if (active) setPendingRequestsCount(requests.length);
        })
        .catch(() => {
          if (active) setPendingRequestsCount(0);
        });
    } else if (user?.role === USER_ROLES.student) {
      getActivePlans()
        .then((plans) => {
          if (active) {
            setActivePlans(plans);
          }
        })
        .catch(() => {
          if (active) setActivePlans([]);
        });
    }
    return () => {
      active = false;
    };
  }, [user?.role]);

  async function handleLogout() {
    try {
      await logout();
    } catch {
      setError('No pudimos cerrar la sesión en el servidor. Tu sesión local se cerró.');
    }
  }

  function handleNotificationClick(_notification: NotificationItem) {
    if (user?.role === USER_ROLES.student) {
      navigate(ROUTES.studentActivePlans);
    }
  }

  return (
    <main className={`home-shell${user?.role === USER_ROLES.trainer ? ' home-shell--trainer' : ''}`}>
      <header className="home-header">
        <Link className="brand" to={homePath(user?.role ?? USER_ROLES.student)}><span className="brand__icon"><Sparkles size={19} /></span><span>set<span className="brand__accent">to</span>set</span></Link>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          {user?.role === USER_ROLES.student && (
            <NotificationBell onNotificationClick={handleNotificationClick} />
          )}
          <button type="button" className="logout-button" onClick={handleLogout}><LogOut size={17} /> Cerrar sesión</button>
        </div>
      </header>
      <section className="welcome-card">
        <span className="welcome-kicker">CUENTA ACTIVA <span className="online-dot" /></span>
        <h1>{greeting}</h1>
        <p>Ingresaste como <strong>{user?.email}</strong>.</p>
        <div className="role-badge">{user?.role === USER_ROLES.trainer ? 'Entrenador/a' : 'Alumno/a'}</div>
        {user?.role === USER_ROLES.trainer && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.trainerProfile}>Completar mi perfil</Link>}
        {user?.role === USER_ROLES.trainer && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.trainerPlans}>Mis paquetes</Link>}
        {user?.role === USER_ROLES.trainer && (
          <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.trainerRequests}>
            <Inbox size={16} /> Solicitudes pendientes
            <span className="inbox-badge-count" aria-label={`${pendingRequestsCount} solicitudes pendientes`}>
              {pendingRequestsCount}
            </span>
          </Link>
        )}
        {user?.role === USER_ROLES.student && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.studentProfile}>Completar mi perfil</Link>}
        {user?.role === USER_ROLES.student && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.studentHealth}>Cuestionario de salud</Link>}
        {user?.role === USER_ROLES.student && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.studentProtectedZones}>Zonas a proteger</Link>}
        {user?.role === USER_ROLES.student && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.studentMedical}>Apto médico</Link>}
        {user?.role === USER_ROLES.student && <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.trainerSearch}>Buscar entrenadores</Link>}
        {user?.role === USER_ROLES.student && (
          <Link className="profile-cta" style={{ marginLeft: '16px' }} to={ROUTES.studentActivePlans}>
            <Inbox size={16} /> Mis entrenadores
            <span className="inbox-badge-count" aria-label={`${activePlans.length} vínculos activos`}>
              {activePlans.length}
            </span>
          </Link>
        )}
        {error && <p className="form-alert" role="alert">{error}</p>}
        {user?.role === USER_ROLES.student && (
          <p className="home-active-plans-summary">
            {activePlans.length > 0
              ? `Tenés ${activePlans.length} vínculo${activePlans.length === 1 ? '' : 's'} activo${activePlans.length === 1 ? '' : 's'}.`
              : 'Consultá tus vínculos y planes de entrenamiento.'}
          </p>
        )}
        <div className="welcome-next"><span>Este es el primer paso de Set to Set.</span><Dumbbell size={18} /></div>
      </section>
    </main>
  );
}
