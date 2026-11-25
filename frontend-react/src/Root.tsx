// Top-level routing: the chat assistant at "/", customer reviews, brand check and copywriter.
import App from "./App";
import { usePath } from "./router";
import { ReviewsPage } from "./reviews/ReviewsPage";
import { BrandCheckPage } from "./studio/BrandCheckPage";
import { CopywriterPage } from "./studio/CopywriterPage";

export default function Root() {
  const path = usePath().replace(/\/+$/, "") || "/";
  if (path === "/reviews") return <ReviewsPage />;
  if (path === "/brand-check") return <BrandCheckPage />;
  if (path === "/copywriter") return <CopywriterPage />;
  return <App />;
}
