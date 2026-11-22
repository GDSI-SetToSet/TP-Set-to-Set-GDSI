import { api } from './api';
import type {
  ConversationDetail,
  ConversationSummary,
  ExerciseQueryThread,
  MessageCreatePayload,
  MessageView,
  PendingQueriesGroup,
  TechnicalNoteView,
  TechnicalQueryPayload,
} from '../types/conversation';

const BASE = '/api/v1/conversations';

function conversationPath(relationshipId: string) {
  return `${BASE}/${encodeURIComponent(relationshipId)}`;
}

/** US-21: conversaciones del usuario autenticado (una por vínculo). */
export async function listConversations(): Promise<ConversationSummary[]> {
  const { data } = await api.get<ConversationSummary[]>(BASE);
  return data;
}

export async function getConversation(relationshipId: string): Promise<ConversationDetail> {
  const { data } = await api.get<ConversationDetail>(`${conversationPath(relationshipId)}/messages`);
  return data;
}

export async function sendMessage(relationshipId: string, payload: MessageCreatePayload): Promise<MessageView> {
  const { data } = await api.post<MessageView>(`${conversationPath(relationshipId)}/messages`, payload);
  return data;
}

export async function markConversationRead(relationshipId: string): Promise<void> {
  await api.post(`${conversationPath(relationshipId)}/read`);
}

/** US-62: consulta técnica del alumno sobre un ejercicio. */
export async function createTechnicalQuery(
  relationshipId: string,
  payload: TechnicalQueryPayload,
): Promise<MessageView> {
  const { data } = await api.post<MessageView>(`${conversationPath(relationshipId)}/technical-queries`, payload);
  return data;
}

export async function getExerciseQueries(relationshipId: string, exerciseId: string): Promise<ExerciseQueryThread[]> {
  const { data } = await api.get<ExerciseQueryThread[]>(
    `${conversationPath(relationshipId)}/exercises/${encodeURIComponent(exerciseId)}/technical-queries`,
  );
  return data;
}

export async function getPendingTechnicalQueries(): Promise<PendingQueriesGroup[]> {
  const { data } = await api.get<PendingQueriesGroup[]>('/api/v1/trainers/me/technical-queries');
  return data;
}

export async function getPendingTechnicalNotes(): Promise<TechnicalNoteView[]> {
  const { data } = await api.get<TechnicalNoteView[]>('/api/v1/students/me/technical-notes');
  return data;
}

export async function acknowledgeTechnicalNote(noteId: string, sessionId: string | null): Promise<TechnicalNoteView> {
  const { data } = await api.post<TechnicalNoteView>(
    `/api/v1/students/me/technical-notes/${encodeURIComponent(noteId)}/acknowledge`,
    { session_id: sessionId },
  );
  return data;
}
