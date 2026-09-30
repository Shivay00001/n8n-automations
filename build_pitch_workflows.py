import json

BODY_GUARD = ("const _raw = $input.first().json;\n"
              "const _in = (_raw && typeof _raw === 'object' && _raw.body && typeof _raw.body === 'object') ? _raw.body : _raw;")

def webhook_node(nid, name, path, x, wid):
    return {
        "id": nid, "name": name,
        "parameters": {"httpMethod": "POST", "options": {}, "path": path, "responseMode": "responseNode"},
        "position": [x, 300],
        "type": "n8n-nodes-base.webhook", "typeVersion": 2, "webhookId": wid,
    }

def code_node(nid, name, js, x):
    return {
        "id": nid, "name": name,
        "parameters": {"jsCode": js, "mode": "runOnceForAllItems"},
        "position": [x, 300],
        "type": "n8n-nodes-base.code", "typeVersion": 2,
    }

def if_node(nid, name, left_expr, operation, right_value, vtype, x):
    return {
        "id": nid, "name": name,
        "parameters": {
            "conditions": {
                "combinator": "and",
                "conditions": [
                    {"id": "cond-1", "leftValue": left_expr,
                     "operator": {"operation": operation, "singleValue": True, "type": vtype},
                     "rightValue": right_value}
                ],
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2},
            },
            "options": {},
        },
        "position": [x, 300],
        "type": "n8n-nodes-base.if", "typeVersion": 2.2,
    }

def respond_node(nid, name, x):
    return {
        "id": nid, "name": name,
        "parameters": {"options": {"responseCode": 200}, "respondWith": "json", "responseBody": "={{ $json }}"},
        "position": [x, 300],
        "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1,
    }

def save(path, name, nodes, connections):
    wf = {"active": False, "connections": connections, "name": name, "nodes": nodes,
          "pinData": {}, "settings": {"executionOrder": "v1"}}
    with open(path, "w") as f:
        json.dump(wf, f, indent=2)
    print("built", path, len(nodes), "nodes")

# ================= 1. VQ AI Enquiry Agent =================
intent_js = BODY_GUARD + """
const name = (_in.name || 'there').toString().trim();
const channel = (_in.channel || 'web').toString().toLowerCase();
const message = (_in.message || '').toString();
const msg = message.toLowerCase();
const business = (_in.business || 'our business').toString();
const phone = (_in.phone || '').toString();
const email = (_in.email || '').toString();

const bookingKw = ['book', 'appointment', 'viewing', 'visit', 'schedule', 'slot', 'reserve', 'reservation'];
const pricingKw = ['price', 'cost', 'quote', 'charge', 'fee', 'emi', 'discount', 'offer'];
const infoKw = ['timing', 'location', 'address', 'services', 'treatment', 'menu', 'info', 'details', 'how', 'when', 'where'];
const complaintKw = ['complaint', 'refund', 'cancel', 'rude', 'bad', 'worst', 'angry', 'disappointed'];
const urgentKw = ['urgent', 'asap', 'today', 'immediately', 'emergency', 'call me'];

const has = (list) => list.some(k => msg.includes(k));
let intent = 'other';
if (has(complaintKw)) intent = 'complaint';
else if (has(bookingKw)) intent = 'booking';
else if (has(pricingKw)) intent = 'pricing';
else if (has(infoKw)) intent = 'info';

const urgent = has(urgentKw) || intent === 'complaint';
const needsHuman = intent === 'complaint' || urgent;

const short = channel === 'whatsapp' || channel === 'sms';
const replies = {
  booking: short
    ? 'Hi ' + name + '! I can book that for you right now. Which day & time suits you? Reply with your preference.'
    : 'Hi ' + name + '! Thanks for reaching out to ' + business + '. I can book your appointment right now - just tell me your preferred day and time, and I will confirm the slot instantly.',
  pricing: short
    ? 'Hi ' + name + '! Sharing pricing now - our team will send your exact quote within 30 minutes.'
    : 'Hi ' + name + '! Thanks for asking about pricing at ' + business + '. I have noted your requirement and our team will send you the exact quote within 30 minutes. Anything else I can help with meanwhile?',
  info: short
    ? 'Hi ' + name + '! Thanks for contacting ' + business + '. Our team will reply within 2 business hours.'
    : 'Hi ' + name + '! Thanks for your interest in ' + business + '. Our team will get back within 2 business hours with complete details. Want me to book a free 15-min consultation meanwhile?',
  complaint: 'Hi ' + name + ', I am very sorry for the experience. This is marked PRIORITY - a senior team member will call you within 15 minutes to resolve it.',
  other: short
    ? 'Hi ' + name + '! Thanks for contacting ' + business + '. Our team will respond within 2 business hours.'
    : 'Hi ' + name + '! Thanks for contacting ' + business + '. We have received your message and our team will respond within 2 business hours.'
};

return [{ json: {
  name: name, channel: channel, phone: phone, email: email, business: business,
  message: message, intent: intent, urgent: urgent, needsHuman: needsHuman,
  reply: replies[intent],
  nextAction: needsHuman ? 'Human callback within 15 min (PRIORITY)' : intent === 'booking' ? 'Collect day/time and confirm slot' : 'Team follow-up within 2 business hours',
  receivedAt: new Date().toISOString()
}}];
"""

nodes1 = [
    webhook_node("a1", "Enquiry Webhook", "enquiry-in", 240, "e1a1a1a1-0000-4000-8000-000000000001"),
    code_node("a2", "Detect Intent", intent_js, 480),
    if_node("a3", "Needs Human?", "={{ $json.needsHuman }}", "true", True, "boolean", 700),
    respond_node("a4", "Send Reply", 920),
]
conn1 = {
    "Enquiry Webhook": {"main": [[{"index": 0, "node": "Detect Intent", "type": "main"}]]},
    "Detect Intent": {"main": [[{"index": 0, "node": "Needs Human?", "type": "main"}]]},
    "Needs Human?": {"main": [[{"index": 0, "node": "Send Reply", "type": "main"}],
                              [{"index": 0, "node": "Send Reply", "type": "main"}]]},
}
save("vq-ai-enquiry-agent.json", "VQ AI Enquiry Agent - Instant Responder", nodes1, conn1)

# ================= 2. VQ Smart Booking Agent =================
booking_js = BODY_GUARD + """
const name = (_in.name || 'Guest').toString().trim();
const phone = (_in.phone || '').toString();
const email = (_in.email || '').toString();
const bookingType = (_in.booking_type || 'appointment').toString().toLowerCase();
const date = _in.date; const time = (_in.time || '10:00').toString();
const partySize = parseInt(_in.party_size || '1', 10);
const notes = (_in.notes || '').toString();

const fail = (reason, fix) => [{ json: { status: 'rejected', reason: reason, fix: fix, receivedAt: new Date().toISOString() } }];

if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}$/.test(date || '')) return fail('Invalid date.', 'Send date as YYYY-MM-DD, e.g. 2026-10-05.');
if (!/^[0-9]{2}:[0-9]{2}$/.test(time)) return fail('Invalid time.', 'Send time as HH:MM in 24h format, e.g. 14:30.');
const start = new Date(date + 'T' + time + ':00');
if (isNaN(start.getTime())) return fail('Invalid date/time combination.', 'Check that the date exists and time is HH:MM (24h).');
const now = new Date();
if (start.getTime() < now.getTime()) return fail('Slot is in the past.', 'Pick a future date and time.');
if (start.getTime() - now.getTime() < 2 * 3600000) return fail('Too soon - need at least 2 hours notice.', 'Pick a slot at least 2 hours from now.');
const hh = start.getHours();
if (hh < 9 || hh >= 21) return fail('Outside booking hours (09:00-21:00).', 'Pick a time between 09:00 and 21:00.');
if (!(partySize >= 1 && partySize <= 20)) return fail('Invalid party size.', 'Send party_size between 1 and 20.');

const end = new Date(start.getTime() + 30 * 60000);
const reminderAt = new Date(start.getTime() - 24 * 3600000);
const ref = 'VQ-' + Date.now().toString(36).toUpperCase().slice(-4) + Math.random().toString(36).toUpperCase().replace(/[^A-Z0-9]/g, '').slice(0, 2);
const typeLabel = { viewing: 'property viewing', appointment: 'appointment', reservation: 'reservation', call: 'callback call' }[bookingType] || bookingType;

return [{ json: {
  status: 'confirmed', bookingRef: ref, name: name, phone: phone, email: email,
  bookingType: bookingType, partySize: partySize, notes: notes,
  slotStart: start.toISOString(), slotEnd: end.toISOString(), reminderAt: reminderAt.toISOString(),
  confirmationMessage: 'Hi ' + name + '! Your ' + typeLabel + ' is confirmed. Ref: ' + ref + '. Date/Time: ' + date + ' ' + time + '. We will send a reminder 24 hours before. Reply to reschedule.',
  reminderMessage: 'Hi ' + name + '! Reminder: your ' + typeLabel + ' (Ref ' + ref + ') is tomorrow at ' + time + '. See you soon!',
  receivedAt: new Date().toISOString()
}}];
"""
nodes2 = [
    webhook_node("b1", "Booking Webhook", "agent-booking", 240, "e1b1b1b1-0000-4000-8000-000000000002"),
    code_node("b2", "Validate & Book", booking_js, 480),
    if_node("b3", "Slot OK?", "={{ $json.status }}", "equals", "confirmed", "string", 700),
    respond_node("b4", "Confirm Booking", 920),
]
conn2 = {
    "Booking Webhook": {"main": [[{"index": 0, "node": "Validate & Book", "type": "main"}]]},
    "Validate & Book": {"main": [[{"index": 0, "node": "Slot OK?", "type": "main"}]]},
    "Slot OK?": {"main": [[{"index": 0, "node": "Confirm Booking", "type": "main"}],
                          [{"index": 0, "node": "Confirm Booking", "type": "main"}]]},
}
save("vq-smart-booking-agent.json", "VQ Smart Booking Agent", nodes2, conn2)

# ================= 3. VQ After-Hours Lead Catcher =================
catcher_js = BODY_GUARD + """
const callerPhone = (_in.caller_phone || '').toString();
const callerName = (_in.caller_name || 'there').toString().trim();
const business = (_in.business || 'our business').toString();
const openH = (_in.business_open || '09:00').toString();
const closeH = (_in.business_close || '21:00').toString();
const missedAt = _in.missed_at ? new Date(_in.missed_at) : new Date();
if (isNaN(missedAt.getTime())) throw new Error('Invalid missed_at. Send ISO datetime, e.g. 2026-09-27T23:30:00.');

const toMin = (t) => { const p = t.split(':'); return parseInt(p[0], 10) * 60 + parseInt(p[1], 10); };
const mins = missedAt.getHours() * 60 + missedAt.getMinutes();
const afterHours = mins < toMin(openH) || mins >= toMin(closeH);

let textBack, callbackAt, priority, status;
if (afterHours) {
  const nextOpen = new Date(missedAt);
  nextOpen.setHours(parseInt(openH.split(':')[0], 10), parseInt(openH.split(':')[1], 10), 0, 0);
  if (nextOpen.getTime() <= missedAt.getTime()) nextOpen.setDate(nextOpen.getDate() + 1);
  textBack = 'Hi ' + callerName + '! Sorry we missed your call. ' + business + ' is open ' + openH + '-' + closeH + '. Reply to this message and we will call you first thing in the morning - you are first in line.';
  callbackAt = nextOpen.toISOString(); priority = 'high'; status = 'after_hours_caught';
} else {
  textBack = 'Hi ' + callerName + '! Sorry we missed your call - our team will call you back within 15 minutes.';
  const cb = new Date(missedAt.getTime() + 15 * 60000);
  callbackAt = cb.toISOString(); priority = 'normal'; status = 'callback_queued';
}

return [{ json: {
  status: status, callerPhone: callerPhone, callerName: callerName, business: business,
  missedAt: missedAt.toISOString(), afterHours: afterHours,
  textBackMessage: textBack, sendTo: callerPhone,
  callbackTask: { callAt: callbackAt, phone: callerPhone, name: callerName, priority: priority },
  receivedAt: new Date().toISOString()
}}];
"""
nodes3 = [
    webhook_node("c1", "Missed Call Webhook", "missed-call", 240, "e1c1c1c1-0000-4000-8000-000000000003"),
    code_node("c2", "After-Hours Check", catcher_js, 480),
    if_node("c3", "Is After Hours?", "={{ $json.afterHours }}", "true", True, "boolean", 700),
    respond_node("c4", "Send Text-Back", 920),
]
conn3 = {
    "Missed Call Webhook": {"main": [[{"index": 0, "node": "After-Hours Check", "type": "main"}]]},
    "After-Hours Check": {"main": [[{"index": 0, "node": "Is After Hours?", "type": "main"}]]},
    "Is After Hours?": {"main": [[{"index": 0, "node": "Send Text-Back", "type": "main"}],
                                 [{"index": 0, "node": "Send Text-Back", "type": "main"}]]},
}
save("vq-afterhours-catcher.json", "VQ After-Hours Lead Catcher", nodes3, conn3)

# ---- static validation ----
for f in ["vq-ai-enquiry-agent.json", "vq-smart-booking-agent.json", "vq-afterhours-catcher.json"]:
    with open(f) as fh:
        wf = json.load(fh)
    names = {n["name"] for n in wf["nodes"]}
    for src, outs in wf["connections"].items():
        assert src in names, f"{f}: bad src {src}"
        for branch in outs["main"]:
            for c in branch:
                assert c["node"] in names, f"{f}: bad dst {c['node']}"
    print("validated", f, "-", len(wf["nodes"]), "nodes, connections OK")
