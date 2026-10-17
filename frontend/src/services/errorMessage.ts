import axios from 'axios';

interface ApiErrorResponse {
  detail?: unknown;
}

export function getApiErrorMessage(error: unknown, fallback: string): string {
  if (axios.isAxiosError<ApiErrorResponse>(error)) {
    const detail = error.response?.data?.detail;
    if (typeof detail === 'string') return detail;
  }

  return fallback;
}
