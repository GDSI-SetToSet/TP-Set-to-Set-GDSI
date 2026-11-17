import { api } from './api';
import { localDateInputValue } from '../utils/dailyRoutineFormat.mjs';
import type {
  AbandonmentRiskItem,
  DailyRoutineItem,
  EvolutionGrouping,
  EvolutionPeriod,
  SessionComparison,
  StudentTerminationPayload,
  StudentTerminationResult,
  TrainerStudentDetail,
  TrainerStudentListItem,
  TrainingEvolution,
} from '../types/trainerStudent';

const STUDENTS_PATH = '/api/v1/trainers/me/students';

export async function getTrainerStudents(): Promise<TrainerStudentListItem[]> {
  const { data } = await api.get<TrainerStudentListItem[]>(STUDENTS_PATH);
  return data;
}

export async function getTrainerStudentDetail(studentId: string): Promise<TrainerStudentDetail> {
  const { data } = await api.get<TrainerStudentDetail>(`${STUDENTS_PATH}/${studentId}`);
  return data;
}

/** US-22: rutinas del día de los alumnos activos, en el día local del entrenador. */
export async function getTrainerDailyRoutines(date: string): Promise<DailyRoutineItem[]> {
  const { data } = await api.get<DailyRoutineItem[]>('/api/v1/trainers/me/daily-routines', {
    params: { date, utc_offset_minutes: -new Date(`${date}T12:00:00`).getTimezoneOffset() },
  });
  return data;
}

/** US-24: comparación de una sesión finalizada con lo planificado y con la sesión previa. */
export async function getSessionComparison(sessionId: string): Promise<SessionComparison> {
  const { data } = await api.get<SessionComparison>(`/api/v1/trainers/me/sessions/${sessionId}/comparison`);
  return data;
}

/** US-32: riesgo de abandono de los alumnos activos (en riesgo primero). */
export async function getAbandonmentRisk(): Promise<AbandonmentRiskItem[]> {
  const { data } = await api.get<AbandonmentRiskItem[]>('/api/v1/trainers/me/abandonment-risk');
  return data;
}

export async function getTrainingEvolution(
  studentId: string,
  params: { groupBy: EvolutionGrouping; period: EvolutionPeriod; muscleGroup?: string },
): Promise<TrainingEvolution> {
  const { data } = await api.get<TrainingEvolution>(`${STUDENTS_PATH}/${studentId}/evolution`, {
    params: { group_by: params.groupBy, period: params.period, muscle_group: params.muscleGroup || undefined },
  });
  return data;
}

/** US-35: da de baja al alumno con el motivo indicado (fecha local del entrenador). */
export async function terminateStudent(
  studentId: string,
  payload: StudentTerminationPayload,
): Promise<StudentTerminationResult> {
  const { data } = await api.post<StudentTerminationResult>(
    `${STUDENTS_PATH}/${encodeURIComponent(studentId)}/termination`,
    payload,
    { params: { date: localDateInputValue() } },
  );
  return data;
}
