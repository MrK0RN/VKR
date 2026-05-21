document.addEventListener("DOMContentLoaded", () => {
  const alert = document.querySelector(".alert");
  if (alert) {
    alert.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
});
