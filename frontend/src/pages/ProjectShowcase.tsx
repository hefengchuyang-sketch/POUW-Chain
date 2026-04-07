import { Link } from 'react-router-dom'
import { ArrowRight, Cpu, ShieldCheck, Orbit, Radar, Sparkles, WalletCards } from 'lucide-react'

const pillars = [
  {
    title: 'Verifiable Compute',
    desc: 'Orders are matched, accepted, and settled with traceable runtime evidence.',
    icon: ShieldCheck,
    color: 'from-cyan-400/35 to-emerald-300/20',
  },
  {
    title: 'Decentralized GPU Market',
    desc: 'Order Account and Mining Account coordinate through open market flow.',
    icon: Cpu,
    color: 'from-fuchsia-400/35 to-blue-300/20',
  },
  {
    title: 'Programmable Settlement',
    desc: 'Supports free orders and paid orders with explicit fee split visibility.',
    icon: WalletCards,
    color: 'from-amber-300/35 to-rose-300/20',
  },
]

const milestones = [
  { stage: 'Q2 2026', text: 'Public demo pipeline: one-click startup, record-ready scripts.' },
  { stage: 'Q3 2026', text: 'Miner runtime attestation and stronger SLA verification.' },
  { stage: 'Q4 2026', text: 'Multi-region order routing and latency-aware scheduling.' },
  { stage: 'Q1 2027', text: 'Pilot with AI teams needing burst GPU capacity.' },
]

export default function ProjectShowcase() {
  return (
    <div className="relative min-h-[calc(100vh-90px)] overflow-hidden rounded-xl border border-cyan-400/30 bg-[#060b16] text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_20%_15%,rgba(0,229,255,0.22),transparent_38%),radial-gradient(circle_at_80%_10%,rgba(139,92,246,0.2),transparent_35%),radial-gradient(circle_at_50%_85%,rgba(16,185,129,0.14),transparent_40%)]" />
      <div className="pointer-events-none absolute inset-0 opacity-35" style={{ backgroundImage: 'linear-gradient(rgba(56,189,248,0.18) 1px, transparent 1px), linear-gradient(90deg, rgba(56,189,248,0.18) 1px, transparent 1px)', backgroundSize: '44px 44px' }} />

      <div className="relative z-10 p-6 md:p-10 space-y-10">
        <section className="grid gap-8 md:grid-cols-[1.2fr_0.8fr] items-center">
          <div className="space-y-5">
            <div className="inline-flex items-center gap-2 rounded-full border border-cyan-300/45 bg-cyan-300/10 px-3 py-1 text-xs tracking-[0.14em] uppercase text-cyan-200" style={{ fontFamily: 'Orbitron, Exo 2, Rajdhani, sans-serif' }}>
              <Radar size={14} />
              MainCoin Protocol Narrative
            </div>
            <h1 className="text-3xl md:text-5xl font-semibold leading-tight" style={{ fontFamily: 'Orbitron, Exo 2, Rajdhani, sans-serif' }}>
              Build The
              <span className="mx-2 bg-gradient-to-r from-cyan-300 via-blue-300 to-fuchsia-300 bg-clip-text text-transparent">Compute Economy</span>
              For The AI Frontier
            </h1>
            <p className="max-w-2xl text-slate-300/90 leading-relaxed">
              MainCoin is shaping a science-fiction-grade infrastructure where developers can place compute orders,
              miners can execute workloads transparently, and settlement is visible as a first-class protocol signal.
              The platform is built for credible demos now and production-grade execution next.
            </p>
            <div className="flex flex-wrap gap-3">
              <Link to="/demo" className="btn-accent inline-flex items-center gap-2">
                Open Interactive Demo
                <ArrowRight size={16} />
              </Link>
              <Link to="/market" className="btn-secondary inline-flex items-center gap-2">
                Explore Compute Market
                <Orbit size={16} />
              </Link>
            </div>
          </div>

          <div className="rounded-2xl border border-cyan-300/35 bg-slate-950/55 p-5 backdrop-blur-sm">
            <div className="mb-4 flex items-center gap-2 text-cyan-200" style={{ fontFamily: 'Rajdhani, Exo 2, sans-serif' }}>
              <Sparkles size={16} />
              Mission Metrics
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Metric label="Order Visibility" value="100%" hint="accepted + running trace" />
              <Metric label="Settlement Modes" value="2" hint="free + paid orders" />
              <Metric label="Demo Startup" value="1-Click" hint="local / docker scripts" />
              <Metric label="System Role Model" value="2-Account" hint="order + mining" />
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-3">
          {pillars.map((p) => {
            const Icon = p.icon
            return (
              <div key={p.title} className="rounded-2xl border border-slate-700/80 bg-slate-950/50 p-5 backdrop-blur-sm transition-all duration-200 hover:-translate-y-1 hover:border-cyan-300/60">
                <div className={`mb-4 inline-flex rounded-xl bg-gradient-to-br ${p.color} p-2`}>
                  <Icon size={18} className="text-cyan-100" />
                </div>
                <h3 className="text-lg font-semibold text-cyan-100" style={{ fontFamily: 'Exo 2, Rajdhani, sans-serif' }}>{p.title}</h3>
                <p className="mt-2 text-sm text-slate-300/85 leading-relaxed">{p.desc}</p>
              </div>
            )
          })}
        </section>

        <section className="grid gap-6 md:grid-cols-[1fr_1fr]">
          <div className="rounded-2xl border border-fuchsia-300/30 bg-slate-950/50 p-5">
            <h2 className="mb-4 text-xl text-fuchsia-200" style={{ fontFamily: 'Orbitron, Exo 2, sans-serif' }}>Execution Pipeline</h2>
            <ol className="space-y-3 text-sm text-slate-300/90">
              <li>1. Buyer creates or imports the Order Account.</li>
              <li>2. Miner activates task mode from the Mining Account.</li>
              <li>3. Order is submitted (free or paid) with program payload.</li>
              <li>4. Miner accepts and runtime state becomes visible.</li>
              <li>5. Result is returned back to the Order Account with settlement proof.</li>
            </ol>
          </div>

          <div className="rounded-2xl border border-emerald-300/30 bg-slate-950/50 p-5">
            <h2 className="mb-4 text-xl text-emerald-200" style={{ fontFamily: 'Orbitron, Exo 2, sans-serif' }}>Roadmap Signals</h2>
            <ul className="space-y-3 text-sm text-slate-300/90">
              {milestones.map((m) => (
                <li key={m.stage} className="flex items-start gap-3">
                  <span className="mt-0.5 rounded border border-emerald-300/40 bg-emerald-300/10 px-2 py-0.5 text-[11px] text-emerald-200">{m.stage}</span>
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
    <div className="rounded-xl border border-slate-700/80 bg-slate-900/65 p-3">
      <div className="text-[11px] uppercase tracking-[0.12em] text-slate-400">{label}</div>
      <div className="mt-1 text-2xl font-semibold text-cyan-200" style={{ fontFamily: 'Orbitron, Exo 2, sans-serif' }}>{value}</div>
      <div className="mt-1 text-xs text-slate-400">{hint}</div>
    </div>
  )
}
