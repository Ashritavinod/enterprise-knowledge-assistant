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
    color: "#B92510",
    soft: "#F8E4DF",
    icon: Palette,
    prompt: "What is the hex code for Raspberry Swirl?",
    blurb: "Colors, fonts, voice & food photography",
  },
  {
    id: "strategy",
    label: "Strategy 2026",
    color: "#46608C",
    soft: "#E8ECF3",
    icon: Target,
    prompt: "How is the 2026 marketing budget allocated?",
    blurb: "Goals, personas, budget & roadmap",
  },
  {
    id: "campaigns",
    label: "Campaigns",
    color: "#A35A1F",
    soft: "#F6E9DC",
    icon: Megaphone,
    prompt: "What is the approval SLA for Tier 1 content?",
    blurb: "Approvals, offers, launches & A/B tests",
  },
  {
    id: "menu",
    label: "Menu & Cakes",
    color: "#4E7A3A",
    soft: "#E9F0E4",
    icon: CakeSlice,
    prompt: "How much does an 8-inch celebration cake cost?",
    blurb: "Pricing, launches, pitches & claims",
  },
  {
    id: "social",
    label: "Social",
    color: "#9C3F5A",
    soft: "#F4E4E8",
    icon: Camera,
    prompt: "How many hashtags can I use in a social post?",
    blurb: "Instagram, TikTok & community care",
  },
  {
    id: "loyalty",
    label: "Crumb Club",
    color: "#8B572A",
    soft: "#F2E8DE",
    icon: Gift,
    prompt: "What perks do loyalty members get?",
    blurb: "Loyalty, email & CRM",
  },
];

/** Accent color per source document, used on citation chips. */
export const DOCUMENT_COLORS: Record<string, string> = {
  "BrandGuidelines.pdf": "#B92510",
  "MarketingStrategy2026.pdf": "#46608C",
  "CampaignPlaybook.pdf": "#A35A1F",
  "ProductMarketingGuide.pdf": "#4E7A3A",
  "MarketingFAQ.pdf": "#8B572A",
};

export const documentColor = (name: string) => DOCUMENT_COLORS[name] ?? "#B92510";

export const documentTitle = (name: string) =>
  name
    .replace(/\.pdf$/i, "")
    .replace(/([a-z])([A-Z0-9])/g, "$1 $2")
    .replace(/([0-9])([A-Z])/g, "$1 $2");
