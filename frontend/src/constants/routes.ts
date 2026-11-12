import { USER_ROLES } from './auth';
import type { UserRole } from '../types/auth';
import type { NotificationItem } from '../types/discovery';

export const ROUTES = {
  root: '/',
  login: '/login',
  register: '/registro',
  forgotPassword: '/olvide-mi-contrasena',
  resetPassword: '/restablecer-contrasena',
  home: '/inicio',
  trainerHome: '/entrenador/inicio',
  trainerProfile: '/entrenador/perfil',
  trainerPlans: '/entrenador/paquetes',
  trainerExercises: '/entrenador/ejercicios',
  trainerRoutines: '/entrenador/rutinas',
  trainerGenerateAIRoutine: '/entrenador/rutinas/generar-ia',
  trainerStudents: '/entrenador/alumnos',
  trainerDailyRoutines: '/entrenador/rutinas-del-dia',
  trainerStudentRoutine: '/entrenador/alumnos/:studentId/rutina',
  trainerRequests: '/entrenador/solicitudes',
  trainerRequestDetail: '/entrenador/solicitudes/:requestId',
  studentHome: '/alumno/inicio',
  studentProfile: '/alumno/perfil',
  studentHealth: '/alumno/salud',
  studentProtectedZones: '/alumno/zonas-a-proteger',
  studentMedical: '/alumno/apto-medico',
  studentActivePlans: '/alumno/mis-entrenamientos',
  studentRoutines: '/alumno/rutinas',
  studentRoutineSession: '/alumno/rutinas/sesion',
  trainerSearch: '/alumno/buscar-entrenadores',
  trainerPublicDetail: '/entrenadores/:trainerId',
  trainerRequest: '/entrenadores/:trainerId/solicitar',
  studentRequests: '/alumno/mis-solicitudes',
  fallback: '*',
} as const;

export function homePath(role: UserRole): string {
  return role === USER_ROLES.trainer ? ROUTES.trainerHome : ROUTES.studentHome;
}

export function trainerNotificationPath(notification: Pick<
  NotificationItem,
  'type' | 'related_student_id' | 'related_session_id' | 'related_entity_id'
>): string {
  if (
    notification.type !== 'PAIN_ALERT'
    && notification.type !== 'PERSONAL_RECORD'
    && notification.type !== 'PROTECTED_ZONES_UPDATED'
  ) {
    return ROUTES.trainerRequests;
  }

  if (!notification.related_student_id) {
    return ROUTES.trainerStudents;
  }

  const params = new URLSearchParams({ studentId: notification.related_student_id });
  if (notification.related_session_id) {
    params.set('sessionId', notification.related_session_id);
  }
  if (
    notification.related_entity_id
    && (notification.type === 'PAIN_ALERT' || notification.type === 'PERSONAL_RECORD')
  ) {
    params.set('eventId', notification.related_entity_id);
    params.set('eventType', notification.type);
  }
  return `${ROUTES.trainerStudents}?${params.toString()}`;
}
