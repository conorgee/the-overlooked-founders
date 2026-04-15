import { Hero } from "../components/landing/Hero";
import { HowItWorks } from "../components/landing/HowItWorks";
import { ProgramStructure } from "../components/landing/ProgramStructure";
import { CTA } from "../components/landing/CTA";
import { Architect } from "../components/landing/Architect";

export function LandingPage() {
  return (
    <>
      <Hero />
      <HowItWorks />
      <ProgramStructure />
      <CTA />
      <Architect />
    </>
  );
}
