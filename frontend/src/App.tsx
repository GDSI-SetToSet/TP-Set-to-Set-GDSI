import { Navigate, Route, Routes } from 'react-router-dom';
import { USER_ROLES } from './constants/auth';
import { ROUTES, homePath } from './constants/routes';
import { useAuth } from './context/AuthContext';
import { ForgotPasswordPage } from './pages/ForgotPasswordPage';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';
import { ResetPasswordPage } from './pages/ResetPasswordPage';
import { TrainerProfileEditPage } from './pages/TrainerProfileEditPage';
import type { UserRole } from './types/auth';
import { HealthQuestionnairePage } from './pages/HealthQuestionnairePage';
import { StudentProfileEditPage } from './pages/StudentProfileEditPage';

function ProtectedRoute({ children, role }: { children: JSX.Element; role: UserRole }) {
  const { user, loading } = useAuth();
  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando tu espacio…</main>;
  if (!user) return <Navigate to={ROUTES.login} replace />;
  if (user.role !== role) return <Navigate to={homePath(user.role)} replace />;
  return children;
}

function HomeRedirect() {
  const { user, loading } = useAuth();
  if (loading) return <main className="loading-screen"><span className="loading-mark" /> Cargando tu espacio…</main>;
  return user ? <Navigate to={homePath(user.role)} replace /> : <Navigate to={ROUTES.login} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path={ROUTES.root} element={<Navigate to={ROUTES.login} replace />} />
      <Route path={ROUTES.login} element={<LoginPage />} />
      <Route path={ROUTES.register} element={<RegisterPage />} />
      <Route path={ROUTES.forgotPassword} element={<ForgotPasswordPage />} />
      <Route path={ROUTES.resetPassword} element={<ResetPasswordPage />} />
      <Route path={ROUTES.home} element={<HomeRedirect />} />
      <Route path={ROUTES.trainerHome} element={<ProtectedRoute role={USER_ROLES.trainer}><HomePage /></ProtectedRoute>} />
      <Route path={ROUTES.trainerProfile} element={<ProtectedRoute role={USER_ROLES.trainer}><TrainerProfileEditPage /></ProtectedRoute>} />
      <Route path={ROUTES.studentHome} element={<ProtectedRoute role={USER_ROLES.student}><HomePage /></ProtectedRoute>} />
      <Route path={ROUTES.fallback} element={<Navigate to={ROUTES.login} replace />} />
      <Route path={ROUTES.studentHealth} element={<ProtectedRoute role={USER_ROLES.student}><HealthQuestionnairePage /></ProtectedRoute>} />
      <Route path={ROUTES.studentProfile} element={<ProtectedRoute role={USER_ROLES.student}><StudentProfileEditPage /></ProtectedRoute>} />
    </Routes>
  );
}
