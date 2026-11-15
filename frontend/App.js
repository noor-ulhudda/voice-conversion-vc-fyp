// ====== CONFIG ======
// Change this to wherever your backend runs.
const API_URL = "http://localhost:8000";

// ====== STATE ======
const state = { gender: null, age: null, blob: null };

const AGES = {
  female: [
    { id: "kid", label: "Girl", note: "Child voice", emoji: "👧" },
    { id: "adult", label: "Woman", note: "Mid-aged voice", emoji: "👩" },
    { id: "old", label: "Older woman", note: "Elderly voice", emoji: "👵" },
  ],
  male: [
    { id: "kid", label: "Boy", note: "Child voice", emoji: "👦" },
    { id: "adult", label: "Man", note: "Mid-aged voice", emoji: "👨" },
    { id: "old", label: "Older man", note: "Elderly voice", emoji: "👴" },
  ],
};

const $ = (s) => document.querySelector(s);

// ====== NAVIGATION ======
function show(id) {
  document.querySelectorAll(".view").forEach((v) => v.classList.toggle("active", v.id === id));
  closeMenu();
  window.scrollTo(0, 0);
}

document.addEventListener("click", (e) => {
  const go = e.target.closest("[data-go]");
  if (go) {
    e.preventDefault();
    show(go.dataset.go);
  }
  if (!e.target.closest(".menu-wrap")) closeMenu();
});

// ====== MENU ======
const menuBtn = $("#menuBtn");
const menu = $("#menu");
function closeMenu() {
  menu.hidden = true;
  menuBtn.setAttribute("aria-expanded", "false");
}
menuBtn.addEventListener("click", () => {
  const open = menu.hidden;
  menu.hidden = !open;
  menuBtn.setAttribute("aria-expanded", String(open));
});

// ====== GENDER -> AGE ======
document.querySelectorAll("[data-gender]").forEach((btn) => {
  btn.addEventListener("click", () => {
    state.gender = btn.dataset.gender;
    $("#ageTitle").textContent =
      state.gender === "female" ? "Which female voice?" : "Which male voice?";
    $("#ageChoices").innerHTML = AGES[state.gender]
      .map(
        (a) =>
          `<button class="choice" data-age="${a.id}">
             <span class="emoji">${a.emoji}</span>${a.label}<small>${a.note}</small>
           </button>`
      )
      .join("");
    show("age");
  });
});

$("#ageChoices").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-age]");
  if (!btn) return;
  state.age = btn.dataset.age;
  const a = AGES[state.gender].find((x) => x.id === state.age);
  $("#targetLabel").textContent = `Target voice: ${a.label} (${a.note.toLowerCase()})`;
  resetRecording();
  show("record");
});

// ====== RECORDING ======
let recorder, stream, chunks = [], tick, startedAt;
const recBtn = $("#recBtn");
const statusEl = $("#recStatus");

function setStatus(msg, isError = false) {
  statusEl.textContent = msg;
  statusEl.classList.toggle("error", isError);
}

function resetRecording() {
  state.blob = null;
  $("#player").hidden = true;
  $("#player").removeAttribute("src");
  $("#result").hidden = true;
  $("#convertBtn").disabled = true;
  $("#timer").textContent = "00:00";
  setStatus("Press the button to start recording.");
}

function fmt(ms) {
  const s = Math.floor(ms / 1000);
  return String(Math.floor(s / 60)).padStart(2, "0") + ":" + String(s % 60).padStart(2, "0");
}

async function startRecording() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    setStatus("Microphone blocked. Allow microphone access in your browser and try again.", true);
    return;
  }
  resetRecording();
  chunks = [];
  recorder = new MediaRecorder(stream);
  recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
  recorder.onstop = () => {
    state.blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
    const player = $("#player");
    player.src = URL.createObjectURL(state.blob);
    player.hidden = false;
    $("#convertBtn").disabled = false;
    setStatus("Recording saved. Press the button to record again, or convert.");
    stream.getTracks().forEach((t) => t.stop());
  };
  recorder.start();
  startedAt = Date.now();
  tick = setInterval(() => ($("#timer").textContent = fmt(Date.now() - startedAt)), 250);
  recBtn.classList.add("recording");
  recBtn.setAttribute("aria-label", "Stop recording");
  setStatus("Recording… press the button to stop.");
}

function stopRecording() {
  clearInterval(tick);
  recorder.stop();
  recBtn.classList.remove("recording");
  recBtn.setAttribute("aria-label", "Start recording");
}

recBtn.addEventListener("click", () => {
  if (recorder && recorder.state === "recording") stopRecording();
  else startRecording();
});

// ====== CONVERT ======
$("#convertBtn").addEventListener("click", async () => {
  if (!state.blob) return;
  const btn = $("#convertBtn");
  btn.disabled = true;
  setStatus("Converting…");

  const form = new FormData();
  form.append("audio", state.blob, "recording.webm");
  form.append("gender", state.gender);
  form.append("age", state.age);

  try {
    const res = await fetch(`${API_URL}/convert`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`Server returned ${res.status}`);
    const out = await res.blob(); // backend should return the converted audio file
    $("#resultPlayer").src = URL.createObjectURL(out);
    $("#result").hidden = false;
    setStatus("Done.");
  } catch (err) {
    setStatus("Could not reach the backend yet. Your recording is saved and ready to send.", true);
    console.error(err);
  }
  btn.disabled = false;
});

// ====== LOGIN / SIGN UP (UI only, connect to backend later) ======
let authMode = "login";
document.querySelectorAll("[data-auth]").forEach((tab) => {
  tab.addEventListener("click", () => {
    authMode = tab.dataset.auth;
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    const label = authMode === "login" ? "Log in" : "Sign up";
    $("#authTitle").textContent = label;
    $("#authSubmit").textContent = label;
    $("#authMsg").textContent = "";
  });
});

$("#authSubmit").addEventListener("click", async () => {
  const email = $("#email").value.trim();
  const password = $("#password").value;
  const msg = $("#authMsg");
  if (!email || !password) {
    msg.textContent = "Enter your email and password.";
    msg.classList.add("error");
    return;
  }
  try {
    const res = await fetch(`${API_URL}/auth/${authMode}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    if (!res.ok) throw new Error();
    msg.classList.remove("error");
    msg.textContent = "Success.";
    setTimeout(() => show("home"), 600);
  } catch {
    msg.classList.add("error");
    msg.textContent = "Login isn't connected to a backend yet.";//kg
  }
});