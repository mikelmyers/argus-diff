const assert = require("node:assert/strict");
const test = require("node:test");

const handler = require("../website/api/waitlist.js");

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
  };
}

async function invoke(body, origin = "https://argusdiff.com") {
  const res = response();
  await handler({ method: "POST", headers: { origin }, body }, res);
  return res;
}

test("stores a consented signup server-side", { concurrency: false }, async () => {
  const previousKey = process.env.RESEND_API_KEY;
  const previousFetch = global.fetch;
  process.env.RESEND_API_KEY = "test-key";
  let request;
  global.fetch = async (url, options) => {
    request = { url, options };
    return { ok: true, status: 201 };
  };

  try {
    const res = await invoke({ email: "Lead@Example.com", consent: true, _honey: "" });
    assert.equal(res.code, 200);
    assert.deepEqual(res.body, { ok: true });
    assert.equal(request.url, "https://api.resend.com/contacts");
    assert.equal(JSON.parse(request.options.body).email, "lead@example.com");
  } finally {
    global.fetch = previousFetch;
    if (previousKey === undefined) delete process.env.RESEND_API_KEY;
    else process.env.RESEND_API_KEY = previousKey;
  }
});

test("rejects a signup without consent", { concurrency: false }, async () => {
  const res = await invoke({ email: "lead@example.com", consent: false, _honey: "" });
  assert.equal(res.code, 400);
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
