# Billio Privacy Policy

**Last updated: [fill in launch date]**

> **Before you publish this policy:** replace the bracketed placeholders — `[Your Legal Entity Name]`, `[Business Address]`, `[Support/Privacy Contact Email]`, and `[Governing State/Country]` — with your actual business details. Those are legal facts about *you* as the operator that only you can supply; everything else in this document describes exactly what the Billio application does, as built.

## The short version

Billio helps you track bills and subscriptions that **you** enter — manually, by describing them in your own words, or by uploading a photo. Billio does **not** connect to your bank, does **not** read your email inbox, and does **not** pull in transactions from anywhere on your behalf. If it's in Billio, it's because you put it there.

## Information we collect

**Account information.** When you create an account we collect a first name, a username, and a password (stored only as a salted Argon2id hash — we never store or can recover your actual password). An email address is optional; you only need to provide one if you want password-reset-by-email or email reminders.

**Bill and payment information you enter.** Names, amounts, due dates, recurrence, categories, and notes for bills you create, plus the history of when you marked them paid. This is the core data Billio exists to store, and it is yours.

**Uploaded bill photos.** If you upload a photo of a bill, the image is stored in encrypted object storage (Cloudflare R2) associated only with your account, and a reference to it is stored in our database. We do not share these images with anyone except the AI provider described below, solely to extract bill details at your request.

**Feedback you submit.** If you use the in-app feedback tool, we store the feedback type, your message, and an optional star rating, associated with your account so we can follow up and improve the product. Feedback is **not anonymous** — we can see which account submitted it — but we do not attach your bills, payment history, or uploaded documents to a feedback submission unless you choose to type that information into your message yourself.

**Device and usage information.** If you enable push notifications, we store the push subscription details your browser generates (an endpoint and encryption keys) so we can deliver reminders — this is standard Web Push plumbing and contains no bill content itself. We also keep basic operational logs (request type, timestamp, response time, success/failure) to keep the service reliable and secure; these logs never contain your password, session tokens, or full bill contents.

## What we don't do

- We do not connect to your bank, credit card, or any financial institution.
- We do not access, read, or scan your email inbox.
- We do not sell your personal information.
- We do not use your bill or payment data to train third-party AI models.
- We do not show your bills, payment history, or documents to anyone other than you (and, if you contact support, the support team assisting you).

## How AI (Groq) is used

When you upload a bill photo, describe a bill in plain language, use the assistant, or run an audit, the minimum necessary text or image data is sent to our AI provider, Groq, to interpret it. Groq is never given your password, authentication tokens, or another user's data. All financial calculations (totals, comparisons, monthly spend) are computed by our own servers using exact decimal arithmetic — AI is only used to understand language and images and to explain numbers we already calculated, never to generate the numbers themselves. If AI processing fails or is unavailable, Billio continues to work normally using manual entry.

## Other service providers

We use a small number of infrastructure providers to operate Billio, each of which processes data only as needed to provide their service to us:

- **Render** — application hosting and the PostgreSQL database.
- **Cloudflare R2** — encrypted storage for uploaded bill photos.
- **Resend** — delivery of transactional emails (password resets, email reminders) if you've added and verified an email address.
- **Groq** — AI interpretation of bill images, natural-language entry, the assistant, and audit explanations, as described above.

## Your control over your data

- **Edit or delete any bill** at any time from within the app.
- **Export everything** — your bills and full payment history — as a CSV file at any time from Settings.
- **Delete your account** permanently from Settings. This removes your bills, occurrences, payment history, uploaded documents, notification records, and feedback tied to your account. Deletion requires re-entering your password to prevent accidental or unauthorized deletion, and cannot be undone.

## Data retention

We keep your bill and payment history for as long as your account exists, so you can browse your full history whenever you want. If you cancel a bill, its historical records are kept (so your payment history stays accurate) but no new occurrences are generated. If you delete your account, associated data is deleted as described above.

## Security

Passwords are hashed with Argon2id and never stored in plain text. All traffic to Billio is encrypted in transit (HTTPS). Every API request is authenticated and independently checked to ensure it only ever touches data belonging to the requesting account. We apply rate limiting to sensitive endpoints (login, password reset, feedback) to reduce abuse. No system is perfectly secure, but we've built Billio with these protections from the ground up rather than adding them as an afterthought.

## Children's privacy

Billio is not directed at children under 13 (or the relevant minimum age in your jurisdiction), and we do not knowingly collect information from children.

## Changes to this policy

If we materially change how we handle your data, we'll update this page and, where required, notify you directly.

## Contact

Questions about this policy or your data can be sent to **[Support/Privacy Contact Email]**.

---

*This policy is provided as a complete, accurate description of the Billio application's actual data practices as built. It is not a substitute for legal advice — before publishing, have it reviewed by a lawyer familiar with the privacy laws applicable to where your users live (e.g. GDPR, CCPA) to confirm it meets your specific legal obligations.*
