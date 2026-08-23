import { Link } from "react-router-dom";

export default function Privacy() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
      <Link to="/" className="mb-6 inline-block text-sm font-semibold text-brand-600 hover:underline">
        ← Back to Billio
      </Link>
      <h1 className="mb-2 text-3xl font-bold text-ink-900">Privacy Policy</h1>
      <p className="mb-8 text-sm text-ink-500">
        The full policy lives in this project's <code>docs/PRIVACY_POLICY.md</code>. Summary below.
      </p>

      <div className="space-y-6 text-sm leading-relaxed text-ink-700">
        <Section title="The short version">
          Billio helps you track bills you enter yourself — manually, described in your own words, or from a photo.
          Billio never connects to your bank and never reads your email inbox. If it's in Billio, you put it there.
        </Section>
        <Section title="What we collect">
          Account info (first name, username, password hash, optional email), the bills and payment history you
          enter, uploaded bill photos (stored in encrypted object storage), feedback you submit (associated with your
          account, never anonymous), and basic operational logs that never contain your password or bill contents.
        </Section>
        <Section title="AI (Groq)">
          When you use a photo upload, natural-language entry, the assistant, or an audit, the minimum necessary data
          is sent to our AI provider to interpret it. AI never calculates your totals — our servers do that with
          exact decimal math — and nothing is saved to your account until you confirm it.
        </Section>
        <Section title="Your control">
          Edit or delete any bill at any time. Export everything as a CSV. Permanently delete your account and all
          associated data from Settings, with a password confirmation required.
        </Section>
        <Section title="Security">
          Passwords are hashed with Argon2id. All traffic is encrypted in transit. Every request is checked to
          ensure it only touches data belonging to the authenticated account.
        </Section>
      </div>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <section>
      <h2 className="mb-1.5 text-base font-bold text-ink-900">{title}</h2>
      <p>{children}</p>
    </section>
  );
}
