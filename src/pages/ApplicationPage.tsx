import { ApplicationForm } from "../components/application/ApplicationForm";

export function ApplicationPage() {
  return (
    <div className="max-w-2xl mx-auto px-6 lg:px-12 pt-32 pb-20">
      <p className="text-xs uppercase tracking-[0.2em] text-text-muted mb-6">
        Applications Open
      </p>
      <h1 className="text-4xl sm:text-5xl font-medium tracking-[-0.04em] text-white mb-4 leading-[1.05]">
        Apply to the Programme
      </h1>
      <p className="text-text-muted text-lg leading-relaxed mb-12">
        25 spots per cohort. Completely free. Tell us about yourself and your
        business idea.
      </p>
      <ApplicationForm />
    </div>
  );
}
