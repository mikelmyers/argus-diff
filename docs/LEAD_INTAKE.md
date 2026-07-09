# Argus lead intake

Argus stores explicit early-access opt-ins server-side with Resend. The site
never exposes the Resend API key or posts directly to the provider. Design
partner submissions remain operator-reviewed because they need context and
data-use choices.

## Contact routes

- **Early access:** submit the form on argusdiff.com. It requires explicit
  consent and stores the email in the Argus Resend contact list.
- **Private concierge diff:** email `myers092@gmail.com` with subject
  `argus concierge diff`.
- **Public CAD revision pair:** use the [design-partner issue](https://github.com/mikelmyers/argus-diff/issues/9).

Do not send proprietary CAD files through a public GitHub issue.

## Inbox handling

New concierge inquiries are labeled `Argus / Leads` in the operator inbox.
Respond with the data-use choices from [the design-partner program](DESIGN_PARTNERS.md)
before accepting any files:

1. process and delete;
2. retain privately to improve Argus; or
3. publish a consented public benchmark case.

## Privacy and sending gate

Resend is the email processor for the opt-in list; it is not a browser-side
relay. Do not send a marketing broadcast until the Resend sending domain is
verified and the message includes a tested unsubscribe path. Honor deletion or
unsubscribe requests immediately.
