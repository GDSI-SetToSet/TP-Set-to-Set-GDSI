import { type RefObject, useEffect, useRef } from 'react';

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
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      if (event.shiftKey && document.activeElement === firstItem) {
        event.preventDefault();
        lastItem.focus();
      } else if (!event.shiftKey && document.activeElement === lastItem) {
        event.preventDefault();
        firstItem.focus();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      previouslyFocused?.focus?.();
    };
  }, [ref]);
}
