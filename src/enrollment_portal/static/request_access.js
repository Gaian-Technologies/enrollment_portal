document.addEventListener("DOMContentLoaded", () => {
  const datalist = document.getElementById("country-options");
  if (!datalist) {
    return;
  }

  const allowedCountries = new Set(
    Array.from(datalist.querySelectorAll("option"))
      .map((option) => option.value.trim())
      .filter(Boolean),
  );

  for (const input of document.querySelectorAll('input[data-country-field="true"]')) {
    const validate = () => {
      const value = input.value.trim();
      if (!value || allowedCountries.has(value)) {
        input.setCustomValidity("");
        return;
      }
      input.setCustomValidity("Select a valid country from the list.");
    };

    input.addEventListener("input", validate);
    input.addEventListener("change", validate);
    input.addEventListener("blur", validate);
  }
});
