# VisionQuantech n8n Automation Pack — v1

Three real, working, independently-sellable n8n workflows. Built and tested on
n8n 1.83.2 (instance: n8n-1-83-2-pmw1.onrender.com).

## The three products

### 1. Instant Lead Responder — Demo (`vq-lead-responder-demo.json`)
- **What:** Website form lead (POST webhook) → auto-qualifies HOT/WARM/COLD by
  scoring keywords + contact completeness → returns a personalised instant reply
  as JSON.
- **Needs:** NOTHING. Zero credentials, zero API keys. Works the second it is
  activated.
- **Use:** Live demo for prospects — "yeh dekho, abhi test karke dikhata hoon."

### 2. Instant Lead Responder — Pro (`vq-lead-responder-pro.json`)
- **What:** Same qualification engine + sends the instant reply to the lead by
  Gmail + logs every lead as a row in a Google Sheet (name, phone, email,
  service, score, tier, reply sent, next action).
- **Needs:** One Google OAuth credential inside n8n (5-minute setup, buyer's own
  Google account) + a blank Google Sheet with a tab named `Leads`.
- **Use:** The actual paid deployment for clinics, hotels, real-estate.

### 3. Appointment Booker + Reminders (`vq-booking-plus-reminders.json`)
- **What:** Booking form (POST webhook: name, phone, email, service, date,
  time) → creates a Google Calendar event → sends confirmation email →
  responds instantly → waits until 24h before → sends reminder email.
- **Needs:** Same one Google OAuth credential (Calendar + Gmail).
- **Use:** Clinics ("appointment booking + patient reminders"), hotels, salons,
  consultants.

## Suggested pricing (matches current pitches)
- Demo: free, shown live on calls.
- Pro setup (workflow 2 or 3, deployed on client's n8n or ours): Starter
  **₹25,000** / Growth **₹45,000** one-time — same slabs as the AI-agent pitches.
- Optional care plan: **₹4,999/month** (monitoring + tweaks).

## Honest notes
- n8n shows a "critical update available → 1.121.0+" banner. Updating needs a
  Render redeploy (Render dashboard) — not done; workflows target 1.83.2.
- Render free tier sleeps when idle: first webhook hit after sleep takes
  ~30–60s to wake. For production client use, recommend Render paid or any
  always-on host.
- The 24h reminder uses n8n's Wait node; long waits resume after restarts.
- The second n8n instance (automation-832k) is currently locked (saved password
  rejected, no SMTP for reset) — everything runs on the working instance.
