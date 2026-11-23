// Top-level routing: the original chat stays at "/", the marketing modules
// get their own pages, and "/s/:id" is the public survey (no app chrome).
import App from "./App";
import { match, usePath } from "./router";
import { CampaignDetailPage, CampaignsPage } from "./intel/pages/Campaigns";
import { CompetitorPage, ResearchPage, SentimentPage, StrategyPage } from "./intel/pages/Modules";
import { AiTeamPage, DashboardPage, InsightPage } from "./intel/pages/Overview";
import { PublicSurveyPage, SurveyDetailPage, SurveysPage } from "./intel/pages/Surveys";
import { Shell, PageHeader } from "./intel/components";
import { Link } from "./router";

function NotFound() {
  return (
    <Shell title="Not found">
      <PageHeader title="Page not found" subtitle={<Link to="/dashboard">Go to the dashboard</Link>} />
    </Shell>
  );
}

export default function Root() {
  const path = usePath().replace(/\/+$/, "") || "/";
  let params: Record<string, string> | null;

  if ((params = match("/s/:id", path))) return <PublicSurveyPage id={params.id} />;
  if (path === "/") return <App />;
  if (path === "/dashboard") return <DashboardPage />;
  if (path === "/campaigns") return <CampaignsPage />;
  if ((params = match("/campaigns/:id", path))) return <CampaignDetailPage key={params.id} id={params.id} />;
  if (path === "/surveys") return <SurveysPage />;
  if ((params = match("/surveys/:id", path))) return <SurveyDetailPage key={params.id} id={params.id} />;
  if ((params = match("/insights/:id", path))) return <InsightPage id={params.id} />;
  if (path === "/ai-team") return <AiTeamPage />;

  const modules = [
    ["/competitors", CompetitorPage],
    ["/research", ResearchPage],
    ["/sentiment", SentimentPage],
    ["/strategy", StrategyPage],
  ] as const;
  for (const [base, Page] of modules) {
    if (path === base) return <Page />;
    if ((params = match(`${base}/:id`, path))) return <Page id={params.id} />;
  }
  return <NotFound />;
}
