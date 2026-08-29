// Mirrors the prediction form's current values into the sticky "specification sheet" panel.

(function () {
  const form = document.getElementById("predict-form");
  if (!form) return;

  const specEls = form.parentElement.querySelectorAll("[data-spec]");
  const specMap = {};
  specEls.forEach((el) => {
    specMap[el.dataset.spec] = el;
  });

  function fieldValue(name) {
    const el = form.querySelector(`[name="${name}"]`);
    if (!el) return "";
    if (el.tagName === "SELECT") {
      return el.options[el.selectedIndex] ? el.options[el.selectedIndex].text : "";
    }
    return el.value;
  }

  function update() {
    if (specMap.location) specMap.location.textContent = fieldValue("location") || "—";
    if (specMap.area_sqft) {
      const area = fieldValue("area_sqft");
      specMap.area_sqft.textContent = area ? `${area} sqft` : "—";
    }
    if (specMap.bhk) {
      const bhk = fieldValue("bhk");
      specMap.bhk.textContent = bhk ? `${bhk} BHK` : "—";
    }
    if (specMap.bathrooms) specMap.bathrooms.textContent = fieldValue("bathrooms") || "—";
    if (specMap.floor) {
      const floor = fieldValue("floor");
      const totalFloors = fieldValue("total_floors");
      specMap.floor.textContent = floor ? `${floor}${totalFloors ? " / " + totalFloors : ""}` : "—";
    }
    if (specMap.property_type) specMap.property_type.textContent = fieldValue("property_type") || "—";
    if (specMap.furnishing) specMap.furnishing.textContent = fieldValue("furnishing") || "—";
  }

  form.addEventListener("input", update);
  form.addEventListener("change", update);
  update();
})();
