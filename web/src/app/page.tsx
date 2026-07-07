import BackendStatusBadge from "@/components/BackendStatusBadge";
import CheckoutButton from "@/components/CheckoutButton";
import CheckoutStatusBanner from "@/components/CheckoutStatusBanner";
import DashboardAccessCard from "@/components/DashboardAccessCard";

const PRIMARY_BUTTON =
  "bg-[#4c8dd6] text-white hover:bg-[#3a7bc0]";
const SECONDARY_BUTTON =
  "border border-[#2d3348] text-zinc-100 hover:bg-[#1a1d29]";

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
    <div className="flex flex-1 flex-col items-center bg-[#0e1117]">
      <main className="flex w-full max-w-5xl flex-1 flex-col items-center gap-16 px-6 py-16 sm:px-10">
        {/* Header */}
        <div className="flex w-full flex-col items-center gap-4 text-center">
          <BackendStatusBadge />
          <h1 className="mt-4 text-4xl font-bold tracking-tight text-zinc-50 sm:text-5xl">
            🥊 UFC Fight Prediction Engine
          </h1>
          <p className="max-w-2xl text-lg text-zinc-400">
            A six-layer quantitative model — Recursive Elo, Physical Matchup,
            Contextual Stats, a Decay-Adjusted Weighted Ensemble, and a
            10,000-iteration Monte Carlo simulation — turned into a licensed
            analytics dashboard.
          </p>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
            {LAYERS.map((layer) => (
              <span
                key={layer}
                className="rounded-full border border-[#2d3348] px-3 py-1 text-xs font-medium text-zinc-400"
              >
                {layer}
              </span>
            ))}
          </div>
        </div>

        <CheckoutStatusBanner />

        {/* Pricing */}
        <section className="grid w-full grid-cols-1 gap-6 sm:grid-cols-2">
          <div className="flex flex-col gap-4 rounded-2xl border border-[#2d3348] bg-[#1a1d29] p-8">
            <h2 className="text-xl font-semibold text-zinc-50">
              Individual
            </h2>
            <p className="text-sm text-zinc-400">
              Full access to the prediction dashboard for a single analyst.
            </p>
            <ul className="flex flex-1 flex-col gap-2 text-sm text-zinc-400">
              <li>• Unlimited matchup predictions</li>
              <li>• Monte Carlo simulation &amp; confidence intervals</li>
              <li>• AI-generated tactical breakdowns</li>
            </ul>
            <CheckoutButton
              plan="individual"
              label="Subscribe — Individual"
              className={PRIMARY_BUTTON}
            />
          </div>

          <div className="flex flex-col gap-4 rounded-2xl border border-[#2d3348] bg-[#1a1d29] p-8">
            <h2 className="text-xl font-semibold text-zinc-50">
              Enterprise
            </h2>
            <p className="text-sm text-zinc-400">
              Everything in Individual, plus the ability to invite your team.
            </p>
            <ul className="flex flex-1 flex-col gap-2 text-sm text-zinc-400">
              <li>• Everything in Individual</li>
              <li>• Invite teammates under one subscription</li>
              <li>• Priority support</li>
            </ul>
            <CheckoutButton
              plan="enterprise"
              label="Subscribe — Enterprise"
              className={SECONDARY_BUTTON}
            />
          </div>
        </section>

        {/* Dashboard access handoff */}
        <DashboardAccessCard />

        <footer className="mt-auto pt-8 text-center text-xs text-zinc-600">
          Billing is handled securely via Stripe-hosted checkout on the web.
        </footer>
      </main>
    </div>
  );
}
