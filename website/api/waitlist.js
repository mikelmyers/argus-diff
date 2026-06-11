// Argus landing waitlist endpoint. Logs the signup and forwards it to the
// operator inbox via formsubmit.co (no stored credentials needed).
const FORWARD = 'https://formsubmit.co/ajax/myers092@gmail.com';

module.exports = async (req, res) => {
  if (req.method !== 'POST') {
    res.status(405).json({ error: 'method not allowed' });
    return;
  }
  const { email } = req.body || {};
  if (!email || !/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email) || email.length > 254) {
    res.status(400).json({ error: 'invalid email' });
    return;
  }
  console.log(`[waitlist] ${new Date().toISOString()} ${email}`);
  try {
    const r = await fetch(FORWARD, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ _subject: '[argus] waitlist signup', email }),
    });
    if (!r.ok) throw new Error(`forward status ${r.status}`);
    res.status(200).json({ ok: true });
  } catch (err) {
    console.error(`[waitlist] forward failed for ${email}: ${err.message}`);
    res.status(502).json({ error: 'forward failed' });
  }
};
