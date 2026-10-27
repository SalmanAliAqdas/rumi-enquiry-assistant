"use strict";

const csrf = document.querySelector('meta[name="csrf-token"]').content;

async function sendJSON(url, method, body) {
  const response = await fetch(url, {
    method,
    headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf},
    body: JSON.stringify(body),
    credentials: "same-origin",
  });
  const data = await response.json();
  if (!response.ok) {
    if (Array.isArray(data.detail)) {
      throw new Error(data.detail.map(item => `${item.loc.at(-1)}: ${item.msg}`).join(". "));
    }
    throw new Error(data.detail || "Could not complete the request. Please try again.");
  }
  return data;
}

const enquiryForm = document.querySelector("#enquiry-form");
if (enquiryForm) {
  // One key per page submission; retain it during network retries.
  const submissionKey = crypto.randomUUID();
  let pending = false;
  const message = document.querySelector("#message");
  message.addEventListener("input", () => {
    document.querySelector("#character-count").textContent = `${message.value.length} / 3000`;
  });
  enquiryForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (pending) return;
    pending = true;
    const button = enquiryForm.querySelector('button[type="submit"]');
    const feedback = document.querySelector("#form-feedback");
    button.disabled = true;
    button.textContent = "Saving your enquiry…";
    feedback.textContent = "";
    try {
      const fields = Object.fromEntries(new FormData(enquiryForm));
      const data = await sendJSON("/api/enquiries", "POST", {...fields, submission_key: submissionKey});
      document.querySelector("#receipt-reference").textContent = data.reference;
      enquiryForm.hidden = true;
      document.querySelector("#form-title").hidden = true;
      const receipt = document.querySelector("#receipt");
      receipt.hidden = false;
      receipt.focus();
    } catch (error) {
      feedback.textContent = error.message || "Connection failed. Retry to safely check your submission.";
      feedback.classList.add("error");
      pending = false;
      button.disabled = false;
      button.textContent = "Submit enquiry ↗";
    }
  });
}

// Empty query options are omitted so FastAPI can validate optional enums.
const filters = document.querySelector(".filters");
if (filters) filters.addEventListener("submit", () => {
  filters.querySelectorAll("select").forEach(select => { if (!select.value) select.disabled = true; });
});

const draftForm = document.querySelector("#draft-form");
if (draftForm) {
  const draft = document.querySelector("#reply_draft");
  const feedback = document.querySelector("#draft-feedback");
  draftForm.addEventListener("submit", async event => {
    event.preventDefault();
    const button = draftForm.querySelector('button[type="submit"]');
    button.disabled = true;
    feedback.textContent = "Saving…";
    try {
      const data = await sendJSON(`/api/admin/enquiries/${draftForm.dataset.enquiryId}`, "PATCH", Object.fromEntries(new FormData(draftForm)));
      document.querySelector("#updated-at").textContent = data.updated_at;
      feedback.textContent = "Changes saved. Reply remains a draft.";
      feedback.classList.remove("error");
    } catch (error) {
      feedback.textContent = error.message;
      feedback.classList.add("error");
    } finally { button.disabled = false; }
  });
  document.querySelector("#copy-draft").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(draft.value);
      feedback.textContent = "Draft copied. Review it before sending outside this app.";
    } catch {
      draft.focus();
      draft.select();
      feedback.textContent = "Select and copy the draft using Ctrl+C (or Command+C).";
    }
  });
}
