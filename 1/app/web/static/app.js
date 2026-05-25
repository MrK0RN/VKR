document.addEventListener("DOMContentLoaded", () => {
  const alert = document.querySelector(".alert");
  if (alert) {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    alert.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "nearest" });
  }

  const form = document.querySelector(".survey-form");
  if (!form) return;

  form.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") {
      const submit = form.querySelector('button[type="submit"]');
      if (submit && document.activeElement !== submit) {
        e.preventDefault();
        submit.click();
      }
    }
  });
});
