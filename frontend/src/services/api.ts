import axios from 'axios';
import { AUTH_STORAGE_KEYS } from '../constants/auth';

const DEFAULT_API_URL = 'http://localhost:8000';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? DEFAULT_API_URL,
  headers: { 'Content-Type': 'application/json' },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem(AUTH_STORAGE_KEYS.token);
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
