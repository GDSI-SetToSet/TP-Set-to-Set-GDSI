export interface FocusableDescriptor {
  isRadio?: boolean;
  name?: string;
  checked?: boolean;
}

export function resolveDialogTabTarget(
  items: FocusableDescriptor[],
  activeIndex: number,
  shiftKey: boolean,
): number | null;
