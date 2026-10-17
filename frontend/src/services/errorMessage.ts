import axios from 'axios';

interface ApiErrorResponse {
  detail?: unknown;
}

export interface ApiErrorInfo {
  message: string;
  status?: number;
  retryAfterSeconds?: number;
}

export function getApiErrorInfo(error: unknown, fallback: string): ApiErrorInfo {
  if (axios.isAxiosError<ApiErrorResponse>(error)) {
    const detail = error.response?.data?.detail;
    const retryAfterHeader = error.response?.headers?.['retry-after'];
    const retryAfterSeconds = Number(retryAfterHeader);
    return {
      message: typeof detail === 'string' ? detail : fallback,
      status: error.response?.status,
      retryAfterSeconds: Number.isFinite(retryAfterSeconds) && retryAfterSeconds > 0 ? retryAfterSeconds : undefined,
    };
  }

  return { message: fallback };
}
