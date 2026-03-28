document.addEventListener("DOMContentLoaded", () => {
  const countryDatalist = document.getElementById("country-options");
  const countryField = document.querySelector('input[data-country-field="true"]');
  const referenceShell = document.getElementById("site-reference-shell");
  const referenceLabel = document.getElementById("site-reference-label");
  const referenceInput = document.getElementById("site-reference-value");
  const referenceHelp = document.getElementById("site-reference-help");
  const referenceSpecsNode = document.getElementById("country-reference-specs");

  let referenceSpecs = {};
  if (referenceSpecsNode?.textContent) {
    try {
      referenceSpecs = JSON.parse(referenceSpecsNode.textContent);
    } catch {
      referenceSpecs = {};
    }
  }

  if (countryDatalist && countryField) {
    const allowedCountries = new Set(
      Array.from(countryDatalist.querySelectorAll("option"))
        .map((option) => option.value.trim())
        .filter(Boolean),
    );

    const validateCountry = () => {
      const value = countryField.value.trim();
      if (!value || allowedCountries.has(value)) {
        countryField.setCustomValidity("");
        return;
      }
      countryField.setCustomValidity("Select a valid country from the list.");
    };

    countryField.addEventListener("input", validateCountry);
    countryField.addEventListener("change", validateCountry);
    countryField.addEventListener("blur", validateCountry);
    validateCountry();
  }

  if (!countryField || !referenceShell || !referenceLabel || !referenceInput || !referenceHelp) {
    return;
  }

  let lastReferenceCountry = null;

  const renderReferenceField = () => {
    const country = countryField.value.trim();
    const spec = referenceSpecs[country];

    if (!spec) {
      if (lastReferenceCountry && lastReferenceCountry !== country) {
        referenceInput.value = "";
      }
      referenceShell.hidden = true;
      referenceInput.disabled = true;
      referenceInput.placeholder = "";
      referenceInput.setCustomValidity("");
      referenceHelp.textContent = "";
      lastReferenceCountry = null;
      return;
    }

    if (lastReferenceCountry && lastReferenceCountry !== country) {
      referenceInput.value = "";
    }

    referenceShell.hidden = false;
    referenceInput.disabled = false;
    referenceInput.placeholder = spec.placeholder || "";
    referenceLabel.textContent = `${spec.label} (optional)`;
    referenceHelp.textContent = spec.help_text || "";
    referenceInput.setCustomValidity("");
    lastReferenceCountry = country;
  };

  countryField.addEventListener("input", renderReferenceField);
  countryField.addEventListener("change", renderReferenceField);
  countryField.addEventListener("blur", renderReferenceField);
  renderReferenceField();
});
