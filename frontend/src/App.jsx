import { useEffect, useRef, useState } from "react";

const API = "http://127.0.0.1:5000/api";
const emptyProfile = { name: "", phone: "", email: "", staffId: "", department: "", position: "" };
const initialState = { profile: null, inAt: null, outAt: null, lastEvent: null, totalMinutes: 0 };

const initials = (name) => name.trim().split(/\s+/).map((part) => part[0]).slice(0, 2).join("").toUpperCase();
const asUtc = (value) => value && !/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? `${value}Z` : value;
const time = (value) => value ? new Date(asUtc(value)).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "--:--";
const duration = (minutes) => `${Math.floor(minutes / 60)}h ${minutes % 60}m`;
const minutesBetween = (start, end) => start && end ? Math.max(0, Math.round((new Date(asUtc(end)) - new Date(asUtc(start))) / 60000)) : 0;

function FaceScan({ open, onClose, onVerified }) {
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const videoRef = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    let stream;
    let timer;
    setDone(false);
    setError("");
    navigator.mediaDevices.getUserMedia({ video: true }).then((camera) => {
      stream = camera;
      videoRef.current.srcObject = camera;
      timer = setTimeout(() => {
        const canvas = document.createElement("canvas");
        canvas.width = videoRef.current.videoWidth;
        canvas.height = videoRef.current.videoHeight;
        canvas.getContext("2d").drawImage(videoRef.current, 0, 0);
        setDone(true);
        onVerified(canvas.toDataURL("image/jpeg", 0.85));
      }, 1800);
    }).catch(() => setError("Camera access is required for face verification."));
    return () => { clearTimeout(timer); stream?.getTracks().forEach((track) => track.stop()); };
  }, [open, onVerified]);
  if (!open) return null;
  return <div className="overlay" onClick={onClose} role="dialog" aria-modal="true">
    <div className="modal" onClick={(event) => event.stopPropagation()}>
      <div className={`scan ${done ? "complete" : ""}`}><video ref={videoRef} autoPlay muted playsInline />{done ? "✓" : <span className="scan-line" />}</div>
      <h2>{done ? "Verification successful" : "Scanning face..."}</h2>
      <p>{error || (done ? "Your face was sent for verification." : "Hold still while we check your face.")}</p>
      <strong>{done ? "Verified" : "Scanning"}</strong>
    </div>
  </div>;
}

function Setup({ initial, onSave, onCancel }) {
  const [values, setValues] = useState(initial || emptyProfile);
  const [errors, setErrors] = useState({});
  const [scanOpen, setScanOpen] = useState(false);
  const [enrolled, setEnrolled] = useState(Boolean(initial));
  const update = (key) => (event) => setValues({ ...values, [key]: event.target.value });
  const submit = (event) => {
    event.preventDefault();
    const next = {};
    if (!values.name.trim()) next.name = "Your name is required";
    if (!values.phone.trim()) next.phone = "Phone number is required";
    if (!values.email.trim()) next.email = "Work email is required";
    if (!values.staffId.trim()) next.staffId = "Staff ID is required";
    setErrors(next);
    if (!Object.keys(next).length && enrolled) onSave(values);
  };
  const field = (key, label, type = "text") => <label className="field">{label}<input type={type} value={values[key]} onChange={update(key)} placeholder={label} />{errors[key] && <small>{errors[key]}</small>}</label>;
  return <form onSubmit={submit}>
    <p className="eyebrow">PUNCH ACCESS MANAGEMENT</p>
    <h1>{initial ? "Edit my details" : "Welcome to Punch Access Management"}</h1>
    <p className="lede">{initial ? "Keep your attendance profile up to date." : "Set up your profile to start tracking attendance."}</p>
    {field("name", "Full name")}{field("phone", "Phone number")}{field("email", "Work email", "email")}{field("staffId", "Staff ID")}{field("department", "Department")}{field("position", "Position")}
    <section className="face-panel"><div><b>{enrolled ? "Face registered" : "Register your face"}</b><p>{enrolled ? "Your face will confirm each punch." : "Complete one scan before saving your details."}</p></div><button type="button" className="button soft" onClick={() => setScanOpen(true)}>◎ {enrolled ? "Scan again" : "Face scan"}</button></section>
    <div className="actions"><button className="button primary" disabled={!enrolled}>Save details</button>{onCancel && <button type="button" className="button ghost" onClick={onCancel}>Cancel</button>}</div>
    <FaceScan open={scanOpen} onClose={() => setScanOpen(false)} onVerified={async (image) => {
      try {
        const response = await fetch(`${API}/register`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ employee_code: values.staffId, full_name: values.name, department: values.department, position: values.position, image }) });
        const result = await response.json();
        if (!response.ok) throw new Error(result.error || "Registration failed.");
        setEnrolled(true);
      } catch (registrationError) { setErrors({ face: registrationError.message }); }
      setTimeout(() => setScanOpen(false), 700);
    }} />
    {errors.face && <p className="server-error">{errors.face}</p>}
  </form>;
}

export default function App() {
  const [state, setState] = useState(() => JSON.parse(localStorage.getItem("pam-state") || "null") || initialState);
  const [editing, setEditing] = useState(false);
  const [notice, setNotice] = useState("");
  const [pending, setPending] = useState(null);
  useEffect(() => localStorage.setItem("pam-state", JSON.stringify(state)), [state]);
  useEffect(() => {
    if (!state.profile?.staffId) return;
    fetch(`${API}/attendance/status?employee_code=${encodeURIComponent(state.profile.staffId)}`)
      .then((response) => response.ok ? response.json() : Promise.reject())
      .then((attendanceState) => setState((current) => ({ ...current, ...attendanceState })))
      .catch(() => setNotice("Could not load attendance status."));
  }, [state.profile?.staffId]);
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => setNotice(""), 3200); return () => clearTimeout(timer); }, [notice]);
  const verify = async (image) => {
    const event = pending === "in" ? "IN" : "OUT";
    let response;
    let result;
    try {
      response = await fetch(`${API}/attendance`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event, image, employee_code: state.profile.staffId }) });
      result = await response.json();
    } catch {
      setNotice("The recognition API is not available.");
      return;
    }
    if (!response.ok) { setNotice(result.error || "Attendance action failed."); return; }
    const timestamp = result.timestamp;
    const identity = `${result.employee.name} (${result.employee.distance.toFixed(2)})`;
    if (event === "IN") { setState({ ...state, inAt: timestamp, outAt: null, lastEvent: "in" }); setNotice(`${identity} verified — punched in`); }
    else { setState({ ...state, outAt: timestamp, lastEvent: "out", totalMinutes: state.totalMinutes + minutesBetween(state.inAt, timestamp) }); setNotice(`${identity} verified — punched out`); }
    setTimeout(() => setPending(null), 700);
  };
  return <div className="app"><header><div className="brand-mark">PAM</div><div><b>Punch Access Management</b><span>{state.profile?.name || "My attendance"}</span></div></header>{notice && <div className="toast">{notice}</div>}<main>{!state.profile || editing ? <Setup initial={state.profile} onCancel={state.profile ? () => setEditing(false) : null} onSave={(profile) => { setState({ ...state, profile }); setEditing(false); setNotice("Details saved"); }} /> : <Dashboard state={state} setEditing={setEditing} setPending={setPending} />}</main><FaceScan open={Boolean(pending)} onClose={() => setPending(null)} onVerified={verify} /></div>;
}

function Dashboard({ state, setEditing, setPending }) {
  const isIn = state.lastEvent === "in";
  const current = state.totalMinutes + (isIn ? minutesBetween(state.inAt, new Date().toISOString()) : 0);
  return <><div className="profile-head"><div className="avatar">{initials(state.profile.name)}</div><div><p className="eyebrow">EMPLOYEE PROFILE</p><h1>{state.profile.name}</h1><p className="muted">{state.profile.staffId}</p></div><span className={`status ${isIn ? "in" : "out"}`}>{isIn ? "In" : "Out"}</span></div><div className="details"><span>✉ {state.profile.email}</span><span>☎ {state.profile.phone}</span></div><section className="summary"><div><span className="muted">TODAY</span><strong>{duration(current)}</strong></div><div><span className="muted">LAST PUNCH IN</span><strong>{time(state.inAt)}</strong></div><div><span className="muted">LAST PUNCH OUT</span><strong>{time(state.outAt)}</strong></div></section><div className="punches"><button className="button primary" disabled={isIn} onClick={() => setPending("in")}>↪ Punch in</button><button className="button danger" disabled={!state.lastEvent} onClick={() => setPending("out")}>↩ Punch out</button></div><button className="edit" onClick={() => setEditing(true)}>Edit my details →</button></>;
}
