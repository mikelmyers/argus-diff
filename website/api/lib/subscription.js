const crypto = require("node:crypto");

const SITE_URL = "https://argusdiff.com";

function unsubscribeSignature(email, secret) {
  return crypto.createHmac("sha256", secret).update(email).digest("base64url");
}

function unsubscribeUrl(email, secret) {
  const params = new URLSearchParams({
    email,
    sig: unsubscribeSignature(email, secret),
  });
  return `${SITE_URL}/api/unsubscribe?${params}`;
}

function validUnsubscribeSignature(email, signature, secret) {
  if (!email || !signature || !secret) return false;
  const expected = Buffer.from(unsubscribeSignature(email, secret));
  const actual = Buffer.from(signature);
  return actual.length === expected.length && crypto.timingSafeEqual(actual, expected);
}

module.exports = { unsubscribeUrl, validUnsubscribeSignature };
