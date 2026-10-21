import axios from 'axios';
import { api } from './api';
import type { HealthQuestionnaire, HealthQuestionnaireInput } from '../types/student';

const PATH = '/api/v1/students/me/health-questionnaire';

export async function getOwnHealthQuestionnaire(): Promise<HealthQuestionnaire | null> {
  try {
    const { data } = await api.get<HealthQuestionnaire>(PATH);
    return data;
  } catch (caught) {
    if (axios.isAxiosError(caught) && caught.response?.status === 404) return null;
    throw caught;
  }
}

export async function saveHealthQuestionnaire(payload: HealthQuestionnaireInput): Promise<HealthQuestionnaire> {
  const { data } = await api.post<HealthQuestionnaire>(PATH, payload);
  return data;
}
