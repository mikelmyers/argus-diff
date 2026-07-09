const { validUnsubscribeSignature } = require("./lib/subscription");

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

function page(title, message) {
  return `<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title} | Argus Diff</title><style>body{margin:0;background:#0c0f14;color:#e6e9ee;font:16px/1.6 -apple-system,Segoe UI,sans-serif}.wrap{max-width:620px;margin:12vh auto;padding:0 24px}h1{color:#f59e0b}p{color:#c9d2de}a{color:#f59e0b}</style><main class="wrap"><h1>${title}</h1><p>${message}</p><p><a href="https://argusdiff.com">Return to Argus Diff</a></p></main></html>`;
}

module.exports = async (req, res) => {
  if (req.method !== "GET") {
    res.status(405).json({ error: "method not allowed" });
    return;
  }

  const email = typeof req.query.email === "string" ? req.query.email.trim().toLowerCase() : "";
  const signature = typeof req.query.sig === "string" ? req.query.sig : "";
  const secret = process.env.UNSUBSCRIBE_SECRET;
  if (!email || !EMAIL_RE.test(email) || !validUnsubscribeSignature(email, signature, secret)) {
    res.status(400).send(page("This link is invalid", "Request a fresh link by replying to an Argus email."));
    return;
  }

  if (!process.env.RESEND_API_KEY) {
    console.error("[unsubscribe] RESEND_API_KEY is not configured");
    res.status(503).send(page("Unsubscribe is temporarily unavailable", "Please reply to an Argus email and we will remove you manually."));
    return;
  }

  let response;
  try {
    response = await fetch(`https://api.resend.com/contacts/${encodeURIComponent(email)}`, {
      method: "PATCH",
      headers: {
        Authorization: `Bearer ${process.env.RESEND_API_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ unsubscribed: true }),
    });
  } catch {
    console.error("[unsubscribe] Resend contact update failed");
    res.status(502).send(page("Unsubscribe is temporarily unavailable", "Please reply to an Argus email and we will remove you manually."));
    return;
  }

  if (!response.ok && response.status !== 404) {
    console.error(`[unsubscribe] Resend contact update failed: ${response.status}`);
    res.status(502).send(page("Unsubscribe is temporarily unavailable", "Please reply to an Argus email and we will remove you manually."));
    return;
  }

  res.status(200).send(page("You are unsubscribed", "You will not receive future Argus updates at this address."));
};
