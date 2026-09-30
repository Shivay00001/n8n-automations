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


def ifequals(nid, name, expr, right, x):
    return {"id": nid, "name": name,
            "parameters": {"conditions": {"combinator": "and", "conditions": [
                {"id": "c1", "leftValue": expr,
                 "operator": {"operation": "equals", "singleValue": True, "type": "string"},
                 "rightValue": right}],
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 2}},
                "options": {}},
            "position": [x, 300], "type": "n8n-nodes-base.if", "typeVersion": 2.2}


def respond(nid, name, x):
    return {"id": nid, "name": name,
            "parameters": {"options": {"responseCode": 200}, "respondWith": "json", "responseBody": "={{ $json }}"},
            "position": [x, 300], "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1}


def http_post(nid, name, url_expr, json_body_expr, x):
    return {"id": nid, "name": name,
            "parameters": {"method": "POST", "url": url_expr, "sendBody": True,
                           "specifyBody": "json", "jsonBody": json_body_expr, "options": {}},
            "position": [x, 300], "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2}


def http_get(nid, name, url_expr, x):
    return {"id": nid, "name": name,
            "parameters": {"method": "GET", "url": url_expr, "options": {}},
            "position": [x, 300], "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2}


def wait_days(nid, name, days, x):
    return {"id": nid, "name": name,
            "parameters": {"resume": "afterTimeInterval", "amount": days, "unit": "days"},
            "position": [x, 300], "type": "n8n-nodes-base.wait", "typeVersion": 1.1}


def link(pairs):
    conns = {}
    for src, dst in pairs:
        conns.setdefault(src, {"main": []})["main"].append([{"index": 0, "node": dst, "type": "main"}])
    return conns


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


# ============ 1. VQ Follow-Up Engine ============
followup_js = GUARD + """
const name = (_in.name || 'there').toString().trim();
const phone = (_in.phone || '').toString();
const email = (_in.email || '').toString();
const interest = (_in.interest || 'our services').toString();
const business = (_in.business || 'our business').toString();
const callback_url = (_in.callback_url || '').toString();
const now = Date.now();
const at = (days) => new Date(now + days * 86400000).toISOString();
const steps = [
  { step: 1, day: 0, send_at: at(0), message: 'Hi ' + name + '! Thanks for your interest in ' + interest + ' at ' + business + '. Our team will call you within 30 minutes.' },
  { step: 2, day: 2, send_at: at(2), message: 'Hi ' + name + '! Just checking in - still interested in ' + interest + '? Reply YES and we will schedule your free consultation.' },
  { step: 3, day: 7, send_at: at(7), message: 'Hi ' + name + ', last call - we are holding a free consultation slot for you this week at ' + business + '. Reply to claim it.' }
];
return [{ json: {
  status: 'sequence_started', name: name, phone: phone, email: email,
  interest: interest, business: business, callback_url: callback_url,
  hasCallback: callback_url.length > 10, steps: steps,
  step1_message: steps[0].message, step2_message: steps[1].message, step3_message: steps[2].message,
  receivedAt: new Date().toISOString()
}}];
"""
n1 = [
    webhook("f1", "Follow-Up Webhook", "followup-start", 200, "f1f1f1f1-0000-4000-8000-000000000001"),
    code("f2", "Build Sequence", followup_js, 420),
    respond("f3", "Send Plan", 640),
    ifbool("f4", "Has Callback?", "={{ $json.hasCallback }}", 860),
    http_post("f5", "Send Step 1 (Day 0)", "={{ $json.callback_url }}",
              "={{ JSON.stringify({ to: $json.phone, step: 1, message: $json.step1_message }) }}", 1080),
    wait_days("f6", "Wait 2 Days", 2, 1300),
    http_post("f7", "Send Step 2 (Day 2)", "={{ $json.callback_url }}",
              "={{ JSON.stringify({ to: $json.phone, step: 2, message: $json.step2_message }) }}", 1520),
    wait_days("f8", "Wait 5 Days", 5, 1740),
    http_post("f9", "Send Step 3 (Day 7)", "={{ $json.callback_url }}",
              "={{ JSON.stringify({ to: $json.phone, step: 3, message: $json.step3_message }) }}", 1960),
]
c1 = link([("Follow-Up Webhook", "Build Sequence"), ("Build Sequence", "Send Plan"),
           ("Send Plan", "Has Callback?"), ("Has Callback?", "Send Step 1 (Day 0)"),
           ("Send Step 1 (Day 0)", "Wait 2 Days"), ("Wait 2 Days", "Send Step 2 (Day 2)"),
           ("Send Step 2 (Day 2)", "Wait 5 Days"), ("Wait 5 Days", "Send Step 3 (Day 7)")])
# fix: IF false branch should end (single output entry only on true)
c1["Has Callback?"] = {"main": [[{"index": 0, "node": "Send Step 1 (Day 0)", "type": "main"}], []]}
save("vq-followup-engine.json", "VQ Follow-Up Engine", n1, c1)

# ============ 2. VQ Website Chatbot ============
ctx_js = GUARD + """
const session_id = (_in.session_id || 's-' + Date.now()).toString();
const message = (_in.message || '').toString();
const history = (Array.isArray(_in.history) ? _in.history : []).slice(-9);
history.push({ role: 'user', text: message });
return [{ json: { session_id: session_id, history: history, message: message } }];
"""
ans_js = GUARD + """
const msg = (_in.message || '').toLowerCase();
const phoneHit = (_in.message || '').match(/(\\+?\\d[\\d\\s-]{7,14}\\d)/);
const emailHit = (_in.message || '').match(/[\\w.%-]+@[\\w.-]+\\.[a-zA-Z]{2,}/);
const faqs = [
  { k: ['price', 'cost', 'charge', 'fee', 'quote'], a: 'Our plans are tailored to your needs and start affordably. Share your phone number and our team will call with an exact quote within 30 minutes.' },
  { k: ['timing', 'open', 'hours', 'when'], a: 'We are open 9 AM to 9 PM, all 7 days.' },
  { k: ['location', 'address', 'where'], a: 'We serve customers across the city. Share your area and we will guide you to the nearest option.' },
  { k: ['book', 'appointment', 'visit', 'schedule'], a: 'Sure! Please share your name and phone number and we will confirm your slot right away.' },
  { k: ['service', 'offer', 'what do you do'], a: 'We handle enquiries, bookings, follow-ups and reminders for your business - 24/7, automatically.' }
];
let reply = null, lead = null;
if (phoneHit || emailHit) {
  lead = { phone: phoneHit ? phoneHit[0] : '', email: emailHit ? emailHit[0] : '' };
  reply = 'Thanks! Our team will call you within 30 minutes to help further.';
} else {
  const hit = faqs.find(f => f.k.some(k => msg.includes(k)));
  reply = hit ? hit.a : null;
}
const history = (_in.history || []).concat([{ role: 'assistant', text: reply || '__handoff__' }]);
return [{ json: { session_id: _in.session_id, history: history, reply: reply,
  fallback: !reply, lead_captured: !!lead, lead: lead } }];
"""
handoff_js = GUARD + """
const history = (_in.history || []).slice(0, -1).concat(
  [{ role: 'assistant', text: 'Thanks for reaching out! Connecting you to our team - they will join within 2 minutes. Meanwhile, what is your phone number?' }]);
return [{ json: { session_id: _in.session_id, history: history,
  reply: 'Thanks for reaching out! Connecting you to our team - they will join within 2 minutes. Meanwhile, what is your phone number?',
  fallback: true, lead_captured: !!_in.lead_captured, lead: _in.lead || null } }];
"""
n2 = [
    webhook("g1", "Chat Webhook", "chat", 200, "f2f2f2f2-0000-4000-8000-000000000002"),
    code("g2", "Build Context", ctx_js, 420),
    code("g3", "Answer", ans_js, 640),
    ifbool("g4", "Fallback?", "={{ $json.fallback }}", 860),
    code("g5", "Human Handoff", handoff_js, 1080),
    respond("g6", "Send Chat Reply", 1300),
]
c2 = link([("Chat Webhook", "Build Context"), ("Build Context", "Answer"),
           ("Answer", "Fallback?"), ("Fallback?", "Human Handoff"),
           ("Human Handoff", "Send Chat Reply")])
c2["Fallback?"] = {"main": [[{"index": 0, "node": "Human Handoff", "type": "main"}],
                            [{"index": 0, "node": "Send Chat Reply", "type": "main"}]]}
save("vq-website-chatbot.json", "VQ Website Chatbot", n2, c2)

# ============ 3. VQ Local SEO Audit Agent ============
audit_js = """
const _raw = $input.first().json;
let html = '';
if (typeof _raw.data === 'string') html = _raw.data;
else if (typeof _raw === 'string') html = _raw;
else html = JSON.stringify(_raw);
// NOTE: the HTTP node replaces the item, so webhook fields (business_name etc.)
// are NOT in $input here. Pull them from the Webhook node directly.
let meta = {};
try {
  const w = $('Audit Webhook').first().json;
  meta = (w && typeof w === 'object' && w.body && typeof w.body === 'object') ? w.body : (w || {});
} catch (e) { meta = {}; }
const get = (k, d) => {
  const v = (meta[k] !== undefined && meta[k] !== null) ? meta[k] : _raw[k];
  return (v === undefined || v === null ? d : v).toString();
};
const business = get('business_name', 'the business');
const url = get('website_url', '') || get('url', '');
const location = get('location', '');
const keyword = get('keyword', '');
const lower = html.toLowerCase();

const checks = [];
const add = (name, pass, fix, weight) => checks.push({ check: name, pass: !!pass, fix: fix, weight: weight });
const title = (html.match(/<title[^>]*>([^<]*)<\\/title>/i) || [])[1] || '';
add('Title tag present', title.length > 0, 'Add a <title> tag with business + keyword.', 15);
add('Title length 30-60 chars', title.length >= 30 && title.length <= 60, 'Keep title between 30-60 characters. Current: ' + title.length + '.', 10);
const desc = (html.match(/<meta[^>]*name=["']description["'][^>]*content=["']([^"']*)["']/i) || [])[1] || '';
add('Meta description present', desc.length > 0, 'Add a meta description (120-160 chars).', 15);
const h1 = (lower.match(/<h1[\\s>]/g) || []).length;
add('H1 heading present', h1 >= 1, 'Add exactly one <h1> with your main keyword.', 10);
add('Mobile viewport meta', /<meta[^>]*name=["']viewport["']/i.test(html), 'Add <meta name="viewport" content="width=device-width, initial-scale=1">.', 10);
add('HTTPS', url.toLowerCase().indexOf('https://') === 0, 'Serve the site over HTTPS.', 10);
add('Schema.org / JSON-LD markup', /schema\\.org|application\\/ld\\+json/i.test(html), 'Add LocalBusiness JSON-LD schema for rich results.', 10);
add('Canonical tag', /<link[^>]*rel=["']canonical["']/i.test(html), 'Add a canonical link tag.', 5);
add('Open Graph tags', /property=["']og:/i.test(html), 'Add Open Graph tags for social sharing.', 5);
const imgs = (lower.match(/<img[\\s>]/g) || []).length;
const alts = (lower.match(/<img[^>]*alt=["'][^"']+["']/g) || []).length;
add('Images have alt text', imgs === 0 || alts >= imgs * 0.8, alts + '/' + imgs + ' images have alt text. Add descriptive alt attributes.', 5);
const words = html.replace(/<[^>]*>/g, ' ').split(/\\s+/).filter(w => w.length > 2).length;
add('Enough content (300+ words)', words >= 300, 'Add more descriptive content. Current ~' + words + ' words.', 5);

let score = 0, maxW = 0;
const fixes = [];
checks.forEach(c => { maxW += c.weight; if (c.pass) score += c.weight; else fixes.push(c.fix); });
score = Math.round(score / maxW * 100);
const grade = score >= 90 ? 'A' : score >= 75 ? 'B' : score >= 60 ? 'C' : score >= 40 ? 'D' : 'F';
return [{ json: {
  business_name: business, website_url: url, location: location, keyword: keyword,
  score: score, grade: grade,
  summary: business + ' scores ' + score + '/100 (grade ' + grade + ') on on-page SEO basics. ' + fixes.length + ' fixes recommended.',
  checks: checks, fixes: fixes,
  note: 'This audit covers on-page SEO basics checkable without paid APIs. Google Maps ranking position needs a SERP API (paid) - ask us for the full audit.',
  receivedAt: new Date().toISOString()
}}];
"""
prep_js = GUARD + """
const b = _in;
const url = (b.website_url || b.url || '').toString().trim();
return [{ json: { website_url: url, business_name: (b.business_name || 'the business').toString(),
  location: (b.location || '').toString(), keyword: (b.keyword || '').toString(),
  valid: /^https?:\\/\\//i.test(url), receivedAt: new Date().toISOString() } }];
"""
n3 = [
    webhook("h1", "Audit Webhook", "seo-audit", 200, "f3f3f3f3-0000-4000-8000-000000000003"),
    code("h1b", "Prepare Audit", prep_js, 460),
    http_get("h2", "Fetch Site", "={{ $json.website_url }}", 720),
    code("h3", "Audit Site", audit_js, 980),
    respond("h4", "Send Audit", 1240),
]
c3 = link([("Audit Webhook", "Prepare Audit"), ("Prepare Audit", "Fetch Site"), ("Fetch Site", "Audit Site"), ("Audit Site", "Send Audit")])
save("vq-seo-audit-agent.json", "VQ Local SEO Audit Agent", n3, c3)

# ============ 4. VQ Ad Lead Instant Responder ============
ad_js = GUARD + """
const name = (_in.name || 'there').toString().trim();
const phone = (_in.phone || '').toString();
const email = (_in.email || '').toString();
const campaign = (_in.campaign || 'our ad').toString();
const adset = (_in.adset || '').toString();
const platform = (_in.platform || 'meta').toString().toLowerCase();
const form = (_in.form_name || '').toString();

let score = 0; const reasons = [];
if (phone.replace(/\\D/g, '').length >= 10) { score += 40; reasons.push('Valid phone (+40)'); }
if (/@/.test(email)) { score += 25; reasons.push('Email provided (+25)'); }
if (name && name !== 'there') { score += 15; reasons.push('Name provided (+15)'); }
if (campaign && campaign !== 'our ad') { score += 20; reasons.push('High-intent campaign: ' + campaign + ' (+20)'); }
const tier = score >= 70 ? 'HOT' : score >= 40 ? 'WARM' : 'COLD';
return [{ json: {
  name: name, phone: phone, email: email, campaign: campaign, adset: adset,
  platform: platform, form_name: form, score: score, tier: tier, reasons: reasons,
  instantReply: 'Hi ' + name + '! Thanks for your interest in ' + campaign + '. Our team will call you within 30 minutes with details.',
  nextAction: tier === 'HOT' ? 'Call within 30 min (HOT ad lead)' : 'Follow up within 4 hours',
  receivedAt: new Date().toISOString()
}}];
"""
n4 = [
    webhook("i1", "Ad Lead Webhook", "ad-lead", 200, "f4f4f4f4-0000-4000-8000-000000000004"),
    code("i2", "Qualify Ad Lead", ad_js, 460),
    ifequals("i3", "Is Hot?", "={{ $json.tier }}", "HOT", 720),
    respond("i4", "Send Response", 980),
]
c4 = link([("Ad Lead Webhook", "Qualify Ad Lead"), ("Qualify Ad Lead", "Is Hot?")])
c4["Is Hot?"] = {"main": [[{"index": 0, "node": "Send Response", "type": "main"}],
                          [{"index": 0, "node": "Send Response", "type": "main"}]]}
save("vq-ad-lead-responder.json", "VQ Ad Lead Instant Responder", n4, c4)

# ============ 5. VQ Review Request Agent ============
rev_js = GUARD + """
const name = (_in.name || 'there').toString().trim();
const phone = (_in.phone || '').toString();
const rating = parseInt(_in.rating || '0', 10);
const review_link = (_in.review_link || '').toString();
const business = (_in.business || 'our business').toString();
const happy = rating >= 4;
return [{ json: {
  name: name, phone: phone, rating: rating, business: business, happy: happy,
  message: happy
    ? 'Hi ' + name + '! Glad you loved ' + business + '. It takes 30 seconds to review us here: ' + review_link + ' - thank you!'
    : 'ALERT: ' + name + ' rated ' + rating + '/5. Call ' + phone + ' within 1 hour to resolve before they review publicly.',
  action: happy ? 'send_review_link' : 'alert_owner',
  receivedAt: new Date().toISOString()
}}];
"""
n5 = [
    webhook("j1", "Review Webhook", "review-ask", 200, "f5f5f5f5-0000-4000-8000-000000000005"),
    code("j2", "Check Rating", rev_js, 460),
    ifbool("j3", "Happy?", "={{ $json.happy }}", 720),
    respond("j4", "Send Result", 980),
]
c5 = link([("Review Webhook", "Check Rating"), ("Check Rating", "Happy?")])
c5["Happy?"] = {"main": [[{"index": 0, "node": "Send Result", "type": "main"}],
                         [{"index": 0, "node": "Send Result", "type": "main"}]]}
save("vq-review-agent.json", "VQ Review Request Agent", n5, c5)
