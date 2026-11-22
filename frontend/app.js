const byId = (id) => document.getElementById(id);

const loginForm = byId("login-form");
const loginMessage = byId("login-message");
const uploadForm = byId("upload-form");
const uploadMessage = byId("upload-message");
const documentList = byId("document-list");
const reviewQueue = byId("review-queue");
const reviewMessage = byId("review-message");

const MAX_FILE_BYTES = 5 * 1024 * 1024;
let accessToken = "";
let listRequest = 0;

function showSignIn(message = "") {
  accessToken = "";
  listRequest += 1;
  loginForm.reset();
  byId("known-applications").replaceChildren();
  byId("admin-rows").replaceChildren();
  byId("admin-message").textContent = "";
  byId("admin-panel").hidden = true;
  byId("register-panel").hidden = true;
  byId("switch-account").hidden = true;
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
    byId("switch-account").hidden = false;
    byId("admin-panel").hidden = profile.role !== "Admin";
    byId("account-heading").textContent = profile.role + " workspace";
    byId("applicant-documents").hidden = profile.role !== "Applicant";
    byId("reviewer-panel").hidden = profile.role !== "Reviewer";
    byId("account-heading").focus();

    if (profile.role === "Applicant") await loadDocuments();
    if (profile.role === "Reviewer") await loadReviewQueue();
    if (profile.role === "Admin") await loadAdminUsers();
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
    const options = Array.from(new Set(documents.map(doc => doc.application_title))).map(title => {
      const option = document.createElement("option");
      option.value = title;
      return option;
    });
    byId("known-applications").replaceChildren(...options);
    documentList.replaceChildren();
    for (const doc of documents) {
      const item = document.createElement("li");
      const name = documentLabel(doc);
      const status = document.createElement("strong");
      status.textContent = doc.review_status;
      status.className = "badge " + doc.review_status.toLowerCase();
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
  if (!file || !/\.(pdf|jpe?g|png)$/i.test(file.name)) {
    uploadMessage.textContent = "Choose a PDF, JPG or PNG file.";
    return;
  }
  if (file.size > MAX_FILE_BYTES) {
    uploadMessage.textContent = "Choose a file of 5 MiB or less.";
    return;
  }

  const token = accessToken;
  const body = new FormData();
  const title = byId("application-title").value.trim();
  body.append("application", title);
  body.append("document_type", byId("document-type").value);
  body.append("notes", byId("document-notes").value);
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
    byId("application-title").value = title;
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
      const name = documentLabel(doc);

      const button = document.createElement("button");
      button.type = "button";
      button.textContent = "Open file";
      button.setAttribute("aria-label", "Open " + doc.original_filename);
      button.addEventListener("click", () => openReviewerPdf(doc.id));

      const actions = document.createElement("div");
      actions.className = "actions";
      actions.append(button);
      for (const decision of ["Approved", "Rejected"]) {
        const action = document.createElement("button");
        action.textContent = decision === "Approved" ? "Approve" : "Reject";
        action.className = decision === "Rejected" ? "reject" : "approve";
        action.addEventListener("click", () => decide(doc, decision, item));
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
    reviewMessage.textContent = "Allow pop-ups for DocVerify, then click Open file again.";
    return;
  }

  tab.opener = null;
  tab.document.title = "Opening file";
  tab.document.body.textContent = "Loading file…";
  reviewMessage.textContent = "";
  let pdfUrl;

  try {
    const response = await sessionFetch("/api/reviewer/documents/" + documentId + "/file", token, {
      headers: { Accept: "application/pdf, image/jpeg, image/png" },
    });
    if (!response || tab.closed) {
      tab.close();
      return;
    }
    if (!response.ok) throw new Error("Could not open the file (" + response.status + ").");

    const pdf = await response.blob();
    if (token !== accessToken || tab.closed) {
      tab.close();
      return;
    }
    if (!["application/pdf", "image/jpeg", "image/png"].includes(pdf.type.split(";")[0])) {
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
    if (token === accessToken) reviewMessage.textContent = error.message || "Could not open the file.";
  }
}

function documentLabel(doc) {
  const label = document.createElement("div");
  label.className = "doc";
  const filename = document.createElement("strong");
  filename.textContent = doc.original_filename;
  const owner = document.createElement("span");
  owner.className = "owner";
  owner.textContent = "Applicant: " + (doc.applicant_name || doc.applicant_email || "Name unavailable");
  const metadata = document.createElement("span");
  metadata.className = "owner";
  metadata.textContent = [doc.application_title, doc.document_type].join(" · ");
  label.append(filename, owner, metadata);
  if (doc.notes) {
    const notes = document.createElement("span");
    notes.textContent = doc.notes;
    label.append(notes);
  }
  return label;
}

async function decide(doc, decision, item) {
  if (!window.confirm('Set "' + doc.original_filename + '" to ' + decision + '? This decision is final.')) return;
  const token = accessToken;
  const buttons = item.querySelectorAll("button");
  buttons.forEach(button => { button.disabled = true; });
  try {
    const response = await sessionFetch("/api/reviewer/documents/" + doc.id + "/decision", token, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ decision }),
    });
    if (!response || token !== accessToken) return;
    if (!response.ok && response.status !== 409) throw new Error();
    item.remove();
    reviewMessage.textContent = response.ok
      ? doc.original_filename + ": " + decision + "."
      : "This submission was already reviewed.";
    if (!reviewQueue.children.length) reviewMessage.textContent += " No pending reviews.";
  } catch {
    if (token === accessToken) reviewMessage.textContent = "Could not confirm the decision. Check the queue before retrying.";
  } finally {
    buttons.forEach(button => { button.disabled = false; });
  }
}

async function loadAdminUsers() {
  const token = accessToken;
  const message = byId("admin-message");
  message.textContent = "Loading users…";
  try {
    const response = await sessionFetch("/api/admin/users", token);
    if (!response) return;
    if (!response.ok) throw new Error();
    const users = await response.json();
    if (token !== accessToken) return;
    const rows = byId("admin-rows");
    rows.replaceChildren();
    for (const user of users) {
      const row = rows.insertRow();
      for (const value of [user.id, user.email, user.role]) row.insertCell().textContent = value;
    }
    message.textContent = users.length ? "" : "No registered users.";
  } catch {
    if (token === accessToken) message.textContent = "Could not load the registered users.";
  }
}

const registerForm = byId("register-form");
byId("show-register").addEventListener("click", () => {
  registerForm.reset();
  byId("register-message").textContent = "";
  byId("register-email").value = byId("email").value.trim();
  byId("password").value = "";
  byId("login-panel").hidden = true;
  byId("register-panel").hidden = false;
  byId("register-name").focus();
});
byId("back-to-login").addEventListener("click", () => {
  registerForm.reset();
  showSignIn();
});
registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const email = byId("register-email").value.trim();
  const name = byId("register-name").value.trim();
  const message = byId("register-message");
  if (!name) {
    message.textContent = "Enter your name.";
    byId("register-name").focus();
    return;
  }
  byId("register-submit").disabled = true;
  byId("back-to-login").disabled = true;
  message.textContent = "Creating account…";
  try {
    const response = await fetch("/api/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, full_name: name, password: byId("register-password").value }),
    });
    if (!response.ok) {
      message.textContent = response.status === 409
        ? "This email is already registered. Sign in to continue."
        : "Could not register. Check your name, email and password.";
      return;
    }
    registerForm.reset();
    showSignIn("Account created. Sign in to continue.");
    byId("email").value = email;
    byId("password").focus();
  } catch {
    message.textContent = "Could not reach DocVerify.";
  } finally {
    byId("register-submit").disabled = false;
    byId("back-to-login").disabled = false;
  }
});
