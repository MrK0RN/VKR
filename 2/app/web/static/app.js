document.addEventListener("DOMContentLoaded", () => {
  const alert = document.querySelector(".alert");
  if (alert) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    alert.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
  }

  document.querySelectorAll(".exclusive-group").forEach((fieldset) => {
    const radios = fieldset.querySelectorAll('input[type="radio"]');
    radios.forEach((radio) => {
      radio.addEventListener("change", () => {
        fieldset.classList.toggle("has-value", Boolean(fieldset.querySelector('input[type="radio"]:checked:not([value=""])') ));
      });
    });
  });
});
