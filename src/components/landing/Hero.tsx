import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center">
      {/* Subtle gradient overlay */}
      <div className="absolute inset-0 bg-gradient-to-b from-black via-black to-transparent pointer-events-none" />

      <div className="max-w-7xl mx-auto px-6 lg:px-12 pt-32 pb-24 relative w-full">
<h1 className="text-5xl sm:text-7xl lg:text-8xl xl:text-9xl font-medium tracking-[-0.04em] leading-[0.95] text-white mb-8 max-w-5xl">
          Backing the founders
          <br />
          <span className="text-text-muted">the system overlooks</span>
        </h1>

        <p className="text-lg sm:text-xl text-text-muted max-w-2xl leading-relaxed mb-12">
          Somewhere right now, there's a brilliant founder talking
          themselves out of an idea because they don't have access to the right
          network, capital or resources. We're changing that.
        </p>

        <div className="flex flex-col sm:flex-row items-start gap-4">
          <Link
            to="/apply"
            className="inline-flex items-center gap-3 bg-accent text-black px-8 py-4 text-xs uppercase tracking-[0.15em] font-medium hover:bg-accent-hover transition-all duration-300"
          >
            Apply to the Programme
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to="/ask"
            className="inline-flex items-center gap-3 border border-white/20 text-white px-8 py-4 text-xs uppercase tracking-[0.15em] font-medium hover:border-white/50 transition-all duration-300"
          >
            Try Ask a Mentor
          </Link>
        </div>

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-8 mt-24 pt-12 border-t border-white/10 max-w-2xl">
          <div>
            <p className="text-3xl sm:text-4xl font-medium text-white tracking-[-0.04em]">10,000</p>
            <p className="text-xs uppercase tracking-[0.15em] text-text-muted mt-2">Founders in 5 years</p>
          </div>
          <div>
            <p className="text-3xl sm:text-4xl font-medium text-white tracking-[-0.04em]">8</p>
            <p className="text-xs uppercase tracking-[0.15em] text-text-muted mt-2">Week programme</p>
          </div>
          <div>
            <p className="text-3xl sm:text-4xl font-medium text-white tracking-[-0.04em]">24/7</p>
            <p className="text-xs uppercase tracking-[0.15em] text-text-muted mt-2">AI mentorship</p>
          </div>
        </div>
      </div>
    </section>
  );
}
