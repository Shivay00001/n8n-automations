import json, zipfile, os

specs = {
  'vq-whatsapp-agent': {
    'title': 'VQ WhatsApp AI Agent', 'path': 'wa-in',
    'pitch': 'AI-agent pitch: dedicated WhatsApp handling - normalize any provider payload, detect intent, reply/escalate.',
    'needs': 'No credentials needed. Optional: callback_url (your WhatsApp sender endpoint, e.g. Meta Cloud API / Twilio relay) to actually deliver replies.',
    'nodes': '6 nodes: WhatsApp Webhook -> Normalize Input -> Detect Intent -> Has Sender? (IF) -> Send WhatsApp (HTTP) -> Send Result',
    'payloads': {
      'test-payload-twilio.json': {"Body": "I want to book a visit", "From": "whatsapp:+919811111111", "callback_url": "https://example.com/send"},
      'test-payload-meta.json': {"entry": [{"changes": [{"value": {"messages": [{"from": "919822222222", "text": {"body": "terrible service, I want refund"}}]}}]}]},
      'test-payload-nocallback.json': {"Body": "what are your prices?", "From": "whatsapp:+919833333333"},
    },
    'how': [
      'POST any WhatsApp provider payload (Twilio form-encoded OR Meta Cloud API JSON) to /webhook/wa-in.',
      'Normalize Input converts both shapes into one: {phone, message, channel, name}.',
      'Detect Intent: complaint > booking > pricing > info > other; urgent/complaint -> needsHuman.',
      'If callback_url is set, the reply is POSTed to it as {to, message, intent}; the response always includes the reply.',
      'To send for real: point callback_url at your Meta Cloud API / Twilio / WATI relay, or swap the HTTP node for direct provider auth.',
    ],
  },
  'vq-email-agent': {
    'title': 'VQ Email AI Agent', 'path': 'email-in',
    'pitch': 'AI-agent pitch: dedicated email handling - classify, prioritize, draft the reply.',
    'needs': 'No credentials needed. Optional: callback_url (your mail-sending endpoint) to actually deliver replies.',
    'nodes': '6 nodes: Email Webhook -> Classify Email -> Draft Reply -> Has Sender? (IF) -> Send Email (HTTP) -> Send Result',
    'payloads': {
      'test-payload-billing.json': {"from": "a@b.com", "subject": "Invoice wrong charged twice", "body": "please refund the extra charge", "callback_url": "https://example.com/send"},
      'test-payload-partnership.json': {"from": "x@y.com", "subject": "Partnership proposal", "body": "we want to resell your services"},
    },
    'how': [
      'POST fields: from, subject, body, callback_url (optional).',
      'Classify Email: intent (billing/support/partnership/spam/general) + priority (refund/legal/urgent/cancel -> high).',
      'Draft Reply: intent-wise template; spam gets an empty draft.',
      'If callback_url is set, the draft is POSTed to it as {to, subject, body}; the response always includes the draft.',
      'Production: swap the HTTP node for the Gmail node (Google OAuth) to send from the real inbox.',
    ],
  },
  'vq-ai-calling-agent': {
    'title': 'VQ AI Calling Agent', 'path': 'call-in (+ call-choice)',
    'pitch': 'AI-agent pitch: "calls" - inbound AI receptionist: greet, IVR menu, route by digit, after-hours handling.',
    'needs': 'No credentials needed for logic. Real calls need Twilio/Exotel pointed at these webhooks (their trial accounts are free).',
    'nodes': '7 nodes: Call Webhook -> Route Call -> After Hours? (IF) -> Answer Call (TwiML Respond) | Choice Webhook -> Read Choice -> Answer Choice (TwiML Respond)',
    'payloads': {
      'test-payload-call.json': {"Caller": "+919811111111", "CallSid": "CA123", "business": "Sunrise Dental"},
      'test-payload-choice.json': {"Digits": "1", "Caller": "+919811111111"},
    },
    'how': [
      'Point your Twilio/Exotel voice webhook at POST /webhook/call-in. The workflow RESPONSE is the call script (TwiML XML).',
      'Route Call: business-hours check (9 AM - 9 PM server time), builds the TwiML; the Gather action URL is built from the real request host - no placeholder to edit.',
      'After hours -> closed message + hangup. Open hours -> greeting + "press 1 to book, 2 for timings".',
      'Caller presses a digit -> provider POSTs to /webhook/call-choice -> Read Choice -> spoken answer -> hangup.',
      'Server timezone note: set TZ on your n8n host for correct business-hours routing.',
    ],
  },
  'vq-reminder-sender': {
    'title': 'VQ Reminder Sender', 'path': 'reminder-in',
    'pitch': 'Every pitch: "sends reminders" - schedule any reminder, delivered exactly at send_at.',
    'needs': 'No credentials needed. callback_url (your SMS/WhatsApp/email sender endpoint) delivers the message.',
    'nodes': '6 nodes: Reminder Webhook -> Compute Schedule -> Acknowledge (Respond) -> Has Sender? (IF) -> Wait Until Time -> Send Reminder (HTTP)',
    'payloads': {
      'test-payload.json': {"to": "9811111111", "message": "Reminder: your appointment is tomorrow at 11 AM", "send_at": "2026-09-28T09:00:00+05:30", "callback_url": "https://example.com/send"},
    },
    'how': [
      'POST fields: to, message, send_at (ISO with timezone), callback_url.',
      'Acknowledge responds IMMEDIATELY with {status: scheduled}; the Wait node holds until send_at, then POSTs {to, message, type: reminder}.',
      'send_at in the past -> valid=false; without callback_url you only get the acknowledgement.',
      'Production note: long waits need persistent n8n (see protocol.md Part C).',
    ],
  },
  'vq-website-lead-capture': {
    'title': 'VQ Website Lead Capture', 'path': 'lead-form',
    'pitch': 'Website pitch: "turn visitors into enquiries" - validate + score every form submission.',
    'needs': 'No credentials needed.',
    'nodes': '4 nodes: Lead Form Webhook -> Validate & Score -> Valid? (IF) -> Send Result',
    'payloads': {
      'test-payload-valid.json': {"name": "Rohan", "phone": "9811111111", "email": "r@x.com", "service": "AI agents", "message": "need AI agent for my clinic urgently", "page_url": "https://example.com"},
      'test-payload-invalid.json': {"name": "", "phone": "123"},
    },
    'how': [
      'POST fields: name, phone, email, service, message, page_url.',
      'Validate & Score: required-field + format checks -> errors[]; score 0-100 (phone +40, email +25, service +20, detailed message +15) -> HOT/WARM/COLD.',
      'Valid leads return owner_alert text ready to forward to the business owner.',
      'Point any website form at this URL - no backend code needed.',
    ],
  },
  'vq-support-triage-agent': {
    'title': 'VQ Support Ticket Triage Agent', 'path': 'ticket-in',
    'pitch': 'SaaS pitch: "answers every question instantly, triages tickets by urgency, escalates the tricky ones" - 24/7.',
    'needs': 'No credentials needed.',
    'nodes': '4 nodes: Ticket Webhook -> Triage Ticket -> Escalate? (IF) -> Send Result',
    'payloads': {
      'test-payload-critical.json': {"customer": "Acme", "channel": "email", "subject": "SYSTEM DOWN - outage", "body": "our dashboard is down, data loss feared"},
      'test-payload-normal.json': {"customer": "Beta", "channel": "web", "subject": "how to reset password", "body": "need help with account access"},
    },
    'how': [
      'POST fields: customer, channel, subject, body.',
      'Triage Ticket: category (billing/technical/account/general) + urgency (critical/high/normal/low) with scores, suggested_reply template, escalated flag.',
      'Critical/high -> owner_alert text for instant escalation to humans.',
      'Feed from Intercom/Zendesk/Freshdesk webhooks or your support inbox parser.',
    ],
  },
  'vq-sdr-agent': {
    'title': 'VQ AI SDR Agent', 'path': 'sdr-lead',
    'pitch': 'Agency pitch: "follows up every new lead in under a minute, qualifies fit, books meetings" - 24/7.',
    'needs': 'No credentials needed.',
    'nodes': '4 nodes: SDR Webhook -> Qualify Fit -> Worth Pursuing? (IF) -> Send Result',
    'payloads': {
      'test-payload-hot.json': {"name": "Neha", "company": "SmileCare", "email": "neha@smilecare.com", "phone": "9876543210", "budget_hint": "high", "need": "need AI receptionist for clinic", "source": "Meta ad"},
      'test-payload-cold.json': {"name": "X"},
    },
    'how': [
      'POST fields: name, company, email, phone, budget_hint, need, source.',
      'Qualify Fit: 0-100 fit score with reasons (company, work email, budget signal, clear need, phone) -> HOT/WARM/COLD.',
      'Returns first_touch message (sub-minute follow-up) + next 2 business-day meeting slots in IST + next_action.',
      'Connect ad lead forms / website forms here for instant SDR response.',
    ],
  },
  'vq-document-agent': {
    'title': 'VQ Document Processing Agent', 'path': 'doc-in',
    'pitch': 'Ops pitch: "extracts data from invoices, claims, and forms, validates it, routes exceptions to a human" - automatically.',
    'needs': 'No credentials needed. (For PDF/image input, add an OCR step before this webhook - e.g. a free OCR API.)',
    'nodes': '5 nodes: Document Webhook -> Extract Fields -> Validate -> Has Exceptions? (IF) -> Send Result',
    'payloads': {
      'test-payload-valid.json': {"doc_type": "invoice", "text": "ACME SUPPLIERS\nInvoice No: INV-2026-8841\nDate: 25/09/2026\nGrand Total: Rs. 45,000"},
      'test-payload-broken.json': {"doc_type": "invoice", "text": "random words here"},
    },
    'how': [
      'POST fields: doc_type (invoice/claim/form), text (extracted document text).',
      'Extract Fields: regex pulls doc number, date (DD/MM/YYYY aware), vendor, total, currency.',
      'Validate: missing fields, invalid/future dates -> exceptions[]; route = auto (clean) or human (exceptions).',
      'Route "auto" documents straight to your books/ERP; "human" ones to a review queue.',
    ],
  },
  'vq-keyword-planner': {
    'title': 'VQ Keyword Planner', 'path': 'kw-in',
    'pitch': 'SEO pitch: "the keywords that bring bookings" - instant keyword + content plan per business.',
    'needs': 'No credentials needed.',
    'nodes': '3 nodes: Keyword Webhook -> Generate Plan -> Send Plan',
    'payloads': {
      'test-payload.json': {"seed_keyword": "dental clinic", "location": "Andheri", "business_type": "clinic"},
    },
    'how': [
      'POST fields: seed_keyword, location, business_type.',
      'Generate Plan: long-tail combos (best/affordable/near me/price/cost/location) + question keywords + content brief (title idea + search intent per keyword).',
      'Use in the free SEO audit call: prospect gets keywords + audit in one 15-minute demo.',
    ],
  },
  'vq-local-presence-booster': {
    'title': 'VQ Local Presence Booster', 'path': 'presence-in',
    'pitch': 'SEO pitch: "Google Maps ranking" - the actionable Maps optimization plan (free checks, honest limits).',
    'needs': 'No credentials needed.',
    'nodes': '3 nodes: Presence Webhook -> Build Presence Plan -> Send Plan',
    'payloads': {
      'test-payload.json': {"business_name": "Sunrise Dental", "category": "Dental clinic", "city": "Mumbai", "has_website": False, "review_link": "https://g.page/r/abc"},
    },
    'how': [
      'POST fields: business_name, category, city, has_website, review_link.',
      'Returns: 7-step Maps checklist (GBP claim, NAP consistency, categories, hours, photos, services, messaging), review generation plan, 4 weekly post ideas.',
      'Honest limit: live Maps ranking POSITION needs a paid SERP API; this gives everything actionable without it.',
      'If has_website=false, the plan flags the website as the #1 ranking blocker - natural upsell to the website pitch.',
    ],
  },
}

os.chdir(os.path.expanduser('~/workspace/n8n-automations'))
for slug, s in specs.items():
    src = os.path.join('workflows', slug + '.json')
    readme = [f"# {s['title']}\n", f"Pitch promise: {s['pitch']}\n", f"{s['nodes']}\n",
              f"**Requirements:** {s['needs']}\n", "## How it works\n"]
    readme += [f"{i}. {h}" for i, h in enumerate(s['how'], 1)]
    readme += ["\n## Setup\n",
      "1. In n8n: Workflows -> ... -> Import from File -> choose workflow.json. Save.",
      "2. Publish (activate) the workflow.",
      f"3. Production webhook URL = https://YOUR-N8N-DOMAIN/webhook/{s['path']} (POST).",
      "4. Send a test POST, e.g.:",
      f'   curl -X POST https://YOUR-N8N-DOMAIN/webhook/{s["path"]} -H "Content-Type: application/json" -d @test-payload.json',
      "\n## Files\n", "- `workflow.json` - import this into n8n.",
      "- `protocol.md` - universal guide: JSON/methods/logic teaching + n8n-as-backend contract."]
    readme += [f"- `{p}` - sample POST body." for p in s['payloads']]
    readme += ["\n- Built by VisionQuantech.\n"]
    zpath = os.path.join('dist', slug + '.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        z.write(src, 'workflow.json')
        z.writestr('README.md', '\n'.join(readme))
        z.write('protocol.md', 'protocol.md')
        for pname, payload in s['payloads'].items():
            z.writestr(pname, json.dumps(payload, indent=2))
    print('built', zpath, os.path.getsize(zpath), 'bytes')
