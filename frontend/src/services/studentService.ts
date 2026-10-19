import { api } from './api';
import type { StudentProfile, StudentProfileUpdate } from '../types/student';

const PROFILE_PATH = '/api/v1/students/me/profile';

export async function getOwnStudentProfile(): Promise<StudentProfile> {
  const { data } = await api.get<StudentProfile>(PROFILE_PATH);
  return data;
}

export async function updateOwnStudentProfile(payload: StudentProfileUpdate): Promise<StudentProfile> {
  const { data } = await api.put<StudentProfile>(PROFILE_PATH, payload);
  return data;
}