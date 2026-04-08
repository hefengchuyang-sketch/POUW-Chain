import { Link } from 'react-router-dom'
import { ArrowRight, BookOpen, Cpu, LineChart, Orbit, ShieldCheck, WalletCards } from 'lucide-react'

const pillars = [
  {
    title: 'Verifiable Runtime',
    desc: 'Execution trails, runtime snapshots, and owner-scoped result retrieval make outcomes auditable.',
    icon: ShieldCheck,
    color: 'from-teal-300/35 to-sky-300/20',
  },
  {
    title: 'Open GPU Marketplace',
    desc: 'Order Account and Mining Account coordinate through transparent bid, accept, and completion states.',
    icon: Cpu,
    color: 'from-indigo-300/30 to-cyan-300/20',
  },
  {
    title: 'Programmable Settlement',
    desc: 'Paid and free flows share one lifecycle, with fee split surfaced as a visible protocol primitive.',
    icon: WalletCards,
    color: 'from-amber-300/35 to-orange-300/20',
  },
]

const milestones = [
  { stage: 'Q2 2026', text: 'Public demonstration pipeline with one-command startup and reviewer-ready scripts.' },
  { stage: 'Q3 2026', text: 'Stronger runtime attestation and measurable SLA proof for buyer confidence.' },
  { stage: 'Q4 2026', text: 'Cross-region routing and latency-aware scheduling for production workloads.' },
  { stage: 'Q1 2027', text: 'Pilot collaborations with AI teams that need burst compute supply.' },
]

export default function ProjectShowcase() {
  return (
    <div className="relative min-h-[calc(100vh-90px)] overflow-hidden rounded-xl border border-slate-300/70 bg-[#f4f1e7] text-slate-900 shadow-[0_18px_60px_rgba(14,23,42,0.12)]">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_15%_20%,rgba(251,191,36,0.22),transparent_35%),radial-gradient(circle_at_85%_8%,rgba(56,189,248,0.18),transparent_30%),radial-gradient(circle_at_75%_85%,rgba(45,212,191,0.16),transparent_38%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-35" style={{ backgroundImage: 'linear-gradient(rgba(15,23,42,0.06) 1px, transparent 1px), linear-gradient(90deg, rgba(15,23,42,0.06) 1px, transparent 1px)', backgroundSize: '40px 40px' }} />

      <div className="relative z-10 p-6 md:p-10 space-y-8">
        <section className="grid gap-7 md:grid-cols-[1.18fr_0.82fr] items-start">
          <div className="space-y-5">
            <div className="inline-flex items-center gap-2 rounded-full border border-slate-500/35 bg-white/75 px-3 py-1 text-xs tracking-[0.14em] uppercase text-slate-700" style={{ fontFamily: 'Space Grotesk, Manrope, sans-serif' }}>
              <BookOpen size={14} />
              MainCoin Briefing
            </div>
            <h1 className="text-3xl md:text-5xl font-semibold leading-tight text-slate-900" style={{ fontFamily: 'Space Grotesk, Manrope, sans-serif' }}>
              A Verifiable Market
              <span className="mx-2 bg-gradient-to-r from-teal-700 via-sky-700 to-indigo-700 bg-clip-text text-transparent">for Compute Execution</span>
              at AI Scale
            </h1>
            <p className="max-w-2xl text-slate-700 leading-relaxed text-[15px]">
              MainCoin positions compute as a market operation with observable states: order, acceptance, runtime,
              settlement, and owner-scoped result delivery. The current product emphasizes demonstrable trust mechanics
              today while preparing for production-grade scheduling and multi-region capacity tomorrow.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/demo" className="inline-flex items-center gap-2 rounded-lg border border-slate-800 bg-slate-900 px-4 py-2 text-sm font-medium text-white transition hover:bg-slate-800">
                Open Interactive Demo
                <ArrowRight size={16} />
              </Link>
              <Link to="/market" className="inline-flex items-center gap-2 rounded-lg border border-slate-400/70 bg-white/80 px-4 py-2 text-sm font-medium text-slate-800 transition hover:bg-white">
                Explore Compute Market
                <Orbit size={16} />
              </Link>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-300/80 bg-white/80 p-5 backdrop-blur-sm">
            <div className="mb-4 flex items-center gap-2 text-slate-700" style={{ fontFamily: 'Space Grotesk, Manrope, sans-serif' }}>
              <LineChart size={16} />
              Mission Metrics
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Metric label="Order Visibility" value="100%" hint="accepted + running traces" />
              <Metric label="Settlement Modes" value="2" hint="free + paid flows" />
              <Metric label="Demo Startup" value="1-Click" hint="local + docker scripts" />
              <Metric label="Role Model" value="2-Account" hint="buyer + miner" />
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {pillars.map((p) => {
            const Icon = p.icon
            return (
              <div key={p.title} className="rounded-2xl border border-slate-300/80 bg-white/75 p-5 backdrop-blur-sm transition-all duration-200 hover:-translate-y-1 hover:border-slate-500/70">
                <div className={`mb-4 inline-flex rounded-xl bg-gradient-to-br ${p.color} p-2`}>
                  <Icon size={18} className="text-slate-800" />
                </div>
                <h3 className="text-lg font-semibold text-slate-900" style={{ fontFamily: 'Space Grotesk, Manrope, sans-serif' }}>{p.title}</h3>
                <p className="mt-2 text-sm text-slate-700 leading-relaxed">{p.desc}</p>
              </div>
            )
          })}
        </section>

        <section className="grid gap-6 md:grid-cols-[1fr_1fr]">
          <div className="rounded-2xl border border-teal-400/35 bg-white/75 p-5">
            <h2 className="mb-4 text-xl text-slate-900" style={{ fontFamily: 'Space Grotesk, Manrope, sans-serif' }}>Execution Narrative</h2>
            <ol className="space-y-3 text-sm text-slate-700 leading-relaxed">
              <li>1. Buyer identity is established and signs order intent.</li>
              <li>2. Miner identity activates acceptance mode and declares availability.</li>
              <li>3. Program payload and optional input files are submitted as execution context.</li>
              <li>4. Runtime and settlement traces are emitted in observable protocol states.</li>
              <li>5. Result access is restricted to the order owner, with explicit proof metadata.</li>
            </ol>
          </div>

          <div className="rounded-2xl border border-amber-400/35 bg-white/75 p-5">
            <h2 className="mb-4 text-xl text-slate-900" style={{ fontFamily: 'Space Grotesk, Manrope, sans-serif' }}>Roadmap Signals</h2>
            <ul className="space-y-3 text-sm text-slate-700">
              {milestones.map((m) => (
                <li key={m.stage} className="flex items-start gap-3">
                  <span className="mt-0.5 rounded border border-slate-400/45 bg-slate-100 px-2 py-0.5 text-[11px] text-slate-700">{m.stage}</span>
                  <span>{m.text}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      </div>
    </div>
  )
}

function Metric({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="rounded-xl border border-slate-300/80 bg-white/85 p-3">
      <div className="text-[11px] uppercase tracking-[0.12em] text-slate-500">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-slate-900" style={{ fontFamily: 'Space Grotesk, Manrope, sans-serif' }}>{value}</div>
      <div className="mt-1 text-xs text-slate-500">{hint}</div>
    </div>
  )
}
