import { api } from './api';
import type {
  RoutineAssignmentStudent,
  RoutineModality,
  RoutineTemplate,
  RoutineTemplateInput,
  WorkoutSetLog,
  WorkoutSetLogInput,
  WorkoutSession,
} from '../types/routineTemplate';

const TEMPLATES_PATH = '/api/v1/routine-templates';
const STUDENT_ASSIGNED_PATH = '/api/v1/students/me/routine-templates/assigned';

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

export async function deleteRoutineTemplate(templateId: string): Promise<void> {
  await api.delete(`${TEMPLATES_PATH}/${templateId}`);
}

export async function getStudentRoutineTemplates(): Promise<RoutineTemplate[]> {
  const { data } = await api.get<RoutineTemplate[]>('/api/v1/students/me/routine-templates');
  return data;
}

export async function getAssignedStudentRoutine(): Promise<RoutineTemplate | null> {
  const { data } = await api.get<RoutineTemplate | null>(STUDENT_ASSIGNED_PATH);
  return data;
}

export async function updateAssignedRoutineModality(modality: RoutineModality): Promise<RoutineTemplate> {
  const { data } = await api.put<RoutineTemplate>(`${STUDENT_ASSIGNED_PATH}/modality`, { modality });
  return data;
}

export async function startAssignedWorkoutSession(dayName: string): Promise<WorkoutSession> {
  const { data } = await api.post<WorkoutSession>(`${STUDENT_ASSIGNED_PATH}/workout-sessions`, { day_name: dayName });
  return data;
}

export async function finishAssignedWorkoutSession(sessionId: string): Promise<WorkoutSession> {
  const { data } = await api.post<WorkoutSession>(`${STUDENT_ASSIGNED_PATH}/workout-sessions/${sessionId}/finish`);
  return data;
}

export async function getAssignedRoutineWorkoutSessions(): Promise<WorkoutSession[]> {
  const { data } = await api.get<WorkoutSession[]>(`${STUDENT_ASSIGNED_PATH}/workout-sessions`);
  return data;
}

export async function getAssignedRoutineWorkoutLogs(exerciseId?: string): Promise<WorkoutSetLog[]> {
  const { data } = await api.get<WorkoutSetLog[]>(
    `${STUDENT_ASSIGNED_PATH}/workout-logs`,
    exerciseId ? { params: { exercise_id: exerciseId } } : undefined,
  );
  return data;
}

export async function createAssignedRoutineWorkoutLog(payload: WorkoutSetLogInput): Promise<WorkoutSetLog> {
  const { data } = await api.post<WorkoutSetLog>(`${STUDENT_ASSIGNED_PATH}/workout-logs`, payload);
  return data;
}

export async function getRoutineAssignments(): Promise<RoutineAssignmentStudent[]> {
  const { data } = await api.get<RoutineAssignmentStudent[]>(`${TEMPLATES_PATH}/assignments`);
  return data;
}

/** Devuelve avisos: ejercicios de la rutina que chocan con las zonas a proteger del alumno. */
export async function assignRoutineToStudent(relationshipId: string, routineTemplateId: string | null): Promise<string[]> {
  const { data } = await api.put<{ warnings: string[] }>(
    `${TEMPLATES_PATH}/assignments/${relationshipId}`,
    { routine_template_id: routineTemplateId },
  );
  return data.warnings ?? [];
}
