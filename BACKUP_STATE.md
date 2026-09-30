# n8n Automations — Backup & State Record

**Purpose:** The Render-hosted n8n has no persistent disk. If the instance restarts / the session
expires, everything inside n8n can vanish. This file + the local JSONs are the source of truth.
Re-import from here — never rebuild from scratch.

## Live instance (working)
- URL: https://n8n-1-83-2-pmw1.onrender.com/
- n8n version: 1.83.2 (update to 1.121.0+ available — NOT applied; needs Render access)
- Owner: Shivam Kumar (account created 2026-09-27, password in Secure Vault)
- Note: editor shows webhook URLs as `http://localhost:5678/...` because the `WEBHOOK_URL`
  env var is unset on Render. The REAL public URL is
  `https://n8n-1-83-2-pmw1.onrender.com/webhook/<path>` — verified live with curl on 2026-09-27.

## Workflows (live state as of 2026-09-27)
| # | Workflow name in n8n | Local file | Webhook path | Public URL | State |
|---|----------------------|-----------|--------------|-----------|-------|
| 1 | VQ Instant Lead Responder — Demo | workflows/vq-lead-responder-demo.json | lead-in | https://n8n-1-83-2-pmw1.onrender.com/webhook/lead-in | ACTIVE |
| 2 | VQ Instant Lead Responder — Pro (Gmail + Sheets) | workflows/vq-lead-responder-pro.json | lead-in-pro | https://n8n-1-83-2-pmw1.onrender.com/webhook/lead-in-pro | INACTIVE (needs Google OAuth) |
| 3 | VQ Appointment Booker + Reminders | workflows/vq-booking-plus-reminders.json | booking-in | https://n8n-1-83-2-pmw1.onrender.com/webhook/booking-in | INACTIVE (needs Google OAuth) |

## Fix history
- 2026-09-27: live test proved the n8n Webhook node nests the POST body under `json.body`.
  First line of the Code nodes fixed in all 3 workflows (local files + live n8n):
  `const data/d = ($input.first().json.body || $input.first().json)` shape guard.
- 2026-09-27: Demo FULLY verified LIVE on the public URL (after Code-node fix):
  HOT payload → HTTP 200, tier HOT, score 99, name/phone/email captured, correct
  PRIORITY reply. COLD payload → HTTP 200, tier COLD, score 30, correct reply.
  Note: first request after idle took ~37s (Render free-tier cold start), next 0.7s.

## Re-import (after a wipe)
1. Log in to https://n8n-1-83-2-pmw1.onrender.com/
2. For each file in `workflows/`: Workflows → ⋯ → Import from File → Save.
   (Import may name it "My workflow" — rename via the title field to the name in the table.)
3. Activate ONLY "VQ Instant Lead Responder — Demo". Leave Pro + Booking INACTIVE until Google OAuth is configured.
4. Verify: `curl -X POST https://n8n-1-83-2-pmw1.onrender.com/webhook/lead-in -H 'Content-Type: application/json' -d @dist-payload` — expect `tier` in the JSON reply.

## Pitch-faithful workflows (built 2026-09-27 from actual pitch promises)
Instance #1 (n8n 2.9.4) — all 3 imported, Published, ZERO node warnings:
- "VQ AI Enquiry Agent - Instant Responder" — https://automation-832k.onrender.com/webhook/enquiry-in
  (pitch: "answers every enquiry instantly, qualifies intent — 24/7")
- "VQ Smart Booking Agent" — https://automation-832k.onrender.com/webhook/agent-booking
  (pitch: "books the viewing/appointment — 24/7" + "sends reminders")
- "VQ After-Hours Lead Catcher" — https://automation-832k.onrender.com/webhook/missed-call
  (pitch: "No missed leads after hours")
LIVE verified 2026-09-27 (6/6 curl tests, all HTTP 200): booking intent + complaint→priority;
valid booking→confirmed w/ ref + 24h reminder; past date→rejected w/ fix hint;
after-hours miss→text-back + next-morning callback (high); in-hours miss→15-min callback.
All credential-free. Zips in dist/ (each with workflow.json + README + payloads + protocol.md).

## Sellable packages (independent, one zip per workflow)
- dist/vq-lead-responder-demo.zip — no credentials needed
- dist/vq-lead-responder-pro.zip — needs Google OAuth (Gmail + Sheets)
- dist/vq-booking-plus-reminders.zip — needs Google OAuth (Calendar + Gmail)
Each zip: workflow.json + README.md (setup) + test payload JSONs + protocol.md
(universal guide: inside-node JSON/methods/logic, why each approach, alternatives,
n8n-as-backend frontend contract; master at ~/workspace/n8n-automations/protocol.md).
New pitch-faithful zips: dist/vq-ai-enquiry-agent.zip, dist/vq-smart-booking-agent.zip,
dist/vq-afterhours-catcher.zip — all credential-free.

## Second instance (recovered 2026-09-27)
- https://automation-832k.onrender.com — login now WORKS (account "shivam").
- n8n version: 2.9.4 (much newer than instance #2's 1.83.2). Help menu shows an update available; NOT applied.
- Workflows (imported + verified 2026-09-27): all 3 imported with ZERO errors/warnings on Demo.
  - "VQ Instant Lead Responder — Demo" = Published (active). Production URL shown correctly as
    https://automation-832k.onrender.com/webhook/lead-in (this n8n sets the public domain properly).
  - Pro + Booking = inactive (credential warnings only — Google OAuth pending).
- LIVE verified 2026-09-27: HOT → tier HOT / score 99 / HTTP 200; COLD → tier COLD / score 30 / HTTP 200.
- Note: n8n 2.x uses "Publish" instead of the old Active toggle.

## Dead instance — RESOLVED, see "Second instance" above.

## 2026-09-27 — Batch 3: full pitch coverage (21 workflows)
- Re-read actual pitch files (pitch-variants-by-service.md + pitches-2026-09-25.md).
- Found 3 MORE agent types promised in vertical pitches: AI support agent (SaaS:
  triage tickets by urgency, escalate), AI SDR agent (agency: sub-minute follow-up,
  qualify fit, book meetings), AI document agent (ops: extract+validate+route).
- Built 10 new credential-free workflows (all locally logic-tested, incl. 3 bug
  fixes: money regex, IST slots, DD/MM/YYYY parsing):
  vq-whatsapp-agent, vq-email-agent, vq-ai-calling-agent (TwiML IVR, dynamic
  Gather URL from request host), vq-reminder-sender (Wait-until-time),
  vq-website-lead-capture, vq-support-triage-agent, vq-sdr-agent,
  vq-document-agent, vq-keyword-planner, vq-local-presence-booster.
- protocol.md now 654 lines (Parts A-D) + pitch coverage map; all 21 zips refreshed.
- Batch 2 (5 files) import to instance #1 in progress; batch 3 (10 files) import
  queued after it. Live tests pending import.

## 2026-09-27 00:10 UTC — 21 workflows live + verified
- Primary instance (automation-832k, n8n 2.9.4): final count 21, all Published, zero node warnings, zero credentials.
- Replaced broken SEO audit (Prepare Audit fix, 5 nodes); imported 10 batch-3 workflows.
- Live curl tests: 18/18 pass. SEO 70/C (visionquantech.com), 50/D (example.com); wa-in booking intent; email-in billing/high; call-in + call-choice TwiML; reminder invalid-past rejected; lead-form HOT 85 / COLD invalid; triage critical→escalated, normal→low; SDR HOT 100 / COLD 0; doc valid→auto 45000 INR, malformed→human; kw-in keywords; presence-in checklist.
- Render free-tier flakiness: 5 requests dropped connection on first attempt, all passed on retry (call-in needed 3 tries). Transport issue, not workflow logic.
- Minor cosmetic quirk: kw-in emits "real estate real estate price" (seed repeated in mods) — local fix pending.
