import { api } from './api';
import type { RoutineTemplate, RoutineTemplateInput } from '../types/routineTemplate';

const TEMPLATES_PATH = '/api/v1/routine-templates';

export async function getRoutineTemplates(): Promise<RoutineTemplate[]> {
  const { data } = await api.get<RoutineTemplate[]>(TEMPLATES_PATH);
  return data;
}

export async function createRoutineTemplate(payload: RoutineTemplateInput): Promise<RoutineTemplate> {
  const { data } = await api.post<RoutineTemplate>(TEMPLATES_PATH, payload);
  return data;
}

export async function updateRoutineTemplate(templateId: string, payload: RoutineTemplateInput): Promise<RoutineTemplate> {
  const { data } = await api.put<RoutineTemplate>(`${TEMPLATES_PATH}/${templateId}`, payload);
  return data;
}

export async function getStudentRoutineTemplates(): Promise<RoutineTemplate[]> {
  const { data } = await api.get<RoutineTemplate[]>('/api/v1/students/me/routine-templates');
  return data;
}
