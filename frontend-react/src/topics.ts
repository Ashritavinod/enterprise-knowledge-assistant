import {
  CakeSlice,
  Gift,
  Camera,
  Megaphone,
  Palette,
  Target,
  type LucideIcon,
} from "lucide-react";

export interface Topic {
  id: string;
  label: string;
  color: string;
  soft: string;
  icon: LucideIcon;
  prompt: string;
  blurb: string;
}

/** Suggested starting questions, one per marketing area (all verified to retrieve well). */
export const TOPICS: Topic[] = [
  {
    id: "brand",
    label: "Brand",
    color: "#E8456B",
    soft: "#FDECF0",
    icon: Palette,
    prompt: "What is the hex code for Raspberry Swirl?",
    blurb: "Colors, fonts, voice & food photography",
  },
  {
    id: "strategy",
    label: "Strategy 2026",
    color: "#5B5FC7",
    soft: "#EEEFFB",
    icon: Target,
    prompt: "How is the 2026 marketing budget allocated?",
    blurb: "Goals, personas, budget & roadmap",
  },
  {
    id: "campaigns",
    label: "Campaigns",
    color: "#D98A0B",
    soft: "#FEF4E2",
    icon: Megaphone,
    prompt: "What is the approval SLA for Tier 1 content?",
    blurb: "Approvals, offers, launches & A/B tests",
  },
  {
    id: "menu",
    label: "Menu & Cakes",
    color: "#5E9A3F",
    soft: "#EEF6E8",
    icon: CakeSlice,
    prompt: "How much does an 8-inch celebration cake cost?",
    blurb: "Pricing, launches, pitches & claims",
  },
  {
    id: "social",
    label: "Social",
    color: "#C2417F",
    soft: "#FBEAF2",
    icon: Camera,
    prompt: "How many hashtags can I use in a social post?",
    blurb: "Instagram, TikTok & community care",
  },
  {
    id: "loyalty",
    label: "Crumb Club",
    color: "#8B5A3C",
    soft: "#F6ECE4",
    icon: Gift,
    prompt: "What perks do loyalty members get?",
    blurb: "Loyalty, email & CRM",
  },
];

/** Accent color per source document, used on citation chips. */
export const DOCUMENT_COLORS: Record<string, string> = {
  "BrandGuidelines.pdf": "#E8456B",
  "MarketingStrategy2026.pdf": "#5B5FC7",
  "CampaignPlaybook.pdf": "#D98A0B",
  "ProductMarketingGuide.pdf": "#5E9A3F",
  "MarketingFAQ.pdf": "#8B5A3C",
};

export const documentColor = (name: string) => DOCUMENT_COLORS[name] ?? "#E8456B";

export const documentTitle = (name: string) =>
  name
    .replace(/\.pdf$/i, "")
    .replace(/([a-z])([A-Z0-9])/g, "$1 $2")
    .replace(/([0-9])([A-Z])/g, "$1 $2");
