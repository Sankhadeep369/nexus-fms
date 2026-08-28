// Help Center content — per tool / agent / use case. Pure data so the tutorials are
// easy to edit without touching the component.

export const HELP_SECTIONS = [
  {
    id: "getting-started",
    title: "Getting started",
    blurb: "NEXUS is your facilities-management assistant — ask questions, run agents, analyse issues, and track KPIs.",
    steps: [
      "Use the tabs at the top to move between Home, Chat, Agents, Analysis and Dashboard.",
      "Home is your personal space — click Customize to drag, resize and add widgets.",
      "Set your name and email in your profile (sidebar) so reminders and personalised features work.",
      "Admins get an extra Admin tab to create users and control who can use which tools.",
    ],
    example: null,
  },
  {
    id: "chat",
    title: "Chat",
    blurb: "Ask anything about your facilities — contracts, systems, procedures, vendors. Answers are grounded in your knowledge base.",
    steps: [
      "Type your question and press Enter. Switch between Simple and Thinking modes for shorter or more reasoned answers.",
      "Open the reference tile under an answer to see which documents it drew from.",
      "Attach files with the paperclip (if permitted) to search your own documents in chat.",
    ],
    example: { input: "What's the SLA response time in the Apex HVAC contract?", note: "Cites the exact contract clause it used." },
  },
  {
    id: "incident_triage",
    title: "Incident Triage agent",
    blurb: "Turns a reported incident into the right vendor action — it classifies the issue and drafts a vendor email.",
    steps: [
      "Describe the incident (what failed, where, severity).",
      "The agent identifies the system and responsible vendor, then drafts an incident email.",
      "Ask a follow-up (e.g. how to make the area safe) and it stays in context of that incident.",
    ],
    example: { input: "Passenger lift in Tower B is stuck between floors 3 and 4 with someone inside.", note: "Drafts an urgent email to the lift vendor + immediate safety steps." },
  },
  {
    id: "vendor_comparison",
    title: "Vendor Comparison agent",
    blurb: "Compares vendors across your contracts on price, SLA, scope and terms.",
    steps: [
      "Ask it to compare two or more vendors, or vendors for a given system.",
      "It pulls the relevant contract facts and lays them side by side.",
      "Use 'ask a follow-up' to dig into any single vendor.",
    ],
    example: { input: "Compare our two HVAC vendors on response time and annual cost.", note: "Side-by-side of SLA and pricing from the contracts." },
  },
  {
    id: "reminder",
    title: "Reminder agent",
    blurb: "Schedules email reminders for renewals, audits and deadlines — NEXUS emails you when they're due.",
    steps: [
      "Set your email once (it adopts your profile email if set).",
      "Create a reminder with a title, date/time, system and optional vendor.",
      "Edit or cancel pending reminders from the list. NEXUS emails you on the due date.",
    ],
    example: { input: "Fire-alarm certification renewal — 15 Sept, Fire Safety system.", note: "You get a confirmation email now and a reminder on the due date." },
  },
  {
    id: "analysis",
    title: "Issue Analysis",
    blurb: "Structured root-cause analysis: 5 Whys, Ishikawa (fishbone), Fault Tree and RCA reports, with corrective/preventive actions.",
    steps: [
      "Pick a method, describe the issue, and optionally ground it in your own documents.",
      "The model proposes a structured result you can edit — chains, fishbone, tree or report.",
      "Generate corrective & preventive actions, then export to Markdown or save to history.",
    ],
    example: { input: "Chilled-water pump P-2 keeps tripping on overload.", note: "Produces an editable fault tree + CAPA actions." },
  },
  {
    id: "dashboard",
    title: "KPI Dashboard",
    blurb: "Track facilities KPIs against targets — some derived live from your data, the rest you track yourself.",
    steps: [
      "Live cards (compliance, overdue, approval) are derived from your reminders and feedback.",
      "Add KPIs from a template or custom, enter values per period, or import a CSV.",
      "Click a card for its trend chart; an off-target KPI can jump straight into Analysis.",
    ],
    example: { input: "Add 'PPM Compliance', target 95%.", note: "Shows red/amber/green vs target with a trend sparkline." },
  },
  {
    id: "home",
    title: "Home canvas",
    blurb: "A personal space you arrange yourself with draggable widgets.",
    steps: [
      "Click Customize to enter edit mode.",
      "Drag widgets to move them, drag the corner to resize, and use Add widget for greetings, shortcuts, KPI tiles and notes.",
      "Click Done to lock it. Your layout is saved on this device. Reset restores the default.",
    ],
    example: null,
  },
];

export const helpSection = (id) => HELP_SECTIONS.find((s) => s.id === id) || HELP_SECTIONS[0];
