import { api } from './api';
import type { ProtectedZonesResponse, StudentProfile, StudentProfileUpdate } from '../types/student';

const PROFILE_PATH = '/api/v1/students/me/profile';

export async function getOwnStudentProfile(): Promise<StudentProfile> {
  const { data } = await api.get<StudentProfile>(PROFILE_PATH);
  return data;
}

export async function updateOwnStudentProfile(payload: StudentProfileUpdate): Promise<StudentProfile> {
  const { data } = await api.put<StudentProfile>(PROFILE_PATH, payload);
  return data;
}

const PROTECTED_ZONES_PATH = '/api/v1/students/me/protected-zones';

export async function getOwnProtectedZones(): Promise<ProtectedZonesResponse> {
  const { data } = await api.get<ProtectedZonesResponse>(PROTECTED_ZONES_PATH);
  return data;
}

export async function updateOwnProtectedZones(zones: string[]): Promise<ProtectedZonesResponse> {
  const { data } = await api.put<ProtectedZonesResponse>(PROTECTED_ZONES_PATH, { zones });
  return data;
}