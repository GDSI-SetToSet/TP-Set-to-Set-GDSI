import type { RoutineTemplate, RoutineTemplateInput } from './routineTemplate';

export interface StudentRoutineView {
  routine: RoutineTemplate;
  draft: RoutineTemplate | null;
  draft_version: number;
  desired_weekly_volume: number | null;
  status: 'ACTIVE' | 'DRAFT_PENDING';
}

export interface RoutineDraftInput extends RoutineTemplateInput {
  draft_version: number;
  desired_weekly_volume: number | null;
}
