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
  trainerSubscriptions: '/entrenador/suscripciones',
  trainerMessages: '/entrenador/mensajes',
  trainerTechnicalQueries: '/entrenador/consultas',
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
  studentProgress: '/alumno/evolucion',
  studentMessages: '/alumno/mensajes',
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

/** US-21: la notificación de mensajes lleva a la conversación del vínculo. */
function messagesPath(base: string, relationshipId: string | null | undefined): string {
  return relationshipId ? `${base}?relationshipId=${encodeURIComponent(relationshipId)}` : base;
}

export function studentNotificationPath(notification: Pick<NotificationItem, 'type' | 'related_entity_id'>): string {
  if (notification.type === 'NEW_MESSAGE') return messagesPath(ROUTES.studentMessages, notification.related_entity_id);
  // US-67: logros y felicitaciones llevan a "Mi evolución", donde está la sección de logros.
  if (notification.type === 'ACHIEVEMENT_UNLOCKED' || notification.type === 'CONGRATULATION') return ROUTES.studentProgress;
  // US-35: la baja (SUBSCRIPTION_TERMINATED) lleva a "Mis entrenadores" (por defecto).
  // US-68: el mensaje de aliento por racha cortada lleva a la rutina del día.
  return notification.type === 'EFFORT_FEEDBACK' || notification.type === 'STREAK_RESET'
    ? ROUTES.studentRoutines
    : ROUTES.studentActivePlans;
}

export function trainerNotificationPath(notification: Pick<
  NotificationItem,
  'type' | 'related_student_id' | 'related_session_id' | 'related_entity_id'
>): string {
  if (notification.type === 'NEW_MESSAGE') return messagesPath(ROUTES.trainerMessages, notification.related_entity_id);
  if (notification.type === 'TECHNICAL_QUERY') return ROUTES.trainerTechnicalQueries;
  // US-67: el logro de un alumno lleva a su detalle, donde puede felicitarlo.
  if (notification.type === 'ACHIEVEMENT_UNLOCKED' && notification.related_student_id) {
    return `${ROUTES.trainerStudents}?studentId=${encodeURIComponent(notification.related_student_id)}`;
  }
  if (
    notification.type !== 'PAIN_ALERT'
    && notification.type !== 'REPEATED_DISCOMFORT_ALERT'
    && notification.type !== 'EXCESSIVE_EFFORT_ALERT'
    && notification.type !== 'PERSONAL_RECORD'
    && notification.type !== 'PROTECTED_ZONES_UPDATED'
    && notification.type !== 'ABANDONMENT_RISK'
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
    && (
      notification.type === 'PAIN_ALERT'
      || notification.type === 'REPEATED_DISCOMFORT_ALERT'
      || notification.type === 'EXCESSIVE_EFFORT_ALERT'
      || notification.type === 'PERSONAL_RECORD'
    )
  ) {
    params.set('eventId', notification.related_entity_id);
    params.set('eventType', notification.type);
  }
  return `${ROUTES.trainerStudents}?${params.toString()}`;
}
