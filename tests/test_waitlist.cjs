const assert = require("node:assert/strict");
const test = require("node:test");

const handler = require("../website/api/waitlist.js");
const unsubscribe = require("../website/api/unsubscribe.js");
const { unsubscribeUrl } = require("../website/api/lib/subscription.js");

function response() {
  return {
    code: 0,
    body: null,
    status(code) {
      this.code = code;
      return this;
    },
    json(body) {
      this.body = body;
    },
    send(body) {
      this.body = body;
    },
  };
}

async function invoke(body, origin = "https://argusdiff.com") {
  const res = response();
  await handler({ method: "POST", headers: { origin }, body }, res);
  return res;
}

test("stores a consented signup server-side", { concurrency: false }, async () => {
  const previousKey = process.env.RESEND_API_KEY;
  const previousSecret = process.env.UNSUBSCRIBE_SECRET;
  const previousFetch = global.fetch;
  process.env.RESEND_API_KEY = "test-key";
  process.env.UNSUBSCRIBE_SECRET = "test-unsubscribe-secret";
  const requests = [];
  global.fetch = async (url, options) => {
    requests.push({ url, options });
    return { ok: true, status: url.endsWith("/contacts") ? 201 : 202 };
  };

  try {
    const res = await invoke({ email: "Lead@Example.com", consent: true, _honey: "" });
    assert.equal(res.code, 200);
    assert.deepEqual(res.body, { ok: true });
    assert.equal(requests[0].url, "https://api.resend.com/contacts");
    assert.equal(JSON.parse(requests[0].options.body).email, "lead@example.com");
    assert.equal(requests[1].url, "https://api.resend.com/emails");
    assert.equal(JSON.parse(requests[1].options.body).to[0], "lead@example.com");
    assert.match(JSON.parse(requests[1].options.body).html, /api\/unsubscribe\?email=lead%40example.com/);
  } finally {
    global.fetch = previousFetch;
    if (previousKey === undefined) delete process.env.RESEND_API_KEY;
    else process.env.RESEND_API_KEY = previousKey;
    if (previousSecret === undefined) delete process.env.UNSUBSCRIBE_SECRET;
    else process.env.UNSUBSCRIBE_SECRET = previousSecret;
  }
});

test("unsubscribes a contact only with a signed link", { concurrency: false }, async () => {
  const previousKey = process.env.RESEND_API_KEY;
  const previousSecret = process.env.UNSUBSCRIBE_SECRET;
  const previousFetch = global.fetch;
  process.env.RESEND_API_KEY = "test-key";
  process.env.UNSUBSCRIBE_SECRET = "test-unsubscribe-secret";
  let request;
  global.fetch = async (url, options) => {
    request = { url, options };
    return { ok: true, status: 200 };
  };

  try {
    const url = new URL(unsubscribeUrl("lead@example.com", process.env.UNSUBSCRIBE_SECRET));
    const res = response();
    await unsubscribe({ method: "GET", query: Object.fromEntries(url.searchParams) }, res);
    assert.equal(res.code, 200);
    assert.match(res.body, /You are unsubscribed/);
    assert.equal(request.url, "https://api.resend.com/contacts/lead%40example.com");
    assert.equal(request.options.method, "PATCH");
    assert.deepEqual(JSON.parse(request.options.body), { unsubscribed: true });
  } finally {
    global.fetch = previousFetch;
    if (previousKey === undefined) delete process.env.RESEND_API_KEY;
    else process.env.RESEND_API_KEY = previousKey;
    if (previousSecret === undefined) delete process.env.UNSUBSCRIBE_SECRET;
    else process.env.UNSUBSCRIBE_SECRET = previousSecret;
  }
});

test("rejects an unsigned unsubscribe request", { concurrency: false }, async () => {
  const res = response();
  await unsubscribe({ method: "GET", query: { email: "lead@example.com", sig: "nope" } }, res);
  assert.equal(res.code, 400);
});

test("rejects a signup without consent", { concurrency: false }, async () => {
  const res = await invoke({ email: "lead@example.com", consent: false, _honey: "" });
  assert.equal(res.code, 400);
});

test("accepts Resend's duplicate-contact response without sending another email", { concurrency: false }, async () => {
  const previousKey = process.env.RESEND_API_KEY;
  const previousFetch = global.fetch;
  process.env.RESEND_API_KEY = "test-key";
  let calls = 0;
  global.fetch = async () => {
    calls += 1;
    return { ok: false, status: 422, json: async () => ({ message: "Contact already exists" }) };
  };

  try {
    const res = await invoke({ email: "lead@example.com", consent: true, _honey: "" });
    assert.equal(res.code, 200);
    assert.deepEqual(res.body, { ok: true });
    assert.equal(calls, 1);
  } finally {
    global.fetch = previousFetch;
    if (previousKey === undefined) delete process.env.RESEND_API_KEY;
    else process.env.RESEND_API_KEY = previousKey;
  }
});

test("does not persist honeypot submissions", { concurrency: false }, async () => {
  const previousKey = process.env.RESEND_API_KEY;
  const previousFetch = global.fetch;
  process.env.RESEND_API_KEY = "test-key";
  global.fetch = async () => {
    throw new Error("honeypot submission reached provider");
  };

  try {
    const res = await invoke({ email: "bot@example.com", consent: true, _honey: "filled" });
    assert.equal(res.code, 200);
    assert.deepEqual(res.body, { ok: true });
  } finally {
    global.fetch = previousFetch;
    if (previousKey === undefined) delete process.env.RESEND_API_KEY;
    else process.env.RESEND_API_KEY = previousKey;
  }
});
