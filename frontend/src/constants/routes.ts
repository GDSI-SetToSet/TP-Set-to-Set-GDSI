import { USER_ROLES } from './auth';
import type { UserRole } from '../types/auth';

export const ROUTES = {
  root: '/',
  login: '/login',
  register: '/registro',
  home: '/inicio',
  trainerHome: '/entrenador/inicio',
  studentHome: '/alumno/inicio',
  fallback: '*',
} as const;

export function homePath(role: UserRole): string {
  return role === USER_ROLES.trainer ? ROUTES.trainerHome : ROUTES.studentHome;
}
