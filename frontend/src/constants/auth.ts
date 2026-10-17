export const USER_ROLES = {
  trainer: 'TRAINER',
  student: 'STUDENT',
} as const;

export const PASSWORD_MIN_LENGTH = 8;

export const AUTH_API_PATHS = {
  login: '/api/v1/auth/login',
  register: '/api/v1/auth/register',
  logout: '/api/v1/auth/logout',
  currentUser: '/api/v1/auth/me',
} as const;

export const AUTH_STORAGE_KEYS = {
  token: 'set-to-set-token',
  user: 'set-to-set-user',
} as const;
