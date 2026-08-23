import { Link } from "react-router-dom";

export default function Terms() {
  return (
    <div className="mx-auto max-w-2xl px-4 py-10 sm:px-6">
      <Link to="/" className="mb-6 inline-block text-sm font-semibold text-brand-600 hover:underline">
        ← Back to Billio
      </Link>
      <h1 className="mb-2 text-3xl font-bold text-ink-900">Terms of Service</h1>
      <p className="mb-8 text-sm text-ink-500">
        The full terms live in this project's <code>docs/TERMS_OF_SERVICE.md</code>. Summary below.
      </p>

      <div className="space-y-6 text-sm leading-relaxed text-ink-700">
        <Section title="What Billio is">
          A personal bill and subscription tracker. Billio does not connect to bank accounts or process payments —
          marking a bill "paid" is a record you keep, not a transaction Billio performs.
        </Section>
        <Section title="AI features">
          AI-extracted bill data is always shown to you for review and is never saved until you confirm it. AI can
          make mistakes — always check extracted amounts and dates. Financial totals are calculated deterministically
          by our servers, never invented by AI.
        </Section>
        <Section title="No financial advice">
          Nothing in Billio, including AI explanations or audit summaries, constitutes financial, legal, or tax
          advice.
        </Section>
        <Section title="Reminders are best-effort">
          We've built the reminder system to avoid duplicate or missed sends, but delivery depends on third-party
          infrastructure we don't fully control. Billio isn't liable for a missed payment caused by an undelivered
          reminder.
        </Section>
        <Section title="Your data">
          You own the data you enter. You can export or permanently delete it at any time.
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
