export interface PlanFilterStudent {
  plan_id?: string | null;
  plan_title?: string | null;
}

export interface PlanFilterPlan {
  id: string;
  title: string;
  is_active: boolean;
}

export interface PlanFilterOption {
  plan_id: string;
  title: string;
  student_count: number;
}

export const ALL_PLANS: '';

export function buildPlanFilterOptions(
  students: PlanFilterStudent[],
  plans?: PlanFilterPlan[],
): PlanFilterOption[];

export function canFilterByPlan(options: PlanFilterOption[]): boolean;

export function filterStudentsByPlan<T extends PlanFilterStudent>(students: T[], planId: string): T[];
