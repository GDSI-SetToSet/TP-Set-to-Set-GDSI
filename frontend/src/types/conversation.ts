/** US-21 (mensajes entrenador–alumno) y US-62 (consultas técnicas). */

export type MessageKind = 'TEXT' | 'TECHNICAL_QUERY';
export type ConversationRole = 'TRAINER' | 'STUDENT';

export interface LastMessage {
  body: string;
  created_at: string;
  is_mine: boolean;
  kind: MessageKind;
}

export interface ConversationSummary {
  relationship_id: string;
  status: string;
  can_send: boolean;
  counterpart_name: string;
  counterpart_role: ConversationRole;
  trainer_id: string;
  student_id: string;
  plan_title: string | null;
  unread_count: number;
  last_message: LastMessage | null;
}

export interface MessageView {
  id: string;
  kind: MessageKind;
  body: string;
  sender_role: ConversationRole;
  sender_name: string;
  is_mine: boolean;
  created_at: string;
  read_at: string | null;
  exercise: { id: string | null; name: string } | null;
  session_id: string | null;
  set_number: number | null;
  reply_to_message_id: string | null;
  is_answered: boolean;
  technical_note: { id: string; acknowledged_at: string | null } | null;
}

export interface ConversationDetail {
  conversation: ConversationSummary;
  messages: MessageView[];
}

export interface PendingQueriesGroup {
  student_id: string;
  student_name: string;
  relationship_id: string;
  queries: MessageView[];
}

export interface ExerciseQueryThread {
  query: MessageView;
  replies: MessageView[];
}

export interface TrainerQueryHistoryGroup {
  student_id: string;
  student_name: string;
  relationship_id: string;
  threads: ExerciseQueryThread[];
}

export interface TechnicalNoteView {
  id: string;
  relationship_id: string;
  exercise_id: string | null;
  exercise_name: string;
  body: string;
  trainer_name: string;
  created_at: string;
  acknowledged_at: string | null;
}

export interface MessageCreatePayload {
  body: string;
  reply_to_message_id?: string | null;
  pin_as_technical_note?: boolean;
}

export interface TechnicalQueryPayload {
  exercise_id: string;
  body: string;
  session_id?: string | null;
  set_number?: number | null;
}
