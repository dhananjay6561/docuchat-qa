// Plain JS on purpose: no build step, and the DOM stays simple for Playwright/Appium to drive.
// Every element tests touch has a data-testid so tests don't break when styling changes.

const log = document.getElementById("log");
const form = document.getElementById("form");
const input = document.getElementById("input");
const send = document.getElementById("send");
const loading = document.getElementById("loading");
const errorBanner = document.getElementById("error");
const sessionLabel = document.querySelector("[data-testid=session-id]");

function newSessionId() {
  return "web-" + crypto.randomUUID().slice(0, 8);
}

let sessionId = sessionStorage.getItem("docuchat-session") || newSessionId();

function setSession(id) {
  sessionId = id;
  sessionStorage.setItem("docuchat-session", id);
  sessionLabel.textContent = id;
}

function addMessage(role, text) {
  const item = document.createElement("li");
  item.className = `msg msg--${role}`;
  item.dataset.testid = `message-${role}`;
  const body = document.createElement("p");
  body.textContent = text;
  item.appendChild(body);
  log.appendChild(item);
  log.scrollTop = log.scrollHeight;
  return item;
}

function addAssistantMessage(data) {
  const item = addMessage("assistant", data.answer);
  if (data.refused) {
    const badge = document.createElement("span");
    badge.className = "badge";
    badge.dataset.testid = "refusal-badge";
    badge.textContent = "Not in documents";
    item.appendChild(badge);
  }
  if (data.sources.length) {
    const list = document.createElement("ul");
    list.className = "sources";
    list.dataset.testid = "sources-list";
    for (const source of data.sources) {
      const li = document.createElement("li");
      li.dataset.testid = "source-item";
      li.title = source.snippet;
      li.textContent = source.chunk_id;
      list.appendChild(li);
    }
    item.appendChild(list);
  }
}

function showError(message) {
  errorBanner.textContent = message;
  errorBanner.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = input.value.trim();
  if (!message) return;

  errorBanner.hidden = true;
  addMessage("user", message);
  input.value = "";
  send.disabled = true;
  loading.hidden = false;

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, message }),
    });
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    addAssistantMessage(await response.json());
  } catch (err) {
    showError(`Something went wrong: ${err.message}. Please try again.`);
    // Give the message back so a retry is one click, unless they've already started typing.
    if (!input.value) input.value = message;
  } finally {
    send.disabled = false;
    loading.hidden = true;
    input.focus();
  }
});

document.getElementById("new-session").addEventListener("click", () => {
  log.innerHTML = "";
  errorBanner.hidden = true;
  setSession(newSessionId());
});

setSession(sessionId);
