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
  // log-only: delivery happens browser-side via FormSubmit (server-origin
  // posts get blocked by their anti-bot layer — learned from the first live test)
  console.log(`[waitlist] ${new Date().toISOString()} ${email}`);
  res.status(200).json({ ok: true });
};
