import { type RefObject, useEffect, useRef } from 'react';
import { resolveDialogTabTarget } from '../utils/dialogFocus.mjs';

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/** Foco inicial, foco atrapado con Tab y cierre con Escape para un diálogo modal. */
export function useDialogFocus(ref: RefObject<HTMLElement | null>, onClose: () => void, disabled = false) {
  // Refs para que el efecto corra solo al montar: si dependiera de onClose, cada render
  // del padre devolvería el foco al primer campo mientras el usuario escribe.
  const onCloseRef = useRef(onClose);
  const disabledRef = useRef(disabled);
  onCloseRef.current = onClose;
  disabledRef.current = disabled;

  useEffect(() => {
    const root = ref.current;
    if (!root) return undefined;
    const previouslyFocused = document.activeElement as HTMLElement | null;
    const first = root.querySelector<HTMLElement>('[data-autofocus]') ?? root.querySelector<HTMLElement>(FOCUSABLE);
    first?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (!root) return;
      if (event.key === 'Escape' && !disabledRef.current) {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== 'Tab') return;
      const items = Array.from(root.querySelectorAll<HTMLElement>(FOCUSABLE));
      if (items.length === 0) return;
      const activeElement = document.activeElement as HTMLElement | null;
      const activeIndex = activeElement ? items.indexOf(activeElement) : -1;
      const targetIndex = resolveDialogTabTarget(
        items.map((element) => (
          element instanceof HTMLInputElement && element.type === 'radio'
            ? { isRadio: true, name: element.name, checked: element.checked }
            : {}
        )),
        activeIndex,
        event.shiftKey,
      );
      if (targetIndex !== null) {
        event.preventDefault();
        items[targetIndex].focus();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      if (previouslyFocused?.isConnected) previouslyFocused.focus();
    };
  }, [ref]);
}
