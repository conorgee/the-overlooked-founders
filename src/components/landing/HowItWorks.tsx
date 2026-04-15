const pillars = [
  {
    number: "01",
    title: "Screening & Selection",
    description:
      "Application screening that ensures founders get access based on their potential, not their past. High-value matching to the right mentors based on background, industry, goals and working style.",
  },
  {
    number: "02",
    title: "AI-Powered Programme",
    description:
      "A personalised, always-on support layer so no founder ever waits days for guidance on a critical decision. Conversational AI, a deep knowledge base, and escalation logic that knows when a human needs to step in.",
  },
  {
    number: "03",
    title: "Community & Impact",
    description:
      "The connective tissue that makes every founder and donor feel known. Peer introductions, feedback loops, event coordination — and real-time dashboards tracking the impact outcomes that matter.",
  },
];

export function HowItWorks() {
  return (
    <section className="border-t border-white/5">
      <div className="max-w-7xl mx-auto px-6 lg:px-12 py-32">
        <div className="mb-20">
          <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-6">
            How It Works
          </p>
          <h2 className="text-4xl sm:text-5xl lg:text-6xl font-medium tracking-[-0.04em] text-white max-w-3xl leading-[1.05]">
            Technology in service of the people who need it most
          </h2>
        </div>

        <div className="grid lg:grid-cols-3 gap-0">
          {pillars.map((pillar, i) => (
            <div
              key={pillar.number}
              className={`py-10 lg:px-10 ${
                i > 0 ? "border-t lg:border-t-0 lg:border-l border-white/10" : ""
              } ${i === 0 ? "lg:pl-0" : ""} ${i === pillars.length - 1 ? "lg:pr-0" : ""}`}
            >
              <span className="text-text-subtle text-sm font-medium">
                {pillar.number}
              </span>
              <h3 className="text-2xl font-medium text-white mt-4 mb-4 tracking-[-0.02em]">
                {pillar.title}
              </h3>
              <p className="text-text-muted leading-relaxed text-[15px]">
                {pillar.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
