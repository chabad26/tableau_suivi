function toggleEmail(button) {
  const item = button.closest(".email-item");
  item.classList.toggle("open");
}

document.querySelectorAll("[data-job-title]").forEach((button) => {
  button.addEventListener("click", () => {
    const input = document.getElementById("job_title");
    input.value = button.dataset.jobTitle;
    input.focus();
    input.dispatchEvent(new Event("input", { bubbles: true }));
  });
});
