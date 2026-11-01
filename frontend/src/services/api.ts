import axios from 'axios';
import { AUTH_STORAGE_KEYS } from '../constants/auth';

// 127.0.0.1 evita que `localhost` resuelva primero a ::1 y alcance otro servicio
// publicado por Docker en el mismo puerto durante el desarrollo local.
const DEFAULT_API_URL = 'http://127.0.0.1:8000';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? DEFAULT_API_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_STORAGE_KEYS.token);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
