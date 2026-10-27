"use strict";

const csrf = document.querySelector('meta[name="csrf-token"]').content;

async function sendJSON(url, method, body) {
  let response;
  try {
    response = await fetch(url, {
      method,
      headers: {"Content-Type": "application/json", "X-CSRF-Token": csrf},
      body: JSON.stringify(body), credentials: "same-origin",
    });
  } catch {
    throw new Error("Connection interrupted. Your form is preserved; retry to check safely.");
  }
  let data;
  try { data = await response.json(); }
  catch { throw new Error("The server could not complete this request. Keep your edits and try again."); }
  if (!response.ok) {
    if (response.status === 401) throw new Error("Your session has expired. Keep a copy of your edits, then sign in again.");
    if (Array.isArray(data.detail)) {
      const labels = {name: "Name", email: "Email", message: "Message", reply_draft: "Reply draft"};
      throw new Error(data.detail.map(item => `${labels[item.loc.at(-1)] || item.loc.at(-1)}: ${item.msg}`).join(". "));
    }
    throw new Error(data.detail || "Could not complete the request. Please try again.");
  }
  return data;
}

function busy(form, value) {
  form.setAttribute("aria-busy", String(value));
  form.querySelectorAll("button").forEach(button => { button.disabled = value; });
}

const enquiryForm = document.querySelector("#enquiry-form");
if (enquiryForm) {
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
    busy(enquiryForm, true);
    button.textContent = "Saving your enquiry…";
    feedback.textContent = "Please wait for your receipt. You can retry safely if the connection fails.";
    feedback.classList.remove("error");
    try {
      const fields = Object.fromEntries(new FormData(enquiryForm));
      const data = await sendJSON("/api/enquiries", "POST", {...fields, submission_key: submissionKey});
      document.querySelector("#receipt-reference").textContent = data.reference;
      enquiryForm.hidden = true;
      document.querySelector("#form-title").hidden = true;
      document.querySelector("#form-instructions").hidden = true;
      const receipt = document.querySelector("#receipt");
      receipt.hidden = false;
      receipt.focus();
    } catch (error) {
      feedback.textContent = error.message;
      feedback.classList.add("error");
      pending = false;
      busy(enquiryForm, false);
      button.textContent = "Submit enquiry ↗";
    }
  });
}

// Native form posts also prevent accidental repeated clicks.
document.querySelectorAll("[data-single-submit]").forEach(form => {
  form.addEventListener("submit", event => {
    if (draftDirty) {
      event.preventDefault();
      document.querySelector("#draft-feedback").textContent = "Save your draft changes before signing out.";
      return;
    }
    if (form.getAttribute("aria-busy") === "true") { event.preventDefault(); return; }
    busy(form, true);
    form.querySelector("button").textContent = "Please wait…";
  });
});
window.addEventListener("pageshow", event => {
  if (event.persisted) window.location.reload();
});

const filters = document.querySelector(".filters");
if (filters) filters.addEventListener("submit", () => {
  filters.querySelectorAll("select").forEach(select => { if (!select.value) select.disabled = true; });
});

const draftForm = document.querySelector("#draft-form");
let draftDirty = false;
let actionPending = false;
if (draftForm) {
  const draft = document.querySelector("#reply_draft");
  const status = document.querySelector("#workflow_status");
  const feedback = document.querySelector("#draft-feedback");
  const state = document.querySelector("#draft-state");
  draftForm.addEventListener("input", () => {
    draftDirty = true;
    state.textContent = "Unsaved changes · save before applying a candidate or leaving";
  });
  window.addEventListener("beforeunload", event => {
    if (draftDirty) { event.preventDefault(); event.returnValue = ""; }
  });
  draftForm.addEventListener("submit", async event => {
    event.preventDefault();
    if (actionPending) return;
    actionPending = true;
    const body = {...Object.fromEntries(new FormData(draftForm))};
    if (draftForm.dataset.revision !== undefined) body.expected_revision = Number(draftForm.dataset.revision);
    busy(draftForm, true);
    draft.readOnly = true;
    status.disabled = true;
    feedback.textContent = "Saving changes…";
    try {
      const data = await sendJSON(`/api/admin/enquiries/${draftForm.dataset.enquiryId}`, "PATCH", body);
      document.querySelector("#updated-at").textContent = data.updated_at;
      document.querySelector("#saved-workflow").textContent = data.workflow_status;
      if (data.processing_status === "Completed" && !data.candidate) {
        document.querySelector("#next-step-text").textContent = data.workflow_status === "Closed"
          ? "This enquiry is closed. No reply has been sent by this application."
          : "Review the saved draft and sources before copying. Nothing has been sent.";
      }
      draftForm.dataset.revision = data.draft_revision;
      const apply = document.querySelector("#apply-candidate");
      if (apply) apply.dataset.revision = data.draft_revision;
      draftDirty = false;
      state.textContent = "Saved draft · not sent";
      feedback.textContent = "Changes saved. Reply remains a draft.";
      feedback.classList.remove("error");
    } catch (error) {
      feedback.textContent = error.message;
      feedback.classList.add("error");
    } finally {
      actionPending = false;
      busy(draftForm, false);
      draft.readOnly = false;
      status.disabled = false;
    }
  });
  document.querySelector("#copy-draft").addEventListener("click", async () => {
    if (actionPending) return;
    actionPending = true;
    const button = document.querySelector("#copy-draft");
    button.disabled = true;
    feedback.classList.remove("error");
    try {
      await navigator.clipboard.writeText(draft.value);
      feedback.textContent = draftDirty
        ? "Current draft copied, including unsaved edits. Nothing was sent."
        : "Saved draft copied. Review it before sending outside this app.";
    } catch {
      draft.focus(); draft.select();
      feedback.textContent = "Clipboard unavailable. Copy the selected draft using Ctrl+C (or Command+C).";
    } finally { actionPending = false; button.disabled = false; }
  });
}

for (const [id, action, feedbackId] of [
  ["retry-processing", "retry", "processing-feedback"],
  ["apply-candidate", "apply-candidate", "candidate-feedback"],
]) {
  const button = document.getElementById(id);
  if (!button) continue;
  button.addEventListener("click", async () => {
    const feedback = document.getElementById(feedbackId);
    if (actionPending) return;
    if (draftDirty) {
      feedback.textContent = "Save your draft changes before processing or applying a candidate.";
      return;
    }
    actionPending = true;
    button.disabled = true;
    if (draftForm) busy(draftForm, true);
    if (draftForm) draftForm.querySelectorAll("textarea,select").forEach(input => { input.disabled = true; });
    feedback.textContent = action === "retry"
      ? "Processing… Your saved draft is preserved. A successful retry creates a separate candidate."
      : "Applying the reviewed candidate… Workflow status will be preserved.";
    try {
      const body = action === "retry" ? {} : {
        candidate_id: button.dataset.candidateId, draft_revision: Number(button.dataset.revision),
      };
      await sendJSON(`/api/admin/enquiries/${button.dataset.enquiryId}/${action}`, "POST", body);
      window.location.reload();
    } catch (error) {
      feedback.textContent = error.message;
      feedback.classList.add("error");
      actionPending = false;
      button.disabled = false;
      if (draftForm) {
        busy(draftForm, false);
        draftForm.querySelectorAll("textarea,select").forEach(input => { input.disabled = false; });
      }
    }
  });
}
