import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";

export function CTA() {
  return (
    <section className="border-t border-white/5">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 py-32">
        <div className="max-w-3xl">
          <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-6">
            Applications Open
          </p>
          <h2 className="text-4xl sm:text-5xl lg:text-6xl font-medium tracking-[-0.04em] text-white leading-[1.05] mb-8">
            Your background shouldn't
            <br />
            determine your future
          </h2>
          <p className="text-lg text-text-muted leading-relaxed mb-12 max-w-xl">
            We believe AI is the most powerful tool we have to deliver meaningful
            impact at scale. 25 spots per cohort. Completely free. Backed by people
            who believe in you.
          </p>
          <Link
            to="/apply"
            className="inline-flex items-center gap-3 bg-accent text-black px-8 py-4 text-xs uppercase tracking-[0.15em] font-medium hover:bg-accent-hover transition-all duration-300"
          >
            Apply to the Programme
            <ArrowRight className="w-4 h-4" />
          </Link>
        </div>
      </div>
    </section>
  );
}
