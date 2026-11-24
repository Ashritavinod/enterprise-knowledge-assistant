// Top-level routing: the chat assistant at "/" and the customer reviews page.
import App from "./App";
import { usePath } from "./router";
import { ReviewsPage } from "./reviews/ReviewsPage";

export default function Root() {
  const path = usePath().replace(/\/+$/, "") || "/";
  if (path === "/reviews") return <ReviewsPage />;
  return <App />;
}
