// Toggles the inline detail drawer for a history row, and caps comparison selection at 4 items.

(function () {
  document.querySelectorAll("[data-toggle]").forEach((row) => {
    row.addEventListener("click", () => {
      const target = document.getElementById(row.dataset.toggle);
      if (target) target.classList.toggle("hidden");
    });
  });

  const MAX_COMPARE = 4;
  const checkboxes = document.querySelectorAll(".compare-checkbox");

  function enforceLimit() {
    const checkedCount = Array.from(checkboxes).filter((c) => c.checked).length;
    const atLimit = checkedCount >= MAX_COMPARE;
    checkboxes.forEach((c) => {
      if (!c.checked) c.disabled = atLimit;
    });
  }

  checkboxes.forEach((c) => c.addEventListener("change", enforceLimit));
})();
