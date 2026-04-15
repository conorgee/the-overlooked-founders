import type { ProgramWeek } from "../lib/types";

export const programWeeks: ProgramWeek[] = [
  {
    week: 1,
    title: "Idea Validation",
    description: "Is your idea solving a real problem? Learn how to test your assumptions before building anything.",
    topics: ["Problem identification", "Market research basics", "Assumption testing"],
    status: "completed",
  },
  {
    week: 2,
    title: "Customer Discovery",
    description: "Who exactly is your customer? Master the art of talking to potential users and extracting real insights.",
    topics: ["User interviews", "Customer personas", "Pain point mapping"],
    status: "completed",
  },
  {
    week: 3,
    title: "Business Model",
    description: "How will you make money? Explore different revenue models and find the right fit for your venture.",
    topics: ["Revenue models", "Pricing strategy", "Unit economics"],
    status: "current",
  },
  {
    week: 4,
    title: "MVP Strategy",
    description: "What is the smallest thing you can build? Define your minimum viable product and get to market fast.",
    topics: ["MVP definition", "Feature prioritisation", "Build vs buy"],
    status: "locked",
  },
  {
    week: 5,
    title: "Go-To-Market",
    description: "How will people find you? Craft a launch strategy that gets your first customers in the door.",
    topics: ["Channel strategy", "Launch planning", "Early traction"],
    status: "locked",
  },
  {
    week: 6,
    title: "Growth & Metrics",
    description: "What numbers matter? Learn to measure what counts and build data-driven growth loops.",
    topics: ["Key metrics", "Growth loops", "Analytics setup"],
    status: "locked",
  },
  {
    week: 7,
    title: "Team & Operations",
    description: "Building beyond yourself. When and how to bring on your first team members.",
    topics: ["First hires", "Culture building", "Delegation"],
    status: "locked",
  },
  {
    week: 8,
    title: "Pitch & Next Steps",
    description: "Tell your story, plan your future. Refine your pitch and map out the road ahead.",
    topics: ["Pitch crafting", "Fundraising basics", "90-day plan"],
    status: "locked",
  },
];
