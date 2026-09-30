# VQ Automation Protocol

How our n8n workflows actually work — the JSON, the methods, the logic, and why
each choice was made. Read this once and you can build, debug, and extend any
functional n8n automation yourself. It also defines how any frontend talks to
n8n as its backend.

---

## 0. The big picture (30 seconds)

```
Any frontend (website/app)  --POST JSON-->  n8n Webhook node  -->  Code/IF nodes  -->  Respond node  --JSON-->
```

- n8n is the **backend**. Each workflow exposes one HTTP endpoint (the Webhook node).
- The frontend never touches n8n's editor. It only calls the webhook URL.
- Data inside n8n travels as **items**: every node outputs a list like `[{ json: { ... } }]`.

---

## 1. How data moves INSIDE n8n (the part that confuses everyone)

Three ways to read data, depending on where you are:

| Where you are | How you read the data | Example |
|---|---|---|
| Code node (JavaScript) | `$input.first().json` | `const d = $input.first().json;` |
| Any expression field `{{ }}` | `$json` (current item) | `{{ $json.name }}` |
| Any expression, older node | `$('Node Name').json` | `{{ $('Detect Intent').json.intent }}` |

### The webhook body gotcha (real bug we hit and fixed)

When a frontend POSTs `{ "name": "Rahul" }`, n8n's Webhook node does NOT give you
`{ "name": "Rahul" }` directly. It wraps it:

```json
{ "headers": {...}, "params": {}, "query": {}, "body": { "name": "Rahul" } }
```

So `$input.first().json.name` is `undefined` — the real data is at `.json.body.name`.
**Our standard guard** (first two lines of every Code node):

```js
const _raw = $input.first().json;
const _in = (_raw && typeof _raw === 'object' && _raw.body && typeof _raw.body === 'object')
  ? _raw.body
  : _raw;
```

Now `_in.name` works whether the data came from a real webhook (`body` wrapper)
or from a manual test run (flat). Without this guard every workflow silently
returns empty/default values — exactly the bug we caught on the live Demo.

---

## 2. HTTP methods — GET, POST, PUT, PATCH, DELETE (universal)

A method tells the server what you want to DO. Same meanings everywhere
(n8n, REST APIs, your frontend's `fetch`):

| Method | Meaning | Data goes... | n8n example |
|---|---|---|---|
| GET | **Read** something | URL query: `?phone=98111` | Webhook trigger from a link; HTTP Request to fetch data |
| POST | **Create / submit** something | JSON body | Our webhooks receive leads; HTTP Request sends a lead to a CRM |
| PUT | **Replace** a whole record | JSON body | Update a full booking |
| PATCH | **Update** part of a record | JSON body | Mark a lead as "contacted" |
| DELETE | **Remove** something | URL path/query | Cancel a booking by ref |

**Rule of thumb:** GET = data in the URL (visible, bookmarkable, size-limited).
POST/PUT/PATCH = data in the body (private, structured JSON, any size).

### In the Webhook node (receiving)
We use **POST** for all our workflows because the frontend submits structured
data (name, phone, message). Use GET only for dead-simple triggers, e.g.
`https://n8n/webhook/ping?client=abc` — no body, just "it was hit".

### In the HTTP Request node (sending — when you call OTHER APIs)
- **Send JSON body:** Method = POST, "Send Body" = ON, "Body Content Type" = JSON,
  then write the body in the JSON field (see §3).
- **Query parameters:** Method = GET, add "Query Parameters" — n8n builds the
  `?key=value` string for you. Or hand-write: `https://api.example.com/check?phone={{ $json.phone }}`.

---

## 3. Custom JSON — how to write it, and the #1 mistake

A custom JSON body is just JSON with n8n **expressions** `{{ }}` mixed in.
n8n evaluates the `{{ }}` parts first, then sends the result.

```json
{
  "name": "{{ $json.name }}",
  "phone": "{{ $json.phone }}",
  "tier": "{{ $json.tier }}",
  "score": {{ $json.score }},
  "isHot": {{ $json.tier === 'HOT' }}
}
```

**The #1 mistake:** quotes.

- Text (string) → quotes REQUIRED: `"{{ $json.name }}"`
- Number / true / false → NO quotes: `{{ $json.score }}`
- `"{{ $json.score }}"` sends the number as text — downstream `score > 80`
  comparisons then break silently.

**Why `{{ }}` and not plain text?** Plain text is static — every lead gets the
same message. Expressions make it dynamic — each lead gets its own name, tier,
booking ref. That is what turns a template into an agent.

---

## 4. The Code node — our standard pattern

Every Code node in our workflows follows the same skeleton. Learn it once:

```js
// 1. UNWRAP — handle the webhook body shape (§1)
const _raw = $input.first().json;
const _in = (_raw && typeof _raw === 'object' && _raw.body && typeof _raw.body === 'object')
  ? _raw.body
  : _raw;

// 2. READ — pull fields with safe defaults
const name = (_in.name || 'there').toString().trim();

// 3. LOGIC — your rules (scoring, validation, intent, math)

// 4. RETURN — always an array of { json: ... }
return [{ json: { name: name, /* ... */ } }];
```

**Why Code node and not the Edit Fields (Set) node?**
Edit Fields is fine for dumb mapping (`firstName` → `name`). The moment you need
`if/else`, keyword lists, date math, or validation chains, Code is clearer and
shorter. Alternative path: you CAN do simple scoring with Edit Fields +
expressions, but a 40-line rule set becomes unreadable there.

**Why `return [{ json: ... }]`?** n8n items. Forget the array wrapper and the
next node sees nothing.

---

## 5. Branching — IF vs Switch

- **IF node** = true/false fork. We use it everywhere: "Slot OK?" (confirmed vs
  rejected), "Needs Human?" (true/false), "Is After Hours?".
- **Switch node** = 3+ branches. Alternative path: the Enquiry Agent COULD use
  Switch on `intent` (booking/pricing/info/complaint/other → 5 different reply
  chains). We chose IF + one smart Code node because the reply differences are
  small — one node instead of five.

**Why both branches go to the same Respond node?** The response contract is
identical (a JSON reply); only the content differs. One Respond node = one
contract.

---

## 6. Respond to Webhook — closing the loop

Two modes:

| Mode | Behaviour | When to use |
|---|---|---|
| `responseNode` (ours) | Waits for the LAST node, returns its JSON | Frontend needs the result (booking ref, reply text) |
| `onReceived` | Replies instantly "ok", workflow continues in background | Fire-and-forget (logging, slow jobs) |

We use `responseNode` with `responseBody = {{ $json }}` so the frontend gets the
full result object in one round trip.

---

## 7. The three pitch workflows — logic and WHY

### 7a. VQ AI Enquiry Agent (pitch: "answers every enquiry instantly, qualifies intent — 24/7")
- **Intent detection:** keyword lists per intent, checked in priority order
  (complaint > booking > pricing > info > other). Priority order matters:
  "I want to cancel my booking" contains "book" but is a complaint — complaint
  wins because it's checked first.
- **Urgency:** keyword scan (`urgent`, `asap`, `today`, `call me`) OR complaint
  intent → `needsHuman = true` → IF node routes to the priority reply.
- **Channel-aware replies:** WhatsApp/SMS get ≤1 short paragraph (people don't
  read essays in chat); email/web get the full version. Same intent, different
  packaging.
- **Alternative path:** a real LLM (OpenAI/Anthropic) could classify intent
  instead of keywords — more accurate, but costs money per message and adds
  latency. Keywords are free, instant, and good enough for 5 intents. Upgrade
  path: swap the keyword block for an HTTP Request to an LLM later without
  touching the rest.

### 7b. VQ Smart Booking Agent (pitch: "books the viewing/appointment — 24/7", "sends reminders")
- **Validation chain order is deliberate:** format → exists → not-past →
  ≥2h notice → business hours → party size. Cheap checks first, each failure
  returns `status: "rejected"` WITH a `fix` hint ("Send date as YYYY-MM-DD").
  No silent failures — the frontend can show the fix to the user.
- **Booking ref:** `VQ-` + time-based + random suffix. Unique enough for a demo/
  SMB; a production version would check a database for collisions.
- **Reminder math:** `reminderAt = slotStart − 24h`, computed at booking time so
  any scheduler (n8n Wait node, cron, or the client's system) can consume it.
- **Alternative path:** with Google credentials, add Google Calendar "Create
  Event" after validation (that's what the older Pro/Booking workflows do).
  This credential-free version proves the logic; the calendar is just a sink.

### 7c. VQ After-Hours Lead Catcher (pitch: "No missed leads after hours")
- **Business-hours math:** everything in minutes-since-midnight; `afterHours =
  mins < open || mins >= close`. Simple, no date library needed.
- **Next-opening calculation:** set clock to opening time today; if that's not in
  the future, +1 day. The callback task carries `callAt`, `phone`, `priority`.
- **In-hours misses** still get a text-back ("callback within 15 min") — the
  promise is "no missed lead", not only "no after-hours lead".
- **Alternative path:** connect a telephony provider (Exotel/Ozonetel/Twilio)
  webhook as the trigger source instead of manual POSTs — the workflow logic
  doesn't change, only the trigger.

---

## 8. n8n as backend — the frontend contract

Your UI (hosted anywhere — Vercel, Netlify, Cloudflare Pages, your own VPS)
talks to n8n ONLY through webhook URLs. n8n's editor is never exposed.

### 8a. Calling a workflow from JavaScript

```js
const res = await fetch('https://automation-832k.onrender.com/webhook/enquiry-in', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    channel: 'web',
    name: 'Rohan',
    phone: '9811111111',
    business: 'Sunrise Dental',
    message: 'I want to book an appointment'
  })
});
const data = await res.json();
// data = { intent: 'booking', reply: 'Hi Rohan! ...', nextAction: '...', ... }
// → render data.reply in the chat bubble
```

Endpoint per workflow: `https://<your-n8n-domain>/webhook/<path>`
(`enquiry-in`, `agent-booking`, `missed-call` for the three above.)

### 8b. The response contract (frontend rules)

1. Our workflows ALWAYS return HTTP 200 with a JSON body. Business outcomes
   live in fields, not status codes: `status: "confirmed" | "rejected"`,
   `intent`, `tier`, `afterHours`, etc.
2. Frontend logic: `if (data.status === 'confirmed') showSuccess(data)` —
   never assume success from HTTP 200 alone.
3. On `rejected`, show `data.reason` + `data.fix` to the user (we write them
   human-readable on purpose).

### 8c. CORS (the thing that bites frontend devs)

Browsers block a page on `your-site.com` from calling `n8n-domain.com` unless
the server allows it. n8n answers preflight (OPTIONS) requests on webhook
paths, so direct browser calls usually work. If a client's browser still
blocks it, the fix is a tiny same-origin proxy (e.g. a 20-line serverless
function on your hosting that forwards to n8n) — the workflow doesn't change.

### 8d. Security basics

- Webhook URLs are unguessable paths, but they're still public URLs. For client
  deployments, add a shared secret: frontend sends `{ "secret": "client-key" }`,
  first lines of the Code node reject mismatches:
  `if (_in.secret !== 'client-key') return [{ json: { status: 'rejected', reason: 'unauthorized' } }];`
- Never expose the n8n editor URL or credentials to the frontend.

### 8e. Multi-tenant pattern (how this becomes a business)

One n8n instance serves MANY clients: every request carries `business` (and
`business_open`/`business_close`). Same workflow, per-client behaviour, zero
per-client infrastructure. That is the sellable shape: onboard a client by
giving them a snippet, not a server.

---

## 9. Build-your-own checklist (the method, distilled)

1. **Write the JSON contract first** — input fields and output fields on paper
   before opening n8n.
2. **Webhook (POST, path)** → **Code (guard + logic + `return [{json}]`)** →
   **IF/Switch** → **Respond (`{{ $json }}`)**.
3. **Test with curl** before any UI exists. If curl works, the workflow works.
4. **Then** build the frontend `fetch` against the verified endpoint.
5. **Document the contract** (inputs, outputs, status values) — that's this file.

---

*Built by VisionQuantech. Workflows: VQ AI Enquiry Agent, VQ Smart Booking
Agent, VQ After-Hours Lead Catcher (+ VQ Instant Lead Responder series).*

---

# PART B — Har node mein kya dala (agent-wise recipes)

Har agent ke liye: kaun se nodes, aur har node ke andar **exact kya configuration**.
Pattern sab me ek hi hai — Webhook (andar lao) → Code (samjho/decide karo) →
IF/Switch (raasta chuno) → Action (HTTP/Gmail/Calendar) → Respond (wapas batao).

---

## B1. WhatsApp AI Agent (inbound auto-reply)

Pitch: "AI agents handle enquiries instantly — WhatsApp — 24/7"

1. **WhatsApp Webhook** (type: Webhook)
   - HTTP Method: POST, Path: `wa-in`, Respond: When Last Node Finishes
   - Kyun: WhatsApp provider (Twilio / Meta Cloud API / WATI / Gupshup) har
     incoming message pe isi URL ko POST karta hai.

2. **Normalize Input** (type: Code)
   - Andar kya: body guard (§1) + har provider ka alag shape ek shape me:
   ```js
   const _raw = $input.first().json;
   const _in = (_raw.body && typeof _raw.body === 'object') ? _raw.body : _raw;
   // Twilio (form-encoded): _in.Body, _in.From
   // Meta Cloud API: _in.entry[0].changes[0].value.messages[0]
   const m = (_in.entry && _in.entry[0].changes[0].value.messages[0]) || {};
   const message = _in.Body || (m.text && m.text.body) || '';
   const phone = (_in.From || m.from || '').toString().replace('whatsapp:', '');
   return [{ json: { phone: phone, message: message, channel: 'whatsapp', name: 'there' } }];
   ```
   - Kyun Code: provider badla to sirf ye node badlega, baaki workflow same.

3. **Detect Intent** (type: Code) — §7a wala keyword engine (booking/pricing/info/complaint/other).

4. **Needs Human?** (type: IF) — condition: `{{ $json.needsHuman }}` is `true`.

5. **Send WhatsApp Reply** (type: HTTP Request) — do raaste, ek hi pattern (§2 + §3):
   - Meta Cloud API: Method POST,
     URL `https://graph.facebook.com/v21.0/YOUR_PHONE_NUMBER_ID/messages`,
     Header `Authorization: Bearer YOUR_TOKEN`, Body JSON:
   ```json
   { "messaging_product": "whatsapp", "to": "{{ $json.phone }}",
     "type": "text", "text": { "body": "{{ $json.reply }}" } }
   ```
   - Twilio: Method POST,
     URL `https://api.twilio.com/2010-04-01/Accounts/ACxxxx/Messages.json`,
     Authentication: Basic Auth (n8n credential: username = Account SID,
     password = Auth Token), Body (x-www-form-urlencoded):
     `From` = `whatsapp:+14155238886`, `To` = `whatsapp:{{ $json.phone }}`,
     `Body` = `{{ $json.reply }}`.
   - Kyun HTTP Request: WhatsApp bhejna = doosre API ko POST karna.

6. **Respond** (type: Respond to Webhook) — `{ status: 'replied', to, intent }`.

---

## B2. Email AI Agent (inbound triage + reply)

Pitch: "AI agents handle enquiries instantly — email — 24/7"

1. **Email Trigger** — do raaste:
   - Gmail Trigger node (Google OAuth chahiye; "on new email" poll karta hai), ya
   - Webhook POST `email-in` (koi bhi email parser → n8n; **credential-free**):
     fields `from`, `subject`, `body`.
2. **Classify** (type: Code)
   - Andar kya: subject+body pe keyword scan → `intent`
     (support/billing/partnership/spam) + `priority`
     (`refund`, `legal`, `urgent`, `cancel` aaye to `high`).
3. **High Priority?** (type: IF) — `{{ $json.priority }}` equals `high`.
4. **Draft Reply** (type: Code)
   - Andar kya: intent-wise template map:
   ```js
   const t = {
     billing: 'Hi ' + name + ', your billing query is noted. Our team replies within 4 business hours with the invoice details.',
     support: 'Hi ' + name + ', thanks for writing in. ' + 'Can you share your order/account ID so we resolve this in one go?',
     partnership: 'Hi ' + name + ', thanks for reaching out! Our partnerships team will schedule a call this week.'
   };
   return [{ json: { draftSubject: 'Re: ' + _in.subject, draftBody: t[intent] || t.support } }];
   ```
5. **Send Email** (type: Gmail) — Operation: Send, To: `={{ $json.email }}`,
   Subject: `={{ $json.draftSubject }}`, Email Type: Text,
   Message: `={{ $json.draftBody }}`. (Bina OAuth: HTTP Request → SMTP/API provider.)
6. **Respond/Log** — `{ status: 'sent', intent, priority }`.

---

## B3. Calling AI Agent (IVR-style inbound + outbound)

Sach: awaaz ka kaam Twilio/Exotel karta hai; **n8n dimaag hai**.

1. **Call Webhook** (type: Webhook, POST, path `call-in`)
   - Andar kya: provider har call event pe `Caller`, `CallSid`, `DialWhomNumber` bhejta hai.
2. **Route Call** (type: Code)
   - Andar kya: caller normalize + business-hours check (§7c jaisa) + VIP list lookup.
3. **After Hours?** (type: IF) — `{{ $json.afterHours }}` is `true`.
4. **Answer with Voice Script** (type: Respond to Webhook) — **sabse important node**:
   Voice providers webhook ke RESPONSE ko call script maante hain.
   - Respond With: Text. Response Headers me `Content-Type: text/xml`. Body:
   ```xml
   <Response>
     <Say voice="alice">Thanks for calling Sunrise Dental. Press 1 to book an appointment, 2 for clinic timings.</Say>
     <Gather numDigits="1" action="https://YOUR-N8N-DOMAIN/webhook/call-choice" method="POST"/>
   </Response>
   ```
   - Kyun: TwiML/Exotel XML = IVR, bina kisi voice-AI kharche ke. Digit dabane pe
     provider `call-choice` webhook ko POST karta hai → wahan Code digit padhta hai →
     agla `<Say>` / `<Dial>` response.
5. **Outbound alternative** (type: HTTP Request): n8n se call INITIATE karna —
   Method POST, URL `https://api.exotel.com/v1/Accounts/YOUR_SID/Calls/connect.json`,
   Basic Auth, form body: `From={{ $json.agent_number }}`, `To={{ $json.customer }}`,
   `CallerId=YOUR_NUMBER`, `Url=https://YOUR-N8N-DOMAIN/webhook/call-in`.
   Provider pehle agent ko, phir customer ko jodta hai.

---

## B4. Data Analyst AI Agent

Pitch (naya): "Apna sales/data bhejo, AI turant analysis + insights dega"

1. **Analyze Webhook** (type: Webhook, POST, path `analyze`)
   - Andar kya: `{ rows: [ {...}, {...} ] }` ya `{ csv_url: "https://..." }`.
2. **Fetch CSV** (type: HTTP Request, optional) — sirf jab `csv_url` aaye:
   Method GET, URL `={{ $json.csv_url }}`. IF node (`{{ $json.csv_url }}` not empty)
   se skip karo jab rows seedha aaye hon.
3. **Analyze** (type: Code) — pure JS, koi credential nahi:
   ```js
   const rows = _in.rows;
   const total = rows.reduce((s, r) => s + (+r.amount || 0), 0);
   const byRegion = {};
   rows.forEach(r => { const k = r.region || 'Unknown'; byRegion[k] = (byRegion[k] || 0) + (+r.amount || 0); });
   const top3 = Object.entries(byRegion).sort((a, b) => b[1] - a[1]).slice(0, 3);
   return [{ json: { rows: rows.length, total: total, avg: total / rows.length, byRegion: byRegion, top3: top3 } }];
   ```
4. **Write Insights** (type: Code)
   - Andar kya: numbers → human-readable lines:
   `"Total sales ₹" + total + " across " + rows.length + " orders. Top region: " + top3[0][0] + "."`
5. **Respond** — `{ insights: [...], stats: {...} }`. Frontend table/chart banata hai.

---

## B5. Data Scientist AI Agent (lead scoring / prediction)

Pitch (naya): "Har lead ka AI score — kaun HOT hai, kaun time waste hai"

1. **Score Webhook** (type: Webhook, POST, path `score`)
   - Andar kya: feature JSON, e.g. `{ budget, timeline, need, contact_age_days }`.
2. **Feature Engineering** (type: Code)
   - Andar kya: normalize + defaults + derived features:
   `const days = Math.max(0, parseInt(_in.contact_age_days || '0', 10));`
3. **Predict** (type: Code) — transparent weighted model:
   ```js
   let score = 0; const reasons = [];
   if ((_in.budget || '') === 'high') { score += 30; reasons.push('High budget (+30)'); }
   if ((_in.timeline || '') === 'immediate') { score += 25; reasons.push('Immediate timeline (+25)'); }
   if (days <= 2) { score += 15; reasons.push('Fresh lead (+15)'); }
   const tier = score >= 70 ? 'HOT' : score >= 40 ? 'WARM' : 'COLD';
   return [{ json: { score: score, tier: tier, reasons: reasons } }];
   ```
   - Kyun rule-based: free, instant, **explainable** (`reasons[]` client ko dikha
     sakte ho). Upgrade path: HTTP Request → real ML endpoint; contract same rahega.
4. **Hot?** (type: IF) — `{{ $json.tier }}` equals `HOT` → turant action branch.
5. **Respond** — `{ score, tier, reasons }`.

---

## B6. Booking / Inquiry AI Agents (built — node recap)

- **VQ AI Enquiry Agent**: Enquiry Webhook (POST `enquiry-in`) → Detect Intent
  (Code: keyword lists, priority order complaint>booking>pricing>info>other,
  channel-aware replies) → Needs Human? (IF `{{ $json.needsHuman }}` true) →
  Send Reply (Respond `{{ $json }}`).
- **VQ Smart Booking Agent**: Booking Webhook (POST `agent-booking`) →
  Validate & Book (Code: validation chain format→past→2h notice→hours 09–21→party
  size; ref `VQ-XXXXXX`; `reminderAt = slot − 24h`) → Slot OK? (IF
  `{{ $json.status }}` equals `confirmed`) → Confirm Booking (Respond).
- (Poora code: respective `workflow.json` me.)

---

## B7. Website Chatbot

Pitch: "Website pe 24/7 AI chat — visitor sawal puche, AI jawab de, lead pakde"

1. **Chat Webhook** (type: Webhook, POST, path `chat`)
   - Andar kya: `{ session_id, message, history: [] }`. **Frontend session rakhta
     hai, backend stateless** — scale ka sabse aasaan tareeka.
2. **Build Context** (type: Code)
   - Andar kya: history me naya message jodo, last 10 rakho:
   ```js
   const h = (_in.history || []).concat([{ role: 'user', text: _in.message }]).slice(-10);
   return [{ json: { session_id: _in.session_id, history: h, message: _in.message } }];
   ```
3. **Answer** (type: Code) — FAQ keyword engine (free):
   ```js
   const faqs = [
     { k: ['price', 'cost', 'charge'], a: 'Our plans start at ₹X/month. Want a callback with exact quote?' },
     { k: ['timing', 'open', 'hours'], a: 'We are open 9 AM – 9 PM, all days.' },
     { k: ['book', 'appointment'], a: 'Sure! Please share your name and phone number to book.' }
   ];
   const hit = faqs.find(f => f.k.some(k => msg.includes(k)));
   return [{ json: { reply: hit ? hit.a : null, fallback: !hit } }];
   ```
   Alternative: HTTP Request → LLM API (paid, smarter). Contract same.
4. **Fallback?** (type: IF) — `{{ $json.fallback }}` true → human handoff reply.
5. **Respond** — `{ reply, session_id, history }` → website widget bubble me render.

---

## B8. Bonus: Follow-Up Agent + Review Agent

**Follow-Up Agent** (pitch: har pitch me "+ follow-up"):
1. Webhook (lead: name/phone/interest) → 2. **Build Sequence** (Code):
   Day 0 thank-you, Day 2 nudge, Day 7 last-call — har step pe exact timestamp +
   personalized message → 3. Respond with plan. Bhejna: **Wait** node (delay) →
   **HTTP Request** POST to client's send-URL. Logic aur sending alag — plan
   testable, sending pluggable.

**Review Request Agent** (SEO pitch se judta hai — "reviews"):
1. Webhook (service completed: name/phone/rating) → 2. **Happy?** (IF
   `{{ $json.rating }}` >= 4) → true: Google review link wala message bhejo
   (HTTP Request → SMS/WhatsApp provider); false: internal complaint alert
   (HTTP Request → owner email/Slack webhook).

---

*Pattern yaad rakho: Webhook → Code → IF/Switch → Action → Respond.
Ye pattern pakad liya to upar ka koi bhi agent — aur "many more" — bana loge.*

---

# PART C — Naye 5 agents: node recap + ek nayi technique

## C1. VQ Follow-Up Engine
- Follow-Up Webhook (POST `followup-start`) → Build Sequence (Code: Day 0/2/7
  steps, exact `send_at` timestamps, `hasCallback` flag) → Send Plan (Respond:
  plan **turant** wapas) → Has Callback? (IF boolean) → [true] Send Step 1
  (HTTP POST `{{ $json.callback_url }}`) → Wait 2 Days → Send Step 2 → Wait 5 Days
  → Send Step 3; [false] end.
- **Nayi technique — beech me Respond:** responseNode mode me Respond node jahan
  execute hota hai, response wahin bhej deta hai; uske baad ke nodes background
  me chalte rehte hain. Isliye plan turant milta hai aur lambe Wait nodes peeche
  kaam karte hain. (Note: lambe waits ko persistent n8n chahiye — free Render ke
  sleep/restart me toot sakte hain.)

## C2. VQ Website Chatbot
- Chat Webhook (POST `chat`: `session_id`, `message`, `history[]`) → Build Context
  (Code: history append, last 10 rakho) → Answer (Code: FAQ keyword map +
  phone/email regex se lead capture) → Fallback? (IF `{{ $json.fallback }}`)
  → [true] Human Handoff (Code) → Send Chat Reply (Respond); [false] seedha Respond.
- Technique: **stateless backend** — session_id aur history frontend rakhta hai.
  Har client ke liye `faqs` array edit karo, workflow same.

## C3. VQ Local SEO Audit Agent
- Audit Webhook (POST `seo-audit`) → Fetch Site (HTTP Request GET
  `={{ $json.website_url }}`) → Audit Site (Code: 11 on-page checks → score
  0–100, grade A–F, fix list) → Send Audit (Respond).
- **Nayi technique — khoya hua data wapas lao:** HTTP Request node item ko
  replace kar deta hai, to webhook ke fields (`business_name`...) Code node tak
  pahuchte hi nahi. Fix — purane node se seedha padho:
  ```js
  const w = $('Audit Webhook').first().json;
  const meta = (w && w.body && typeof w.body === 'object') ? w.body : (w || {});
  ```
  Yehi pattern jab bhi beech ka node item badal de (HTTP, Set, Merge...).

## C4. VQ Ad Lead Instant Responder
- Ad Lead Webhook (POST `ad-lead`: name/phone/email/campaign/adset/platform) →
  Qualify Ad Lead (Code: weighted score — phone +40, email +25, name +15,
  high-intent campaign +20 → tier + `reasons[]`) → Is Hot? (IF
  `{{ $json.tier }}` equals `HOT`) → Send Response (Respond).
- Meta Lead Ads / Google Lead Forms ka webhook isi URL pe lagao — lead aate hi
  jawab.

## C5. VQ Review Request Agent
- Review Webhook (POST `review-ask`: name/phone/rating/review_link) → Check Rating
  (Code: `happy = rating >= 4`, dono messages compose) → Happy? (IF boolean) →
  Send Result (Respond). Happy → review link wala message; unhappy → owner alert
  ("1 hour me call karo, public review se pehle").
- Trigger: billing/CRM ke "service completed" event se.

---

# PART D — Batch 3: baaki pitch promises (node recap)

Pitches me 4 service tracks se zyada tha — SaaS support, agency SDR, ops document
agent bhi becha gaya tha. Ye 10 workflows un sabko cover karte hain.

## D1. VQ WhatsApp AI Agent
- WhatsApp Webhook (POST `wa-in`) → Normalize Input (Code: Twilio form-encoded
  AUR Meta Cloud API JSON — dono shapes → ek shape) → Detect Intent (Code:
  complaint>booking>pricing>info>other) → Has Sender? (IF) → [true] Send WhatsApp
  (HTTP POST `{{ $json.callback_url }}`) → Send Result (Respond); [false] seedha Respond.

## D2. VQ Email AI Agent
- Email Webhook (POST `email-in`: from/subject/body) → Classify Email (Code:
  intent + priority) → Draft Reply (Code: intent-wise templates) → Has Sender?
  (IF) → [true] Send Email (HTTP POST callback) → Send Result (Respond).

## D3. VQ AI Calling Agent (IVR)
- Call Webhook (POST `call-in`: Caller/CallSid) → Route Call (Code: business-hours
  check + TwiML build; Gather action URL request ke `host` header se dynamic —
  koi placeholder nahi) → After Hours? (IF) → Answer Call (Respond, `text` mode:
  `{{ $json.twiml }}`, Content-Type text/xml).
- Choice Webhook (POST `call-choice`: Digits) → Read Choice (Code: 1→booking,
  2→timings) → Answer Choice (Respond, text mode).
- **Core idea:** voice provider webhook ke RESPONSE ko call script maanta hai.
  TwiML = `<Say>` + `<Gather>` + `<Hangup>`.

## D4. VQ Reminder Sender
- Reminder Webhook (POST `reminder-in`: to/message/send_at/callback_url) →
  Compute Schedule (Code: send_at valid+future?) → Acknowledge (Respond: turant
  `{status: scheduled}`) → Has Sender? (IF) → Wait Until Time (Wait node,
  `dateTime = {{ $json.send_at }}`) → Send Reminder (HTTP POST callback).

## D5. VQ Website Lead Capture
- Lead Form Webhook (POST `lead-form`) → Validate & Score (Code: errors[] +
  0–100 score → HOT/WARM/COLD + owner_alert) → Valid? (IF) → Send Result.

## D6. VQ Support Ticket Triage Agent
- Ticket Webhook (POST `ticket-in`: customer/channel/subject/body) → Triage
  Ticket (Code: category + urgency critical/high/normal/low + suggested_reply +
  escalated) → Escalate? (IF) → Send Result.

## D7. VQ AI SDR Agent
- SDR Webhook (POST `sdr-lead`) → Qualify Fit (Code: 0–100 fit score + reasons,
  first_touch message, next 2 business-day IST meeting slots) → Worth Pursuing?
  (IF) → Send Result.

## D8. VQ Document Processing Agent
- Document Webhook (POST `doc-in`: doc_type/text) → Extract Fields (Code: regex —
  doc number, DD/MM/YYYY date, vendor, total, currency) → Validate (Code:
  exceptions[] → route auto/human) → Has Exceptions? (IF) → Send Result.
- Seekha: `Date.parse` Indian DD/MM/YYYY nahi samajhta — manual parse likha;
  `parseFloat` "Rs. 45,000" ko 0.45 banata hai — pehle number extract karo,
  phir parse.

## D9. VQ Keyword Planner
- Keyword Webhook (POST `kw-in`: seed_keyword/location/business_type) →
  Generate Plan (Code: long-tail combos + question keywords + content brief with
  intent) → Send Plan.

## D10. VQ Local Presence Booster
- Presence Webhook (POST `presence-in`) → Build Presence Plan (Code: 7-step Maps
  checklist + review plan + weekly post ideas) → Send Plan.
- Honest limit: live Maps ranking POSITION paid SERP API maangta hai; ye
  actionable plan free me deta hai.

## Pitch coverage map (21 workflows)
- AI agents track: Enquiry Agent ✓ | WhatsApp Agent ✓ | Email Agent ✓ |
  AI Calling Agent ✓ | Booking Agent ✓ | Follow-Up Engine ✓ | Reminder Sender ✓ |
  After-Hours Catcher ✓ | Lead Responder Demo/Pro ✓
- Websites track: Website Chatbot ✓ | Website Lead Capture ✓
- SEO track: SEO Audit Agent ✓ | Review Agent ✓ | Keyword Planner ✓ |
  Local Presence Booster ✓
- Ads track: Ad Lead Instant Responder ✓
- Vertical pitches: Support Triage (SaaS) ✓ | SDR Agent (agency) ✓ |
  Document Agent (ops/insurance/logistics) ✓
- Abhi bhi credential-gated: Pro (Gmail+Sheets), Booking+Reminders (Calendar/Gmail)
  — Google OAuth ke baad end-to-end.
