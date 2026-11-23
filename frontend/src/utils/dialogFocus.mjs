/**
 * Resolves the focus target index when Tab or Shift+Tab is pressed on a dialog boundary,
 * accounting for radio button groups acting as a single tab stop.
 *
 * @param {Array<{ isRadio?: boolean, name?: string, checked?: boolean }>} items
 * @param {number} activeIndex
 * @param {boolean} shiftKey
 * @returns {number | null} Target index to focus, or null if default Tab behavior should continue.
 */
export function resolveDialogTabTarget(items, activeIndex, shiftKey) {
  if (!Array.isArray(items) || items.length === 0) return null;
  if (activeIndex < 0 || activeIndex >= items.length) {
    return shiftKey ? items.length - 1 : 0;
  }

  const current = items[activeIndex];
  const first = items[0];
  const last = items[items.length - 1];

  const firstGroupName = first.isRadio && first.name ? first.name : null;
  const lastGroupName = last.isRadio && last.name ? last.name : null;

  const isFirstTabStop =
    activeIndex === 0
    || Boolean(
      firstGroupName
      && current.isRadio
      && current.name === firstGroupName
      && items.slice(0, activeIndex).every((item) => item.isRadio && item.name === firstGroupName),
    );

  const isLastTabStop =
    activeIndex === items.length - 1
    || Boolean(
      lastGroupName
      && current.isRadio
      && current.name === lastGroupName
      && items.slice(activeIndex + 1).every((item) => item.isRadio && item.name === lastGroupName),
    );

  if (shiftKey && isFirstTabStop) {
    if (lastGroupName) {
      for (let i = items.length - 1; i >= 0; i -= 1) {
        const candidate = items[i];
        if (!candidate.isRadio || candidate.name !== lastGroupName) break;
        if (candidate.checked) return i;
      }
    }
    return items.length - 1;
  }

  if (!shiftKey && isLastTabStop) {
    if (firstGroupName) {
      for (let i = 0; i < items.length; i += 1) {
        const candidate = items[i];
        if (!candidate.isRadio || candidate.name !== firstGroupName) break;
        if (candidate.checked) return i;
      }
    }
    return 0;
  }

  return null;
}
