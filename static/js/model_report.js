// Client-side sort for the model comparison table -- no re-fetch, the rows already carry
// their metric values as data attributes.

(function () {
  const table = document.getElementById("model-comparison-table");
  if (!table) return;

  const tbody = table.querySelector("tbody");
  const headers = table.querySelectorAll("th[data-sort]");
  let currentSort = { key: null, dir: 1 };

  headers.forEach((th) => {
    th.addEventListener("click", () => {
      const key = th.dataset.sort;
      const dir = currentSort.key === key ? -currentSort.dir : 1;
      currentSort = { key, dir };

      const rows = Array.from(tbody.querySelectorAll("tr[data-model_name]"));
      rows.sort((a, b) => {
        const av = a.dataset[key];
        const bv = b.dataset[key];
        const an = Number(av);
        const bn = Number(bv);
        const cmp = Number.isNaN(an) || Number.isNaN(bn) ? String(av).localeCompare(String(bv)) : an - bn;
        return cmp * dir;
      });
      rows.forEach((row) => tbody.appendChild(row));
    });
  });
})();
