import type {
  SafetyAlertAction,
  SafetyAlertReviewRequest,
  SafetyAlertType,
  SafetyAlertView,
  StudentPainAlertReviewedNotice,
} from '../types/safetyAlert';
import type { AbandonmentRiskItem } from '../types/trainerStudent';

export const SAFETY_ALERT_TYPE_LABELS: Record<SafetyAlertType, string>;
export const SAFETY_ALERT_ACTION_OPTIONS: Array<{ value: SafetyAlertAction; label: string }>;
export const SAFETY_ALERT_ACTION_LABELS: Record<SafetyAlertAction, string>;

export interface PendingAlertsSummary {
  count: number;
  latestCreatedAtMs: number;
  alerts: SafetyAlertView[];
}

export interface StudentSortCandidate {
  student_name?: string;
  full_name?: string;
  first_name?: string | null;
  last_name?: string | null;
}

export function compareStudentNamesAlphabetically(
  leftStudent: StudentSortCandidate | string,
  rightStudent: StudentSortCandidate | string,
): number;

export interface ScopedRequestTicket {
  requestId: number;
  scopeKey: string;
  isCurrent: (expectedScopeKey?: string) => boolean;
}

export interface ScopedRequestTracker {
  begin: (scopeKey?: string) => ScopedRequestTicket;
  invalidate: (scopeKey?: string) => void;
  isActive: () => boolean;
  dispose: () => void;
}

export function createScopedRequestTracker(): ScopedRequestTracker;

export function executeStudentDetailRequest<TDetail>(params: {
  studentId: string;
  tracker: ScopedRequestTracker;
  isSelectedStudent?: (studentId: string) => boolean;
  fetchDetail: (studentId: string) => Promise<TDetail>;
  onSuccess: (detail: TDetail) => void;
  onError?: (err: unknown) => void;
  onFinally?: () => void;
}): Promise<void>;

export function executeStudentSafetyAlertsRequest(params: {
  studentId: string;
  tracker: ScopedRequestTracker;
  isCurrentStudent?: (studentId: string) => boolean;
  fetchAlerts: (studentId: string) => Promise<SafetyAlertView[]>;
  onSuccess: (items: SafetyAlertView[]) => void;
  onError?: (err: unknown) => void;
  onFinally?: () => void;
}): Promise<void>;

export function runSafetyRefreshTransition<
  TStudent extends { relationship_id: string; student_id: string },
>(params: {
  safetyRefreshKey: number;
  openRelationshipId: string | null;
  students: TStudent[];
  globalTracker: ScopedRequestTracker;
  fetchPendingAlerts: () => Promise<SafetyAlertView[]>;
  onPendingSuccess: (alerts: SafetyAlertView[]) => void;
  onPendingError?: (err: unknown) => void;
  loadStudentAlerts: (studentId: string) => Promise<void> | void;
}): Promise<unknown>;

export function runOpenProgressSafetyTransition<
  TStudent extends { relationship_id: string; student_id: string },
>(params: {
  openRelationshipId: string | null;
  students: TStudent[];
  loadStudentAlerts: (studentId: string) => Promise<void> | void;
}): Promise<void>;

export function focusSafetyAlertsTransition<
  TStudent extends { relationship_id: string; student_id: string },
>(params: {
  student: TStudent;
  openRelationshipId: string | null;
  setOpenProgressFor: (relationshipId: string | null) => void;
  loadStudentAlerts: (studentId: string) => Promise<void> | void;
}): Promise<void>;

export function resolvePainAlertHighlightId(
  alerts?: SafetyAlertView[] | null,
  reportId?: string | null,
): string | null;

export function getReviewSubmitButtonState(
  alertId: string,
  selectedAction: SafetyAlertAction | '',
  submittingId: string | null,
): {
  disabled: boolean;
  isSubmittingCurrent: boolean;
  label: string;
};

export function executeAlertReviewSubmit(params: {
  alertId: string;
  actionTaken: SafetyAlertAction | '';
  trainerNote?: string;
  inFlightGuard: { current: boolean };
  isMounted: () => boolean;
  reviewAlert: (alertId: string, payload: SafetyAlertReviewRequest) => Promise<SafetyAlertView>;
  setSubmittingId: (alertId: string | null) => void;
  clearAlertError: (alertId: string) => void;
  setAlertError: (alertId: string, message: string) => void;
  onReviewed: (updatedAlert: SafetyAlertView) => void;
  onSuccessCleanup: (alertId: string) => void;
}): Promise<boolean>;

export function groupPendingAlertsByRelationship(
  alerts?: SafetyAlertView[],
): Map<string, PendingAlertsSummary>;

export function sortAssignmentsByPriority<
  T extends { relationship_id: string; student_name?: string },
>(
  students: T[],
  abandonmentRisks?: Pick<AbandonmentRiskItem, 'relationship_id' | 'at_risk' | 'days_without_report'>[],
  pendingAlerts?: SafetyAlertView[],
): T[];

export function formatSafetyAlertSummary(alert: SafetyAlertView | null | undefined): {
  typeLabel: string;
  detailText: string;
  statusLabel: string;
  actionLabel: string;
  note: string | null;
};

export function formatStudentPainReviewedNotice(
  notice: (StudentPainAlertReviewedNotice & { alert_type?: string }) | null | undefined,
): {
  id: string;
  title: string;
  contextText: string;
  actionLabel: string;
  trainerNote: string | null;
  reviewedAt: string;
} | null;
