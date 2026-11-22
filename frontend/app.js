const byId = (id) => document.getElementById(id);

const loginForm = byId("login-form");
const loginMessage = byId("login-message");
const uploadForm = byId("upload-form");
const uploadMessage = byId("upload-message");
const documentList = byId("document-list");
const reviewQueue = byId("review-queue");
const reviewMessage = byId("review-message");

const MAX_PDF_BYTES = 5 * 1024 * 1024;
let accessToken = "";
let listRequest = 0;

function showSignIn(message = "") {
  accessToken = "";
  listRequest += 1;
  loginForm.reset();
  uploadForm.reset();
  documentList.replaceChildren();
  reviewQueue.replaceChildren();
  byId("account-email").textContent = "";
  byId("account-role").textContent = "";
  byId("list-message").textContent = "";
  uploadMessage.textContent = "";
  reviewMessage.textContent = "";
  byId("upload-button").disabled = false;
  byId("applicant-documents").hidden = true;
  byId("reviewer-panel").hidden = true;
  byId("account-panel").hidden = true;
  byId("login-panel").hidden = false;
  loginMessage.textContent = message;
  byId("email").focus();
}

byId("switch-account").addEventListener("click", () => showSignIn());

async function sessionFetch(path, token, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...options.headers, Authorization: "Bearer " + token },
  });
  if (token !== accessToken) return null;
  if (response.status === 401) {
    showSignIn("Your session expired. Please sign in again.");
    return null;
  }
  return response;
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = byId("submit-button");
  button.disabled = true;
  loginMessage.textContent = "Signing in…";

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        email: byId("email").value.trim(),
        password: byId("password").value,
      }),
    });

    if (!response.ok) {
      loginMessage.textContent = response.status === 401
        ? "The email or password is incorrect."
        : "Sign-in is unavailable. Please try again.";
      return;
    }

    const session = await response.json();
    const profileResponse = await fetch("/api/me", {
      headers: { Authorization: "Bearer " + session.access_token },
    });
    if (!profileResponse.ok) {
      loginMessage.textContent = "Could not load your account. Please sign in again.";
      return;
    }

    const profile = await profileResponse.json();
    accessToken = session.access_token;
    byId("password").value = "";
    loginMessage.textContent = "";
    byId("account-email").textContent = profile.email;
    byId("account-role").textContent = profile.role;
    byId("login-panel").hidden = true;
    byId("account-panel").hidden = false;
    byId("applicant-documents").hidden = profile.role !== "Applicant";
    byId("reviewer-panel").hidden = profile.role !== "Reviewer";
    byId("account-heading").focus();

    if (profile.role === "Applicant") await loadDocuments();
    if (profile.role === "Reviewer") await loadReviewQueue();
  } catch {
    loginMessage.textContent = "Could not reach DocVerify. Check that Docker is running.";
  } finally {
    button.disabled = false;
  }
});

async function loadDocuments() {
  const token = accessToken;
  const request = ++listRequest;
  const message = byId("list-message");
  message.textContent = "Loading documents…";
  try {
    const response = await sessionFetch("/api/documents", token);
    if (!response || request !== listRequest) return;
    if (!response.ok) throw new Error();

    const documents = await response.json();
    if (request !== listRequest) return;
    documentList.replaceChildren();
    for (const doc of documents) {
      const item = document.createElement("li");
      const name = document.createElement("span");
      const status = document.createElement("strong");
      name.textContent = doc.original_filename;
      status.textContent = doc.review_status;
      item.append(name, " ", status);
      documentList.append(item);
    }
    message.textContent = documents.length ? "" : "You haven’t uploaded a document yet.";
  } catch {
    if (request === listRequest) message.textContent = "Could not load your documents.";
  }
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = byId("pdf-file").files[0];
  if (!file || !file.name.toLowerCase().endsWith(".pdf")) {
    uploadMessage.textContent = "Choose a PDF file.";
    return;
  }
  if (file.size > MAX_PDF_BYTES) {
    uploadMessage.textContent = "Choose a PDF of 5 MiB or less.";
    return;
  }

  const token = accessToken;
  const body = new FormData();
  body.append("file", file);
  byId("upload-button").disabled = true;
  uploadMessage.textContent = "Uploading…";

  try {
    const response = await sessionFetch("/api/documents", token, { method: "POST", body });
    if (!response) return;
    if (!response.ok) {
      const error = await response.json().catch(() => ({}));
      if (token === accessToken) {
        uploadMessage.textContent = typeof error.detail === "string"
          ? error.detail : "Upload failed (" + response.status + ").";
      }
      return;
    }
    uploadForm.reset();
    uploadMessage.textContent = file.name + " uploaded.";
    await loadDocuments();
  } catch {
    if (token === accessToken) {
      uploadMessage.textContent = "Connection interrupted. Check your list before uploading again.";
    }
  } finally {
    if (token === accessToken) byId("upload-button").disabled = false;
  }
});

async function loadReviewQueue() {
  const token = accessToken;
  reviewMessage.textContent = "Loading pending reviews…";
  try {
    const response = await sessionFetch("/api/reviewer/documents", token);
    if (!response) return;
    if (!response.ok) throw new Error();

    const documents = await response.json();
    if (token !== accessToken) return;
    reviewQueue.replaceChildren();
    for (const doc of documents) {
      const item = document.createElement("li");
      const name = document.createElement("span");
      name.textContent = doc.original_filename;

      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Open PDF";
      button.setAttribute("aria-label", "Open " + doc.original_filename);
      button.addEventListener("click", () => openReviewerPdf(doc.id));
const actions = document.createElement("div");
actions.className = "review-actions";
actions.append(button); // Existing Open PDF button

for (const decision of ["Approved", "Rejected"]) {
  const action = document.createElement("button");
  action.type = "button";
  action.textContent = decision === "Approved" ? "Approve" : "Reject";
  action.addEventListener("click", () => submitDecision(doc, decision, actions));
  actions.append(action);
}

item.append(name, actions);
      reviewQueue.append(item);
    }
    reviewMessage.textContent = documents.length ? "" : "No documents are awaiting review.";
  } catch {
    if (token === accessToken) reviewMessage.textContent = "Could not load the review queue.";
  }
}

async function openReviewerPdf(documentId) {
  const token = accessToken;
  const tab = window.open("about:blank", "_blank");
  if (!tab) {
    reviewMessage.textContent = "Allow pop-ups for DocVerify, then click Open PDF again.";
    return;
  }

  tab.opener = null;
  tab.document.title = "Opening PDF";
  tab.document.body.textContent = "Loading PDF…";
  reviewMessage.textContent = "";
  let pdfUrl;

  try {
    const response = await sessionFetch("/api/reviewer/documents/" + documentId + "/file", token, {
      headers: { Accept: "application/pdf" },
    });
    if (!response || tab.closed) {
      tab.close();
      return;
    }
    if (!response.ok) throw new Error("Could not open the PDF (" + response.status + ").");

    const pdf = await response.blob();
    if (token !== accessToken || tab.closed) {
      tab.close();
      return;
    }
    if (pdf.type.split(";")[0] !== "application/pdf") {
      throw new Error("The server returned an unexpected file type.");
    }

    pdfUrl = URL.createObjectURL(pdf);
    tab.location.replace(pdfUrl);
    const cleanup = window.setInterval(() => {
      if (tab.closed) {
        URL.revokeObjectURL(pdfUrl);
        window.clearInterval(cleanup);
      }
    }, 1000);
  } catch (error) {
    tab.close();
    if (pdfUrl) URL.revokeObjectURL(pdfUrl);
    if (token === accessToken) reviewMessage.textContent = error.message || "Could not open the PDF.";
  }
}

async function submitDecision(doc, decision, actions) {
  const verb = decision === "Approved" ? "Approve" : "Reject";
  if (!window.confirm(`${verb} "${doc.original_filename}"? This decision is final.`)) {
    return;
  }

  const token = accessToken;
  const buttons = actions.querySelectorAll("button");
  buttons.forEach((button) => { button.disabled = true; });
  reviewMessage.textContent = "Saving decision…";

  try {
    const response = await sessionFetch(
      `/api/reviewer/documents/${doc.id}/decision`,
      token,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ decision }),
      }
    );

    if (!response || token !== accessToken) return;

    if (response.ok || response.status === 409) {
      // Remove only this row so other pending documents stay available.
      actions.closest("li").remove();
      const result = response.ok
        ? `${doc.original_filename}: ${decision}.`
        : `${doc.original_filename} was already reviewed.`;
      reviewMessage.textContent = reviewQueue.children.length
        ? result
        : `${result} No documents are awaiting review.`;
      return;
    }

    reviewMessage.textContent = `Could not save the decision (${response.status}).`;
  } catch {
    if (token === accessToken) {
      reviewMessage.textContent =
        "Connection interrupted. Reload the queue to check whether the decision was saved.";
    }
  } finally {
    buttons.forEach((button) => { button.disabled = false; });
  }
}