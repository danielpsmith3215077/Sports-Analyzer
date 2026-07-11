import BackendStatusBadge from "@/components/BackendStatusBadge";
import CheckoutButton from "@/components/CheckoutButton";
import CheckoutStatusBanner from "@/components/CheckoutStatusBanner";
import DashboardAccessCard from "@/components/DashboardAccessCard";
import DemoAccessButton from "@/components/DemoAccessButton";
import Link from "next/link";

const LAYERS = [
  "Recursive Elo",
  "Physical Matchup",
  "Contextual Stats",
  "Weighted Ensemble",
  "Wear & Tear Decay",
  "Monte Carlo Simulation",
];

export default function Home() {
  return (
    <div className="sa-atmosphere flex flex-1 flex-col">
      {/* ── Hero: one composition ── */}
      <header className="relative isolate min-h-[100svh] w-full overflow-hidden">
        <div className="sa-hero-visual" aria-hidden="true">
          <div className="sa-hero-visual__grid" />
          <div className="sa-hero-visual__plane" />
        </div>

        <div className="relative z-10 mx-auto flex min-h-[100svh] w-full max-w-6xl flex-col px-6 pb-16 pt-8 sm:px-10 lg:px-12">
          <div className="sa-reveal flex items-center justify-between gap-4">
            <BackendStatusBadge />
          </div>

          <div className="flex flex-1 flex-col justify-center py-16 sm:py-20 lg:max-w-2xl lg:py-0">
            <p className="sa-eyebrow sa-reveal sa-reveal-delay-1">
              Licensed analytics desk
            </p>

            <h1 className="sa-brand sa-reveal sa-reveal-delay-1 mt-5 text-[clamp(3.25rem,9vw,5.75rem)] text-[var(--foreground)]">
              Sports Analyzer
            </h1>

            <h2 className="sa-display sa-reveal sa-reveal-delay-2 mt-6 max-w-xl text-[clamp(1.5rem,3.5vw,2.15rem)] text-[var(--champagne-bright)]">
              Quantitative fight intelligence
            </h2>

            <p className="sa-reveal sa-reveal-delay-3 mt-5 max-w-md text-base leading-relaxed text-[var(--muted-strong)] sm:text-lg">
              A six-layer model and 10,000-iteration Monte Carlo engine —
              delivered as licensed institutional access.
            </p>

            <div className="sa-reveal sa-reveal-delay-4 mt-10 flex flex-col gap-3 sm:flex-row sm:items-center">
              <a href="#subscribe" className="sa-btn sa-btn-primary">
                Subscribe
              </a>
              <DemoAccessButton
                label="View Live Demo"
                className="sa-btn sa-btn-secondary"
              />
            </div>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto flex w-full max-w-6xl flex-1 flex-col gap-20 px-6 pb-24 sm:px-10 lg:px-12">
        <div className="w-full">
          <CheckoutStatusBanner />
        </div>

        {/* Model layers — below fold */}
        <section aria-labelledby="model-heading" className="max-w-3xl">
          <p className="sa-eyebrow">Methodology</p>
          <h2
            id="model-heading"
            className="sa-display mt-3 text-3xl text-[var(--foreground)] sm:text-4xl"
          >
            Six layers. One edge.
          </h2>
          <p className="mt-4 max-w-xl text-[var(--muted-strong)]">
            Each bout is scored through recursive ratings, physical matchup,
            context, ensemble weighting, wear-and-tear decay, and Monte Carlo
            simulation — then surfaced in a licensed dashboard.
          </p>
          <ul className="mt-8 grid grid-cols-1 gap-x-10 gap-y-3 sm:grid-cols-2">
            {LAYERS.map((layer, i) => (
              <li
                key={layer}
                className="flex items-baseline gap-3 border-t border-[var(--border)] pt-3 text-sm text-[var(--muted-strong)]"
              >
                <span className="font-mono text-xs text-[var(--champagne)]">
                  {String(i + 1).padStart(2, "0")}
                </span>
                {layer}
              </li>
            ))}
          </ul>
        </section>

        {/* Pricing — cards only where interaction lives */}
        <section id="subscribe" aria-labelledby="pricing-heading" className="scroll-mt-12">
          <div className="max-w-xl">
            <p className="sa-eyebrow">Access</p>
            <h2
              id="pricing-heading"
              className="sa-display mt-3 text-3xl text-[var(--foreground)] sm:text-4xl"
            >
              Licensed seats
            </h2>
            <p className="mt-4 text-[var(--muted-strong)]">
              Secure Stripe checkout. Instant dashboard access once licensed.
            </p>
          </div>

          <div className="mt-10 grid w-full grid-cols-1 gap-5 sm:grid-cols-2">
            <article className="sa-card sa-card-featured flex flex-col gap-5">
              <div>
                <h3 className="sa-display text-2xl text-[var(--foreground)]">
                  Individual
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
                  Full prediction desk for a single analyst.
                </p>
              </div>
              <ul className="flex flex-1 flex-col gap-2.5 text-sm text-[var(--muted-strong)]">
                <li className="border-t border-[var(--border)] pt-2.5">
                  Unlimited matchup predictions
                </li>
                <li className="border-t border-[var(--border)] pt-2.5">
                  Monte Carlo simulation &amp; confidence intervals
                </li>
                <li className="border-t border-[var(--border)] pt-2.5">
                  AI-generated tactical breakdowns
                </li>
              </ul>
              <CheckoutButton
                plan="individual"
                label="Subscribe — Individual"
                className="sa-btn sa-btn-primary w-full"
              />
            </article>

            <article className="sa-card flex flex-col gap-5">
              <div>
                <h3 className="sa-display text-2xl text-[var(--foreground)]">
                  Enterprise
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--muted)]">
                  Everything in Individual, with seats for your desk.
                </p>
              </div>
              <ul className="flex flex-1 flex-col gap-2.5 text-sm text-[var(--muted-strong)]">
                <li className="border-t border-[var(--border)] pt-2.5">
                  Everything in Individual
                </li>
                <li className="border-t border-[var(--border)] pt-2.5">
                  Invite teammates under one subscription
                </li>
                <li className="border-t border-[var(--border)] pt-2.5">
                  Priority support
                </li>
              </ul>
              <CheckoutButton
                plan="enterprise"
                label="Subscribe — Enterprise"
                className="sa-btn sa-btn-ghost w-full"
              />
            </article>
          </div>
        </section>

        <DashboardAccessCard />

        <footer className="mt-auto border-t border-[var(--border)] pt-10 text-center text-xs text-[var(--muted)]">
          <p>Billing is handled securely via Stripe-hosted checkout.</p>
          <p className="mt-3">
            <Link
              href="/admin"
              className="text-[var(--muted)] transition-colors hover:text-[var(--champagne)]"
            >
              Admin
            </Link>
          </p>
        </footer>
      </main>
    </div>
  );
}
