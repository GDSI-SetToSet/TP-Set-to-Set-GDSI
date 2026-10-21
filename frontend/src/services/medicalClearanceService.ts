import axios from 'axios';
import { api } from './api';
import type { MedicalClearance } from '../types/student';

const ME_PATH = '/api/v1/students/me/medical-clearance';

export async function getOwnMedicalClearance(): Promise<MedicalClearance | null> {
  try {
    const { data } = await api.get<MedicalClearance>(ME_PATH);
    return data;
  } catch (caught) {
    if (axios.isAxiosError(caught) && caught.response?.status === 404) return null;
    throw caught;
  }
}

export async function uploadMedicalClearance(file: File, issueDate: string): Promise<MedicalClearance> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('issue_date', issueDate);

  const { data } = await api.post<MedicalClearance>(ME_PATH, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return data;
}

export async function downloadMedicalClearance(studentId: string, filename: string): Promise<void> {
  const downloadUrl = `/api/v1/students/${studentId}/medical-clearance/download`;
  const response = await api.get<Blob>(downloadUrl, {
    responseType: 'blob',
  });
  const headerType = response.headers['content-type'];
  const mimeType = typeof headerType === 'string' ? headerType : 'application/octet-stream';
  const blob = new Blob([response.data], { type: mimeType });
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  window.URL.revokeObjectURL(objectUrl);
}
