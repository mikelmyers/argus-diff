// Consent-aware Argus early-access capture. Contacts are stored server-side in
// Resend; the browser never receives the API key or posts to Resend directly.

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const ALLOWED_HOSTS = new Set([
  "argusdiff.com",
  "argusdiff.dev",
  "argus-diff.vercel.app",
  "argus-diff-mikelmyers-projects.vercel.app",
]);

function allowedOrigin(value) {
  try {
    const host = new URL(value).hostname;
    return ALLOWED_HOSTS.has(host) || host.endsWith("-mikelmyers-projects.vercel.app");
  } catch {
    return false;
  }
}

function bodyOf(req) {
  if (typeof req.body === "string") {
    return JSON.parse(req.body);
  }
  return req.body || {};
}

module.exports = async (req, res) => {
  if (req.method !== "POST") {
    res.status(405).json({ error: "method not allowed" });
    return;
  }

  const origin = req.headers.origin;
  if (!origin || !allowedOrigin(origin)) {
    res.status(403).json({ error: "invalid origin" });
    return;
  }

  let body;
  try {
    body = bodyOf(req);
  } catch {
    res.status(400).json({ error: "invalid request" });
    return;
  }

  const email = typeof body.email === "string" ? body.email.trim().toLowerCase() : "";
  if (!email || email.length > 254 || !EMAIL_RE.test(email) || body.consent !== true) {
    res.status(400).json({ error: "valid email and consent required" });
    return;
  }

  // A bot that fills the honeypot receives the same generic success response
  // but is never persisted.
  if (body._honey) {
    res.status(200).json({ ok: true });
    return;
  }

  if (!process.env.RESEND_API_KEY) {
    console.error("[waitlist] RESEND_API_KEY is not configured");
    res.status(503).json({ error: "signup temporarily unavailable" });
    return;
  }

  const response = await fetch("https://api.resend.com/contacts", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      email,
      unsubscribed: false,
      properties: {
        source: "argusdiff.com",
        consented_at: new Date().toISOString(),
      },
    }),
  });

  // A repeat signup is not an error from the visitor's perspective.
  if (response.ok || response.status === 409) {
    res.status(200).json({ ok: true });
    return;
  }

  console.error(`[waitlist] Resend contact create failed: ${response.status}`);
  res.status(502).json({ error: "signup temporarily unavailable" });
};
