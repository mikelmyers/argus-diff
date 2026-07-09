// Consent-aware Argus early-access capture. Contacts are stored server-side in
// Resend; the browser never receives the API key or posts to Resend directly.

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
const { unsubscribeUrl } = require("./lib/subscription");
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

  let existing;
  try {
    existing = await fetch(`https://api.resend.com/contacts/${encodeURIComponent(email)}`, {
      headers: {
        Authorization: `Bearer ${process.env.RESEND_API_KEY}`,
      },
    });
  } catch {
    console.error("[waitlist] Resend contact lookup failed");
    res.status(502).json({ error: "signup temporarily unavailable" });
    return;
  }

  // A repeat signup is not an error from the visitor's perspective. Do not
  // resend the acknowledgement (or silently re-subscribe someone who opted out).
  if (existing.ok) {
    res.status(200).json({ ok: true });
    return;
  }
  if (existing.status !== 404) {
    console.error(`[waitlist] Resend contact lookup failed: ${existing.status}`);
    res.status(502).json({ error: "signup temporarily unavailable" });
    return;
  }

  let response;
  try {
    response = await fetch("https://api.resend.com/contacts", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        email,
        unsubscribed: false,
      }),
    });
  } catch {
    console.error("[waitlist] Resend contact request failed");
    res.status(502).json({ error: "signup temporarily unavailable" });
    return;
  }

  if (!response.ok) {
    console.error(`[waitlist] Resend contact create failed: ${response.status}`);
    res.status(502).json({ error: "signup temporarily unavailable" });
    return;
  }

  if (!process.env.UNSUBSCRIBE_SECRET) {
    console.error("[waitlist] UNSUBSCRIBE_SECRET is not configured");
    res.status(503).json({ error: "signup temporarily unavailable" });
    return;
  }

  const stopUrl = unsubscribeUrl(email, process.env.UNSUBSCRIBE_SECRET);
  try {
    const acknowledgement = await fetch("https://api.resend.com/emails", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${process.env.RESEND_API_KEY}`,
        "Content-Type": "application/json",
        "Idempotency-Key": `argus-early-access-${email}`,
      },
      body: JSON.stringify({
        from: "Argus Diff <updates@argusdiff.com>",
        to: [email],
        reply_to: "myers092@gmail.com",
        subject: "You’re on the Argus early-access list",
        html: `<p>Thanks for your interest in Argus Diff.</p><p>We’ll send occasional, practical updates about CAD review and the cloud tier. The open-source CLI and GitHub Action are available now.</p><p><a href="${stopUrl}">Unsubscribe from Argus updates</a></p>`,
        text: `Thanks for your interest in Argus Diff. We’ll send occasional, practical updates about CAD review and the cloud tier. Unsubscribe: ${stopUrl}`,
      }),
    });
    if (!acknowledgement.ok) {
      console.error(`[waitlist] Resend acknowledgement failed: ${acknowledgement.status}`);
    }
  } catch {
    // The signup is already durable. A transient acknowledgement failure must
    // not make the visitor retry and create a confusing experience.
    console.error("[waitlist] Resend acknowledgement request failed");
  }

  res.status(200).json({ ok: true });
};
