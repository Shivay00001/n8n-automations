# Setup Guide — VisionQuantech n8n Automation Pack

## A. Import (2 min per workflow)
1. Open the n8n editor → **Workflows** (left sidebar).
2. Click **⋯ → Import from File** → select the `.json` file.
3. The workflow opens with all nodes connected. **Save** it (Ctrl+S).

## B. Connect Google once (5 min, needed for Pro + Booking workflows)
1. Open the **Send Instant Reply** (Gmail) node → **Credential → Create new**.
2. Choose **Gmail OAuth2**, sign in with the Google account that will send mail,
   allow access. Name it `Google - VisionQuantech`.
3. Open the **Log to CRM Sheet** node → select the same credential → pick the
   Google Sheet document (create a blank sheet first with a tab named `Leads`).
4. Open **Create Calendar Event** → same credential → pick the calendar.
5. The Demo workflow needs none of this — skip.

## C. Activate + get the live URL
1. Toggle the workflow **Active** (top-right).
2. Open the Webhook node → copy the **Production URL**.
   - Demo: `.../webhook/lead-in`
   - Pro: `.../webhook/lead-in-pro`
   - Booking: `.../webhook/booking-in`
3. Point the client's website form at that URL (POST JSON).

## D. Test in 60 seconds (curl)
```bash
# Demo / Pro lead test
curl -X POST https://n8n-1-83-2-pmw1.onrender.com/webhook/lead-in \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Patient","phone":"+919999988888","email":"test@example.com","service":"dental implant","message":"Hi, I need an urgent appointment tomorrow, what is the cost?"}'
# Expect: {"tier":"HOT","score":>=70,"reply":"Hi Test Patient! ...", ...}

# Booking test
curl -X POST https://n8n-1-83-2-pmw1.onrender.com/webhook/booking-in \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Guest","phone":"+919999988888","email":"test@example.com","service":"root canal","date":"2026-10-05","time":"11:00"}'
# Expect: {"status":"booking_confirmed", ...}
```
(If the Render instance is asleep, the first call takes ~30–60s to wake it.)

## E. Webhook payload contracts
**Lead:** `{name, phone, email, service, message}` — all strings.
**Booking:** `{name, phone, email, service, date: "YYYY-MM-DD", time: "HH:MM" 24h}`.

## Troubleshooting
- Gmail/Sheets/Calendar node errors with "credentials": select the Google
  OAuth credential created in step B.
- Sheets "couldn't find tab": the tab must be named exactly `Leads`.
- Booking "Invalid date/time": send `date` as `YYYY-MM-DD`, `time` as `HH:MM`.
- Webhook 404: the workflow must be **Active**; use the Production URL, not Test.
