import json

GUARD = ("const _raw = $input.first().json;\n"
         "const _in = (_raw && typeof _raw === 'object' && _raw.body && typeof _raw.body === 'object') ? _raw.body : _raw;")


def webhook(nid, name, path, x, wid):
    return {"id": nid, "name": name,
            "parameters": {"httpMethod": "POST", "options": {}, "path": path, "responseMode": "responseNode"},
            "position": [x, 300], "type": "n8n-nodes-base.webhook", "typeVersion": 2, "webhookId": wid}


def code(nid, name, js, x):
    return {"id": nid, "name": name,
            "parameters": {"jsCode": js, "mode": "runOnceForAllItems"},
            "position": [x, 300], "type": "n8n-nodes-base.code", "typeVersion": 2}


def ifbool(nid, name, expr, x):
    return {"id": nid, "name": name,
            "parameters": {"conditions": {"combinator": "and", "conditions": [
                {"id": "c1", "leftValue": expr,
                 "operator": {"operation": "true", "singleValue": True, "type": "boolean"},
                 "rightValue": True}],
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}},
                "options": {}},
            "position": [x, 300], "type": "n8n-nodes-base.if", "typeVersion": 2.2}


def respond(nid, name, x, body="={{ $json }}"):
    return {"id": nid, "name": name,
            "parameters": {"options": {"responseCode": 200}, "respondWith": "json", "responseBody": body},
            "position": [x, 300], "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1}


def respond_text(nid, name, x):
    # Voice providers (Twilio/Exotel) read the webhook RESPONSE as the call script (TwiML/XML).
    return {"id": nid, "name": name,
            "parameters": {"respondWith": "text", "responseBody": "={{ $json.twiml }}",
                           "options": {"responseCode": 200,
                                       "responseHeaders": {"entries": [{"name": "Content-Type", "value": "text/xml"}]}}},
            "position": [x, 300], "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1}


def http_post(nid, name, url_expr, json_body_expr, x):
    return {"id": nid, "name": name,
            "parameters": {"method": "POST", "url": url_expr, "sendBody": True,
                           "specifyBody": "json", "jsonBody": json_body_expr, "options": {}},
            "position": [x, 300], "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2}


def wait_until(nid, name, dt_expr, x):
    return {"id": nid, "name": name,
            "parameters": {"resume": "specificTime", "dateTime": dt_expr},
            "position": [x, 300], "type": "n8n-nodes-base.wait", "typeVersion": 1.1}


def link(pairs):
    conns = {}
    for src, dst in pairs:
        conns.setdefault(src, {"main": []})["main"].append([{"index": 0, "node": dst, "type": "main"}])
    return conns


def set_if_branches(conns, ifname, true_node, false_node):
    conns[ifname] = {"main": [[{"index": 0, "node": true_node, "type": "main"}],
                              [{"index": 0, "node": false_node, "type": "main"}]]}


def save(path, name, nodes, connections):
    wf = {"active": False, "connections": connections, "name": name, "nodes": nodes,
          "pinData": {}, "settings": {"executionOrder": "v1"}}
    with open(path, "w") as f:
        json.dump(wf, f, indent=2)
    names = {n["name"] for n in nodes}
    for src, outs in connections.items():
        assert src in names, f"{path}: bad src {src}"
        for branch in outs["main"]:
            for c in branch:
                assert c["node"] in names, f"{path}: bad dst {c['node']}"
    print("built+validated", path, len(nodes), "nodes")


# ============ A. VQ WhatsApp AI Agent ============
wa_norm = GUARD + """
const m = (_in.entry && _in.entry[0] && _in.entry[0].changes && _in.entry[0].changes[0] &&
           _in.entry[0].changes[0].value && _in.entry[0].changes[0].value.messages &&
           _in.entry[0].changes[0].value.messages[0]) || {};
const message = (_in.Body || (m.text && m.text.body) || '').toString();
const phone = ((_in.From || m.from || '').toString()).replace('whatsapp:', '');
const cb = (_in.callback_url || '').toString();
return [{ json: { phone: phone, message: message, channel: 'whatsapp',
  name: (_in.ProfileName || 'there').toString(), callback_url: cb, hasSender: cb.length > 10 } }];
"""
wa_intent = GUARD + """
const msg = (_in.message || '').toLowerCase();
const rules = [
  ['complaint', ['complaint', 'bad', 'worst', 'terrible', 'rude', 'refund', 'angry', 'cheat', 'fraud']],
  ['booking', ['book', 'appointment', 'slot', 'schedule', 'visit', 'reserve']],
  ['pricing', ['price', 'cost', 'charge', 'fee', 'quote', 'rate']],
  ['info', ['timing', 'hour', 'open', 'close', 'location', 'address', 'service', 'offer']]
];
let intent = 'other';
for (const r of rules) { if (r[1].some(k => msg.includes(k))) { intent = r[0]; break; } }
const urgent = /urgent|asap|immediately|emergency/.test(msg);
const needsHuman = intent === 'complaint' || urgent;
const replies = {
  booking: 'Sure! Please share your name and preferred date/time and we will confirm your slot.',
  pricing: 'Thanks for asking! Share what you need and we will send an exact quote within 30 minutes.',
  info: 'Happy to help! What would you like to know - timings, location or services?',
  complaint: 'We are very sorry about this. Our manager will call you within 30 minutes to fix it on priority.',
  other: 'Thanks for messaging us! Our team will reply within 30 minutes. Meanwhile, how can we help?'
};
return [{ json: Object.assign({}, _in, { intent: intent, needsHuman: needsHuman,
  reply: replies[intent], status: 'processed', receivedAt: new Date().toISOString() }) }];
"""
nA = [
    webhook("a1", "WhatsApp Webhook", "wa-in", 200, "a1a1a1a1-0000-4000-8000-0000000000a1"),
    code("a2", "Normalize Input", wa_norm, 420),
    code("a3", "Detect Intent", wa_intent, 640),
    ifbool("a4", "Has Sender?", "={{ $json.hasSender }}", 860),
    http_post("a5", "Send WhatsApp", "={{ $json.callback_url }}",
              "={{ JSON.stringify({ to: $json.phone, message: $json.reply, intent: $json.intent }) }}", 1080),
    respond("a6", "Send Result", 1300),
]
cA = link([("WhatsApp Webhook", "Normalize Input"), ("Normalize Input", "Detect Intent"),
           ("Detect Intent", "Has Sender?"), ("Has Sender?", "Send WhatsApp"), ("Send WhatsApp", "Send Result")])
set_if_branches(cA, "Has Sender?", "Send WhatsApp", "Send Result")
save("vq-whatsapp-agent.json", "VQ WhatsApp AI Agent", nA, cA)

# ============ B. VQ Email AI Agent ============
em_cls = GUARD + """
const text = ((_in.subject || '') + ' ' + (_in.body || '')).toLowerCase();
const email = (_in.from || _in.email || '').toString();
const rules = [
  ['billing', ['invoice', 'bill', 'payment', 'charged', 'refund', 'subscription']],
  ['support', ['error', 'bug', 'not working', 'broken', 'help', 'issue', 'problem']],
  ['partnership', ['partner', 'collaborat', 'resell', 'affiliate', 'invest']],
  ['spam', ['lottery', 'winner', 'crypto double', 'inheritance']]
];
let intent = 'general';
for (const r of rules) { if (r[1].some(k => text.includes(k))) { intent = r[0]; break; } }
const priority = /refund|legal|sue|urgent|asap|complaint|angry|cancel/.test(text) ? 'high' : 'normal';
const cb = (_in.callback_url || '').toString();
return [{ json: { email: email, subject: (_in.subject || '').toString(), intent: intent,
  priority: priority, callback_url: cb, hasSender: cb.length > 10 } }];
"""
em_draft = GUARD + """
const name = (_in.email || 'there').toString().split('@')[0];
const t = {
  billing: 'Hi ' + name + ', thanks for writing about billing. Our team will reply within 4 business hours with your invoice details.',
  support: 'Hi ' + name + ', sorry for the trouble! Please share your account/order ID and a screenshot so we can resolve this in one go.',
  partnership: 'Hi ' + name + ', thanks for reaching out! Our partnerships team will schedule a call with you this week.',
  spam: '',
  general: 'Hi ' + name + ', thanks for writing in! Our team will reply within 4 business hours.'
};
return [{ json: Object.assign({}, _in, { draftSubject: 'Re: ' + _in.subject,
  draftBody: t[_in.intent] || t.general, status: 'drafted', receivedAt: new Date().toISOString() }) }];
"""
nB = [
    webhook("b1", "Email Webhook", "email-in", 200, "b2b2b2b2-0000-4000-8000-0000000000b2"),
    code("b2", "Classify Email", em_cls, 420),
    code("b3", "Draft Reply", em_draft, 640),
    ifbool("b4", "Has Sender?", "={{ $json.hasSender }}", 860),
    http_post("b5", "Send Email", "={{ $json.callback_url }}",
              "={{ JSON.stringify({ to: $json.email, subject: $json.draftSubject, body: $json.draftBody }) }}", 1080),
    respond("b6", "Send Result", 1300),
]
cB = link([("Email Webhook", "Classify Email"), ("Classify Email", "Draft Reply"),
           ("Draft Reply", "Has Sender?"), ("Has Sender?", "Send Email"), ("Send Email", "Send Result")])
set_if_branches(cB, "Has Sender?", "Send Email", "Send Result")
save("vq-email-agent.json", "VQ Email AI Agent", nB, cB)

# ============ C. VQ AI Calling Agent ============
call_route = """
const _raw = $input.first().json;
const _in = (_raw && typeof _raw === 'object' && _raw.body && typeof _raw.body === 'object') ? _raw.body : _raw;
let host = '';
try { host = $('Call Webhook').first().json.headers.host || ''; } catch (e) {}
const base = (host ? 'https://' + host : (_in.base_url || '')).toString().replace(/\\/$/, '');
const caller = (_in.Caller || _in.caller || '').toString();
const business = (_in.business || 'our business').toString();
const h = new Date().getHours();
const afterHours = h < 9 || h >= 21;
const twiml = afterHours
  ? '<Response><Say voice="alice">Thanks for calling ' + business + '. We are currently closed. Please call between 9 AM and 9 PM, or send us a WhatsApp message.</Say><Hangup/></Response>'
  : '<Response><Say voice="alice">Thanks for calling ' + business + '. Press 1 to book an appointment, press 2 for timings.</Say><Gather numDigits="1" action="' + base + '/webhook/call-choice" method="POST" timeout="10"/></Response>';
return [{ json: { caller: caller, business: business, afterHours: afterHours, twiml: twiml,
  gather_url: base + '/webhook/call-choice', receivedAt: new Date().toISOString() } }];
"""
call_choice = GUARD + """
const d = (_in.Digits || _in.digits || '').toString().trim();
let say;
if (d === '1') say = 'Great! Our team will call you back within 15 minutes to confirm your booking.';
else if (d === '2') say = 'We are open 9 AM to 9 PM, all seven days.';
else say = 'Sorry, we did not get that. Our team will call you back shortly.';
return [{ json: { digits: d, caller: (_in.Caller || _in.caller || '').toString(),
  twiml: '<Response><Say voice="alice">' + say + '</Say><Hangup/></Response>' } }];
"""
nC = [
    webhook("c1", "Call Webhook", "call-in", 200, "c3c3c3c3-0000-4000-8000-0000000000c3"),
    code("c2", "Route Call", call_route, 460),
    ifbool("c3", "After Hours?", "={{ $json.afterHours }}", 720),
    respond_text("c4", "Answer Call (TwiML)", 980),
    webhook("c5", "Choice Webhook", "call-choice", 200, "c5c5c5c5-0000-4000-8000-0000000000c5"),
    code("c6", "Read Choice", call_choice, 460),
    respond_text("c7", "Answer Choice (TwiML)", 720),
]
# position second chain lower
nC[4]["position"] = [200, 560]; nC[5]["position"] = [460, 560]; nC[6]["position"] = [720, 560]
cC = link([("Call Webhook", "Route Call"), ("Route Call", "After Hours?"),
           ("Choice Webhook", "Read Choice"), ("Read Choice", "Answer Choice (TwiML)")])
set_if_branches(cC, "After Hours?", "Answer Call (TwiML)", "Answer Call (TwiML)")
save("vq-ai-calling-agent.json", "VQ AI Calling Agent", nC, cC)

# ============ D. VQ Reminder Sender ============
rem_js = GUARD + """
const send_at = (_in.send_at || '').toString();
const t = Date.parse(send_at);
const cb = (_in.callback_url || '').toString();
return [{ json: { to: (_in.to || '').toString(), message: (_in.message || '').toString(),
  send_at: send_at, valid: !isNaN(t) && t > Date.now(), callback_url: cb,
  hasSender: cb.length > 10, status: 'scheduled', receivedAt: new Date().toISOString() } }];
"""
nD = [
    webhook("d1", "Reminder Webhook", "reminder-in", 200, "d4d4d4d4-0000-4000-8000-0000000000d4"),
    code("d2", "Compute Schedule", rem_js, 420),
    respond("d3", "Acknowledge", 640),
    ifbool("d4", "Has Sender?", "={{ $json.hasSender }}", 860),
    wait_until("d5", "Wait Until Time", "={{ $json.send_at }}", 1080),
    http_post("d6", "Send Reminder", "={{ $json.callback_url }}",
              "={{ JSON.stringify({ to: $json.to, message: $json.message, type: 'reminder' }) }}", 1300),
]
cD = link([("Reminder Webhook", "Compute Schedule"), ("Compute Schedule", "Acknowledge"),
           ("Acknowledge", "Has Sender?"), ("Has Sender?", "Wait Until Time"),
           ("Wait Until Time", "Send Reminder")])
cD["Has Sender?"] = {"main": [[{"index": 0, "node": "Wait Until Time", "type": "main"}], []]}
save("vq-reminder-sender.json", "VQ Reminder Sender", nD, cD)

# ============ E. VQ Website Lead Capture ============
lc_js = GUARD + """
const errors = [];
const name = (_in.name || '').toString().trim();
const phone = (_in.phone || '').toString();
const email = (_in.email || '').toString();
const service = (_in.service || '').toString();
if (!name) errors.push('name is required');
if (phone.replace(/\\D/g, '').length < 10) errors.push('valid phone is required');
if (email && !/^[\\w.%-]+@[\\w.-]+\\.[a-zA-Z]{2,}$/.test(email)) errors.push('email looks invalid');
let score = 0;
if (phone.replace(/\\D/g, '').length >= 10) score += 40;
if (/@/.test(email)) score += 25;
if (service) score += 20;
if ((_in.message || '').toString().length > 20) score += 15;
return [{ json: { name: name, phone: phone, email: email, service: service,
  message: (_in.message || '').toString(), page_url: (_in.page_url || '').toString(),
  valid: errors.length === 0, errors: errors, score: score,
  tier: score >= 70 ? 'HOT' : score >= 40 ? 'WARM' : 'COLD',
  owner_alert: errors.length === 0 ? ('New ' + score + '-point lead: ' + name + ' (' + phone + ') via ' + service) : null,
  status: errors.length === 0 ? 'captured' : 'invalid', receivedAt: new Date().toISOString() } }];
"""
nE = [
    webhook("e1", "Lead Form Webhook", "lead-form", 200, "e5e5e5e5-0000-4000-8000-0000000000e5"),
    code("e2", "Validate & Score", lc_js, 460),
    ifbool("e3", "Valid?", "={{ $json.valid }}", 720),
    respond("e4", "Send Result", 980),
]
cE = link([("Lead Form Webhook", "Validate & Score"), ("Validate & Score", "Valid?")])
set_if_branches(cE, "Valid?", "Send Result", "Send Result")
save("vq-website-lead-capture.json", "VQ Website Lead Capture", nE, cE)

# ============ F. VQ Support Ticket Triage Agent ============
tri_js = GUARD + """
const text = ((_in.subject || '') + ' ' + (_in.body || '')).toLowerCase();
const catRules = [
  ['billing', ['invoice', 'bill', 'payment', 'charged', 'refund', 'subscription', 'price']],
  ['technical', ['error', 'bug', 'crash', 'not working', 'broken', 'slow', 'login', 'down', 'outage']],
  ['account', ['password', 'account', 'signup', 'delete account', 'access']]
];
let category = 'general';
for (const r of catRules) { if (r[1].some(k => text.includes(k))) { category = r[0]; break; } }
let urgency = 'low', uscore = 10;
if (/outage|down|breach|hack|data loss|security/.test(text)) { urgency = 'critical'; uscore = 100; }
else if (/refund|angry|furious|cancel|complaint|sue|asap/.test(text)) { urgency = 'high'; uscore = 75; }
else if (/error|broken|not working|payment failed/.test(text)) { urgency = 'normal'; uscore = 50; }
const replies = {
  billing: 'Thanks for flagging this! Our billing team is checking your account and will update you within 4 business hours.',
  technical: 'Sorry about this! Our tech team is on it. Please share a screenshot and the steps to reproduce so we fix it faster.',
  account: 'Got it! For account security, please confirm your registered email and we will sort this out right away.',
  general: 'Thanks for reaching out! Our support team will reply within 4 business hours.'
};
const escalate = urgency === 'critical' || urgency === 'high';
return [{ json: { customer: (_in.customer || '').toString(), channel: (_in.channel || 'web').toString(),
  subject: (_in.subject || '').toString(), category: category, urgency: urgency, urgency_score: uscore,
  suggested_reply: replies[category], escalated: escalate,
  owner_alert: escalate ? ('ESCALATE [' + urgency + '/' + category + ']: ' + (_in.subject || '')) : null,
  status: 'triaged', receivedAt: new Date().toISOString() } }];
"""
nF = [
    webhook("f1", "Ticket Webhook", "ticket-in", 200, "f6f6f6f6-0000-4000-8000-0000000000f6"),
    code("f2", "Triage Ticket", tri_js, 460),
    ifbool("f3", "Escalate?", "={{ $json.escalated }}", 720),
    respond("f4", "Send Result", 980),
]
cF = link([("Ticket Webhook", "Triage Ticket"), ("Triage Ticket", "Escalate?")])
set_if_branches(cF, "Escalate?", "Send Result", "Send Result")
save("vq-support-triage-agent.json", "VQ Support Ticket Triage Agent", nF, cF)

# ============ G. VQ AI SDR Agent ============
sdr_js = GUARD + """
const name = (_in.name || 'there').toString().trim();
const company = (_in.company || '').toString();
const email = (_in.email || '').toString();
const phone = (_in.phone || '').toString();
const budget = (_in.budget_hint || '').toString().toLowerCase();
const need = (_in.need || '').toString();
let score = 0; const reasons = [];
if (company) { score += 20; reasons.push('Company known (+20)'); }
if (/@/.test(email) && !/gmail|yahoo|hotmail/.test(email)) { score += 15; reasons.push('Work email (+15)'); }
if (/high|5000|10k|approved/.test(budget)) { score += 25; reasons.push('Budget signal (+25)'); }
if (need.length > 10) { score += 20; reasons.push('Clear need (+20)'); }
if (phone.replace(/\\D/g, '').length >= 10) { score += 20; reasons.push('Phone provided (+20)'); }
const tier = score >= 70 ? 'HOT' : score >= 40 ? 'WARM' : 'COLD';
const slots = [];
const d = new Date(Date.now() + 19800000); let added = 0;
while (added < 2) { d.setUTCDate(d.getUTCDate() + 1); const day = d.getUTCDay();
  if (day !== 0 && day !== 6) { const s = d.toISOString().slice(0, 10);
    slots.push(s + ' 11:00 IST', s + ' 16:00 IST'); added++; } }
return [{ json: { name: name, company: company, email: email, phone: phone,
  source: (_in.source || 'website').toString(), fit_score: score, tier: tier, reasons: reasons,
  goodFit: tier !== 'COLD',
  first_touch: 'Hi ' + name + '! Saw your interest via ' + (_in.source || 'our website') +
    ' - quick question: what is the #1 thing you want to fix this month?',
  meeting_slots: slots,
  next_action: tier === 'HOT' ? 'Call within 30 min + send calendar invite' :
    tier === 'WARM' ? 'Send first-touch message, follow up in 4 hours' : 'Add to nurture sequence',
  status: 'qualified', receivedAt: new Date().toISOString() } }];
"""
nG = [
    webhook("g1", "SDR Webhook", "sdr-lead", 200, "a7a7a7a7-0000-4000-8000-0000000000a7"),
    code("g2", "Qualify Fit", sdr_js, 460),
    ifbool("g3", "Worth Pursuing?", "={{ $json.goodFit }}", 720),
    respond("g4", "Send Result", 980),
]
cG = link([("SDR Webhook", "Qualify Fit"), ("Qualify Fit", "Worth Pursuing?")])
set_if_branches(cG, "Worth Pursuing?", "Send Result", "Send Result")
save("vq-sdr-agent.json", "VQ AI SDR Agent", nG, cG)

# ============ H. VQ Document Processing Agent ============
doc_ext = GUARD + """
const text = (_in.text || '').toString();
const doc_type = (_in.doc_type || 'document').toString();
const pick = (re) => { const m = text.match(re); return m ? (m[m.length - 1] || '').trim() : ''; };
const money = (s) => { const m = (s || '').match(/[\d,]+(?:\.\d+)?/); if (!m) return null; const n = parseFloat(m[0].replace(/,/g, '')); return isNaN(n) ? null : n; };
const extracted = {
  doc_no: pick(/invoice\\s*(no|number|#)?\\s*[:\\-]?\\s*([A-Za-z0-9\\-\\/]+)/i) || pick(/(?:no|#)\\s*[:\\-]?\\s*([A-Za-z0-9\\-\\/]{3,})/i),
  date: pick(/(\\d{1,2}[\\/\\-]\\d{1,2}[\\/\\-]\\d{2,4})/),
  vendor: (text.split('\\n').map(l => l.trim()).filter(l => l.length > 2)[0] || '').slice(0, 80),
  total: money(pick(/(?:grand total|total amount|amount due|total)\\s*[:\\-]?\\s*([^\\n]*)/i)),
  currency: /\\u20b9|INR|Rs\\.?/i.test(text) ? 'INR' : (/\$|USD/i.test(text) ? 'USD' : '')
};
return [{ json: { doc_type: doc_type, extracted: extracted } }];
"""
doc_val = """
const _raw = $input.first().json;
const e = _raw.extracted || {};
const doc_type = _raw.doc_type || 'document';
const exceptions = [];
if (!e.doc_no) exceptions.push('Document number not found');
if (!e.date) exceptions.push('Date not found or unreadable');
else { const m = e.date.match(/(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})/);
  let t = NaN;
  if (m) { let y = +m[3]; if (y < 100) y += 2000; const dt = new Date(y, +m[2] - 1, +m[1]);
    if (dt.getFullYear() === y && dt.getMonth() === +m[2] - 1 && dt.getDate() === +m[1]) t = dt.getTime(); }
  if (isNaN(t)) exceptions.push('Date is invalid: ' + e.date);
  else if (t > Date.now()) exceptions.push('Date is in the future: ' + e.date); }
if (e.total === null || e.total === undefined) exceptions.push('Total amount not found');
if (!e.vendor) exceptions.push('Vendor/sender not identified');
return [{ json: { doc_type: doc_type, extracted: e, valid: exceptions.length === 0,
  exceptions: exceptions, route: exceptions.length ? 'human' : 'auto',
  status: 'processed', receivedAt: new Date().toISOString() } }];
"""
nH = [
    webhook("h1", "Document Webhook", "doc-in", 200, "b8b8b8b8-0000-4000-8000-0000000000b8"),
    code("h2", "Extract Fields", doc_ext, 460),
    code("h3", "Validate", doc_val, 720),
    ifbool("h4", "Has Exceptions?", "={{ $json.exceptions.length > 0 }}", 980),
    respond("h5", "Send Result", 1240),
]
cH = link([("Document Webhook", "Extract Fields"), ("Extract Fields", "Validate"),
           ("Validate", "Has Exceptions?")])
set_if_branches(cH, "Has Exceptions?", "Send Result", "Send Result")
save("vq-document-agent.json", "VQ Document Processing Agent", nH, cH)

# ============ I. VQ Keyword Planner ============
kw_js = GUARD + """
const seed = (_in.seed_keyword || 'services').toString().trim();
const loc = (_in.location || '').toString().trim();
const biz = (_in.business_type || 'business').toString().trim();
const mods = ['best', 'affordable', 'top 10', 'near me', loc, seed + ' price', seed + ' cost'];
const keywords = [];
mods.forEach(m => { if (m) keywords.push((seed + ' ' + m).trim()); });
keywords.push('how much does ' + seed + ' cost' + (loc ? ' in ' + loc : ''));
keywords.push('best ' + seed + (loc ? ' in ' + loc : '') + ' near me');
const brief = keywords.slice(0, 5).map((k, i) => ({
  keyword: k,
  title_idea: k.charAt(0).toUpperCase() + k.slice(1) + ' - ' + biz + (loc ? ' | ' + loc : ''),
  intent: /price|cost|how much/.test(k) ? 'commercial' : /best|top/.test(k) ? 'commercial-investigation' : 'local'
}));
return [{ json: { seed_keyword: seed, location: loc, business_type: biz,
  keywords: keywords, content_brief: brief,
  note: 'Target one keyword per page. Commercial-intent keywords bring bookings fastest.',
  status: 'planned', receivedAt: new Date().toISOString() } }];
"""
nI = [
    webhook("i1", "Keyword Webhook", "kw-in", 200, "c9c9c9c9-0000-4000-8000-0000000000c9"),
    code("i2", "Generate Plan", kw_js, 460),
    respond("i3", "Send Plan", 720),
]
cI = link([("Keyword Webhook", "Generate Plan"), ("Generate Plan", "Send Plan")])
save("vq-keyword-planner.json", "VQ Keyword Planner", nI, cI)

# ============ J. VQ Local Presence Booster ============
pb_js = GUARD + """
const biz = (_in.business_name || 'your business').toString();
const cat = (_in.category || 'business').toString();
const city = (_in.city || '').toString();
const link = (_in.review_link || '').toString();
return [{ json: { business_name: biz,
  maps_checklist: [
    'Claim and verify the Google Business Profile for ' + biz,
    'NAP consistency: name, address, phone identical on website, GBP and directories',
    'Primary category set to "' + cat + '"' + (city ? ', service areas include ' + city : ''),
    'Opening hours complete including holidays',
    'Add 10+ real photos (exterior, interior, team, work)',
    'List all services/products with descriptions',
    'Enable messaging and Q&A on the profile'
  ],
  review_plan: [
    'Ask every happy customer for a review within 24 hours of service',
    'Review link: ' + (link || 'ADD-YOUR-GOOGLE-REVIEW-LINK'),
    'Print the link as a QR code at billing counter / on receipts',
    'Reply to every review within 48 hours (thank positive, resolve negative)'
  ],
  weekly_post_ideas: [
    'Offer of the week at ' + biz,
    'Behind the scenes: meet the team',
    'Customer story / before-after',
    'Local tip related to ' + cat
  ],
  has_website: !!_in.has_website,
  website_note: _in.has_website ? 'Website present - run the VQ SEO Audit Agent on it next.' : 'No website detected - this is the #1 Maps ranking blocker. Pitch a website first.',
  status: 'planned', receivedAt: new Date().toISOString() } }];
"""
nJ = [
    webhook("j1", "Presence Webhook", "presence-in", 200, "d0d0d0d0-0000-4000-8000-0000000000d0"),
    code("j2", "Build Presence Plan", pb_js, 460),
    respond("j3", "Send Plan", 720),
]
cJ = link([("Presence Webhook", "Build Presence Plan"), ("Build Presence Plan", "Send Plan")])
save("vq-local-presence-booster.json", "VQ Local Presence Booster", nJ, cJ)

print("BATCH3 DONE")
