export const USER_ROLES = {
  trainer: 'TRAINER',
  student: 'STUDENT',
} as const;

export const PASSWORD_MIN_LENGTH = 8;
export const PASSWORD_MAX_LENGTH = 128;
export const PASSWORD_REQUIREMENTS_MESSAGE =
  'La contraseña debe tener entre 8 y 128 caracteres e incluir al menos una mayúscula, una minúscula y un número.';

export const LOGIN_LOCKOUT_SECONDS = 15 * 60;
export const LOGIN_LOCKOUT_STORAGE_PREFIX = 'set-to-set-login-lockout:';
export const LOGIN_LOCKOUT_MESSAGE = 'Se excedió el límite de intentos.';
export const INVALID_CREDENTIALS_MESSAGE = 'Mail o contraseña incorrectos';
export const PASSWORD_RESET_REQUESTED_MESSAGE = 'Si el correo está registrado, recibirás un enlace de recuperación.';
export const PASSWORD_RESET_SUCCESS_MESSAGE = 'Tu contraseña se actualizó. Iniciá sesión con tu nueva contraseña.';
export const INVALID_RESET_TOKEN_MESSAGE = 'El enlace de recuperación no es válido o expiró. Solicitá uno nuevo.';

export const AUTH_API_PATHS = {
  login: '/api/v1/auth/login',
  register: '/api/v1/auth/register',
  logout: '/api/v1/auth/logout',
  currentUser: '/api/v1/auth/me',
  forgotPassword: '/api/v1/auth/forgot-password',
  resetPassword: '/api/v1/auth/reset-password',
} as const;

export const AUTH_STORAGE_KEYS = {
  token: 'set-to-set-token',
  user: 'set-to-set-user',
} as const;
