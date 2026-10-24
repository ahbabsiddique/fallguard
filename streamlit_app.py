import html, os, time
import altair as alt
import pandas as pd
import streamlit as st

st.set_page_config(page_title="FallGuard", layout="wide")
conn = st.connection("snowflake", ttl=os.getenv("SNOWFLAKE_CONNECTION_TTL"))
session = conn.session()
ss = st.session_state

MODEL = "llama3.1-70b"
EMAIL = "caregiver@example.com"
EMERGENCY_NUMBER = "911"
DEMO_MODE = True  # True: simulate the call. False: route to the monitoring-center integration.

# ---------- Fresh board on Run / reload; keep state only for in-app clicks ----------
STATE_KEYS = ("status_html", "alert_html", "esc_html", "summary", "answer", "last_q",
              "sig_activity", "sig_state", "progress", "q")

def mark_interaction():
    ss["_interacted"] = True

if not ss.pop("_interacted", False):
    for k in STATE_KEYS:
        ss.pop(k, None)

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');
html, body, [class*="css"], .stMarkdown, button, input { font-family: 'Inter', sans-serif !important; }
.block-container { padding-top: 2rem; max-width: 1200px; }
header, footer, #MainMenu { visibility: hidden; }
.fg-head { display:flex; justify-content:space-between; align-items:flex-end; border-bottom:1px solid #D7E7E4; padding-bottom:16px; margin-bottom:24px; }
.fg-brand { font-size:22px; font-weight:600; letter-spacing:-0.02em; color:#0F766E; }
.fg-sub { font-size:13px; color:#5B7B78; margin-top:2px; }
.fg-meta { font-family:'JetBrains Mono', monospace; font-size:11px; color:#5B7B78; text-align:right; line-height:1.7; }
.fg-label { font-size:11px; font-weight:500; letter-spacing:0.08em; text-transform:uppercase; color:#5B7B78; margin-bottom:8px; }
.fg-card { background:#FFFFFF; border:1px solid #D7E7E4; border-radius:10px; padding:18px 20px; margin-bottom:14px; }
.fg-kpi { font-size:22px; font-weight:600; color:#0B3B3C; letter-spacing:-0.01em; }
.fg-status { font-size:34px; font-weight:600; letter-spacing:-0.02em; color:#0B3B3C; margin-top:4px; }
.fg-time { font-family:'JetBrains Mono', monospace; font-size:12px; color:#5B7B78; }
.fg-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:8px; vertical-align:middle; }
.fg-bar { height:3px; background:#E6F4F1; border-radius:2px; margin-top:12px; }
.fg-bar > div { height:3px; background:#0F766E; border-radius:2px; }
.fg-alert { border-left:3px solid #E0533D; background:#FFF7F5; } .fg-alert .fg-label { color:#E0533D; }
.fg-esc { border-left:3px solid #A12C1B; background:#FBEFEC; } .fg-esc .fg-label { color:#A12C1B; }
.fg-body { font-size:15px; line-height:1.6; color:#0B3B3C; }
.fg-mono { font-family:'JetBrains Mono', monospace; font-size:11px; color:#5B7B78; margin-top:12px; }
.fg-row { display:flex; justify-content:space-between; padding:7px 0; border-bottom:1px solid #E6F4F1; font-size:14px; color:#0B3B3C; }
.fg-legend { display:flex; gap:18px; flex-wrap:wrap; margin-top:2px; }
.fg-swatch { display:inline-block; width:10px; height:10px; border-radius:2px; margin-right:6px; vertical-align:middle; }
.fg-sig { font-size:15px; font-weight:600; color:#0B3B3C; margin-bottom:8px; }
</style>""", unsafe_allow_html=True)

h = html.escape
DOMAIN = ["Walk", "Lie Down", "Sit Down", "Stand Up", "Pick Up", "Run", "Fall"]
PALETTE = ["#0F766E", "#C9E8E3", "#5FB3A8", "#2A9D8F", "#99D6CF", "#0B3B3C", "#E0533D"]
STATE_COLOR = {"ok": "#2A9D8F", "down": "#F08A72", "fall": "#E0533D"}
STATE_TEXT = {"ok": "Normal", "down": "Not recovered", "fall": "Fall detected"}

def card(label, body, cls=""):
    return f'<div class="fg-card {cls}"><div class="fg-label">{label}</div>{body}</div>'

def kpi(label, value, sub):
    return card(label, f'<div class="fg-kpi">{value}</div><div class="fg-time" style="margin-top:4px">{sub}</div>')

def waiting_html():
    return card("Current activity",
        '<div class="fg-status" style="color:#99D6CF">Waiting for data</div>'
        '<div class="fg-time" style="margin-top:6px">Replay today to stream readings</div>')

def status_html(ts, activity, conf, state):
    return card("Current activity",
        f'<div class="fg-time"><span class="fg-dot" style="background:{STATE_COLOR[state]}"></span>'
        f'{ts:%I:%M %p} · {STATE_TEXT[state]}</div>'
        f'<div class="fg-status">{h(activity.title())}</div>'
        f'<div class="fg-time" style="margin-top:6px">Model confidence {conf:.0%}</div>'
        f'<div class="fg-bar"><div style="width:{conf * 100:.0f}%"></div></div>')

def counts_html(sub):
    if sub.empty:
        return card("Detected today", '<div class="fg-time">No readings yet</div>')
    rows = "".join(f'<div class="fg-row"><span>{h(a.title())}</span><span class="fg-time">{n} min</span></div>'
                   for a, n in sub.ACTIVITY.value_counts().items())
    return card("Detected today", rows)

def log_of(sub):
    return ", ".join(f"{t:%H:%M} {a}" for t, a in zip(sub.TS, sub.ACTIVITY))

def ask(prompt):
    p = prompt.replace("'", "''")
    out = session.sql(f"SELECT AI_COMPLETE('{MODEL}', '{p}')::STRING").collect()[0][0]
    out = out.strip().strip('"').replace("\\n", "\n").strip()
    lines = [l.strip() for l in out.split("\n") if l.strip()]
    if len(lines) > 1 and lines[0].endswith(":"):
        lines = lines[1:]
    return " ".join(lines)

def send_email(subject, body):
    try:
        s, b = subject.replace("'", "''"), body.replace("'", "''")
        session.sql(f"CALL SYSTEM$SEND_EMAIL('fallguard_email', '{EMAIL}', '{s}', '{b}')").collect()
        st.toast(f"Email sent: {subject}")
    except Exception as e:
        st.toast(f"Email failed: {e}")

def emergency_call(fall_ts, reason):
    mode = "SIMULATED" if DEMO_MODE else "LIVE"
    r = reason.replace("'", "''")
    session.sql(
        "INSERT INTO FALLGUARD.APP.ESCALATIONS (FALL_TS, TARGET, REASON, MODE) "
        f"VALUES ('{fall_ts:%Y-%m-%d %H:%M:%S}', '{EMERGENCY_NUMBER}', '{r}', '{mode}')").collect()
    if DEMO_MODE:
        return f"Call to {EMERGENCY_NUMBER} · simulated for demo · logged in FALLGUARD.APP.ESCALATIONS"
    # Production: hand off to a monitoring-center / telephony API here.
    return f"Call to {EMERGENCY_NUMBER} · placed · logged in FALLGUARD.APP.ESCALATIONS"

@st.cache_data
def load():
    return session.sql("SELECT * FROM FALLGUARD.APP.ACTIVITY_LOG ORDER BY TS").to_pandas()

df = load()
T0 = df.TS.min().floor("h")
T1 = (df.TS.max() + pd.Timedelta(minutes=1)).ceil("30min")

def adt(t):
    return alt.DateTime(year=t.year, month=t.month, date=t.day, hours=t.hour, minutes=t.minute)

def timeline_chart(sub):
    tl = pd.DataFrame({
        "START": sub.TS.dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "END": (sub.TS + pd.Timedelta(minutes=1)).dt.strftime("%Y-%m-%dT%H:%M:%S"),
        "LABEL": sub.ACTIVITY.str.title(),
        "ROW": "Bedroom",
    })
    return (alt.Chart(tl).mark_bar(size=26).encode(
            x=alt.X("START:T", title=None, scale=alt.Scale(domain=[adt(T0), adt(T1)]),
                    axis=alt.Axis(format="%H:%M", grid=False, labelColor="#5B7B78",
                                  domainColor="#D7E7E4", tickColor="#D7E7E4")),
            x2="END:T",
            y=alt.Y("ROW:N", title=None, axis=None),
            color=alt.Color("LABEL:N", scale=alt.Scale(domain=DOMAIN, range=PALETTE), legend=None),
            tooltip=[alt.Tooltip("START:T", format="%H:%M", title="Time"), alt.Tooltip("LABEL:N", title="Activity")])
        .properties(height=40).configure_view(strokeWidth=0))

# ---------- Page layout (rendered first) ----------
st.markdown(
    '<div class="fg-head"><div><div class="fg-brand">FallGuard</div>'
    '<div class="fg-sub">Privacy-first fall detection from Wi-Fi signals. No cameras, no wearables.</div></div>'
    f'<div class="fg-meta">BEDROOM · WI-FI CSI · {df.TS.min():%b %d, %Y}<br>'
    f'SNOWFLAKE AI_COMPLETE · {MODEL.upper()}</div></div>', unsafe_allow_html=True)

k1, k2, k3, k4 = st.columns(4)
k1.markdown(kpi("Room", "Bedroom", "Single occupant"), unsafe_allow_html=True)
k2.markdown(kpi("Sensor", "Wi-Fi CSI", "3 antennas · 30 subcarriers"), unsafe_allow_html=True)
k3.markdown(kpi("Fall detection", "84%", "Test accuracy · UT-HAR"), unsafe_allow_html=True)
k4.markdown(kpi("Escalation rule", "5 min", "No recovery after a fall"), unsafe_allow_html=True)

left, right = st.columns([2, 1], gap="large")

with left:
    status = st.empty()
    alert_box = st.empty()
    esc_box = st.empty()
    replay = st.button("Replay today", type="primary", on_click=mark_interaction)
    if replay:
        for k in STATE_KEYS:
            if k != "q":
                ss.pop(k, None)
        ss.progress = 0
    status.markdown(ss.get("status_html", waiting_html()), unsafe_allow_html=True)
    if "alert_html" in ss:
        alert_box.markdown(ss.alert_html, unsafe_allow_html=True)
    if "esc_html" in ss:
        esc_box.markdown(ss.esc_html, unsafe_allow_html=True)

progress = ss.get("progress", 0)
seen = df.iloc[:progress]

with right:
    counts_box = st.empty()
    counts_box.markdown(counts_html(seen), unsafe_allow_html=True)
    st.markdown('<div class="fg-label">Live signal</div>', unsafe_allow_html=True)
    sig_label = st.empty()
    sig_img = st.empty()
    st.caption("Representative Wi-Fi CSI for the detected activity: signal strength across 90 "
               "subcarrier channels over time. No images, no faces, no identity.")

def show_signal(activity, state):
    if not activity:
        sig_label.markdown('<div class="fg-time" style="margin-bottom:8px">No signal yet</div>',
                           unsafe_allow_html=True)
        sig_img.empty()
        return
    sig_label.markdown(
        f'<div class="fg-sig"><span class="fg-dot" style="background:{STATE_COLOR[state]}"></span>'
        f'{h(activity.title())}</div>', unsafe_allow_html=True)
    path = f"signals/{activity.replace(' ', '_')}.png"
    if os.path.exists(path):
        sig_img.image(path)

show_signal(ss.get("sig_activity"), ss.get("sig_state", "ok"))

st.markdown('<div class="fg-label" style="margin-top:24px">Timeline</div>', unsafe_allow_html=True)
tl_box = st.empty()
tl_box.altair_chart(timeline_chart(seen), width="stretch")
st.markdown('<div class="fg-legend">' + "".join(
    f'<span class="fg-time"><span class="fg-swatch" style="background:{c}"></span>{n}</span>'
    for n, c in zip(DOMAIN, PALETTE)) + '</div>', unsafe_allow_html=True)

b1, b2 = st.columns(2, gap="large")
with b1:
    st.markdown('<div class="fg-label" style="margin-top:24px">Daily summary</div>', unsafe_allow_html=True)
    if st.button("Generate summary", on_click=mark_interaction):
        if seen.empty:
            ss["summary"] = "No readings yet. Replay today first."
        else:
            with st.spinner("Summarizing"):
                ss["summary"] = ask("Summarize this elderly person's day so far for a caregiver in 3 short sentences "
                                    "(activity level, rest periods, any incidents). Refer to her as Grandma. "
                                    f"Reply with only the summary, no preamble: {log_of(seen)}")
    if "summary" in ss:
        st.markdown(card("Summary", f'<div class="fg-body">{h(ss["summary"])}</div>'), unsafe_allow_html=True)
with b2:
    st.markdown('<div class="fg-label" style="margin-top:24px">Ask about today</div>', unsafe_allow_html=True)
    q = st.text_input("Question", key="q", placeholder="How long was she lying down after the fall?",
                      label_visibility="collapsed", on_change=mark_interaction)
    if q and ss.get("last_q") != q and not replay:
        if seen.empty:
            ss["answer"] = "No readings yet. Replay today first."
        else:
            with st.spinner("Answering"):
                ss["answer"] = ask("You answer a caregiver's questions about an elderly person, Grandma, using only this "
                                   f"activity log (one entry per minute): {log_of(seen)}. Question: {q}. "
                                   "Answer in 1 to 3 sentences, plainly, no preamble.")
        ss["last_q"] = q
    if "answer" in ss:
        st.markdown(card("Answer", f'<div class="fg-body">{h(ss["answer"])}</div>'), unsafe_allow_html=True)

# ---------- Replay (runs last, streams into the placeholders above) ----------
if replay:
    fall_ts, escalated = None, False
    for i, (_, r) in enumerate(df.iterrows()):
        ss.progress = i + 1
        sub = df.iloc[:i + 1]
        state = "fall" if r.IS_FALL else ("down" if fall_ts is not None else "ok")
        ss.status_html = status_html(r.TS, r.ACTIVITY, r.CONFIDENCE, state)
        status.markdown(ss.status_html, unsafe_allow_html=True)
        counts_box.markdown(counts_html(sub), unsafe_allow_html=True)
        tl_box.altair_chart(timeline_chart(sub), width="stretch")
        if r.ACTIVITY != ss.get("sig_activity") or state != ss.get("sig_state"):
            ss.sig_activity, ss.sig_state = r.ACTIVITY, state
            show_signal(r.ACTIVITY, state)
        if r.IS_FALL:
            window = df[(df.TS >= r.TS - pd.Timedelta(minutes=10)) & (df.TS <= r.TS)]
            alert_box.markdown(card(f"Fall detected · {r.TS:%I:%M %p}",
                '<div class="fg-body">Generating caregiver alert...</div>', "fg-alert"), unsafe_allow_html=True)
            msg = ask(
                "You are FallGuard, a privacy-preserving Wi-Fi fall detection system for elderly care. "
                f"A fall was just detected in the Bedroom at {r.TS:%I:%M %p}. Activity log leading up to it: {log_of(window)}. "
                "Write a calm, clear 2-sentence alert for a family caregiver about their grandmother: "
                "what happened, what she was doing before, and what to do now. "
                "Reply with only the alert text, no preamble, no quotes. Do not mention confidence scores.")
            ss.alert_html = card(f"Fall detected · {r.TS:%I:%M %p}",
                f'<div class="fg-body">{h(msg)}</div><div class="fg-mono">Caregiver notified by email</div>',
                "fg-alert")
            alert_box.markdown(ss.alert_html, unsafe_allow_html=True)
            send_email("FallGuard: Fall detected", msg)
            fall_ts = r.TS
            time.sleep(2)
        elif fall_ts is not None and not escalated:
            if r.ACTIVITY in ("stand up", "walk"):
                fall_ts = None
            elif (r.TS - fall_ts).total_seconds() >= 300:
                escalated = True
                esc_text = (f"No recovery detected for 5 minutes since the fall at {fall_ts:%I:%M %p}. "
                            "Escalating to emergency services and notifying the caregiver.")
                call_status = emergency_call(fall_ts, esc_text)
                ss.esc_html = card(f"Escalated · {r.TS:%I:%M %p}",
                    f'<div class="fg-body">{h(esc_text)}</div><div class="fg-mono">{h(call_status)}</div>',
                    "fg-esc")
                esc_box.markdown(ss.esc_html, unsafe_allow_html=True)
                send_email("URGENT: FallGuard escalation", f"{esc_text}\n{call_status}")
                time.sleep(2)
        time.sleep(0.25)
