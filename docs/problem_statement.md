# Problem Statement

The Honeycrumb Bakehouse marketing team needs one accessible place to turn
approved company information and customer feedback into reliable marketing
decisions. Marketing knowledge is currently distributed across PDF documents
covering products, campaigns, brand guidelines, menu information and strategy.
Teams may spend too much time searching these documents manually, and it can be
difficult to verify which passage supports an answer.

The team also needs to understand how customers feel about products and how
that feedback relates to sales and seasonal demand. Decisions about campaigns,
promotions and Christmas product positioning should be based on customer
sentiment, sales performance and real customer comments rather than intuition
alone.

## Product goal

Build a MarketMind assistant that lets Honeycrumb marketing employees:

- Ask questions in plain language about the company's marketing documents.
- Receive answers grounded only in relevant approved material.
- View document names, pages, sections and excerpts used to support each answer.
- Continue a conversation with follow-up questions.
- Browse, search and filter customer reviews.
- Review product ratings, sentiment, demand, growth and seasonal sales.
- Run an AI analysis that identifies marketing opportunities and concerns.
- Recommend products and campaign themes for Christmas using verified sales,
  sentiment and review data.
- Export filtered review data for further analysis.

## Current scope

### Marketing knowledge assistant

- Ingest Honeycrumb marketing PDFs from `data/policies/`.
- Preserve document structure, pages and sections during text extraction.
- Split the documents into searchable passages.
- Embed passages in a local FAISS index or an optional Azure OpenAI embedding
  deployment.
- Retrieve the passages that are relevant to a question.
- Generate answers with Azure OpenAI, grounded in the retrieved passages and
  recent conversation history.
- Include `[n]` citations that correspond to the displayed sources.
- Persist conversations, messages and query logs in PostgreSQL.
- Return the top retrieved passage when AI generation is unavailable.

### Customer reviews and insights

- Store products, reviews, monthly sales and generated insights in PostgreSQL.
- Provide a filterable review explorer with product, sentiment, rating, text,
  customer, city and date filters.
- Export the filtered result set as CSV.
- Use Azure OpenAI to classify new reviews as positive, neutral or negative,
  with confidence scores and topic labels.
- Calculate deterministic statistics for ratings, sentiment, demand, growth,
  seasonality and December sales share.
- Generate an evidence-based marketing report from verified statistics and real
  review quotations.
- Validate product names and citations so the AI cannot invent unsupported
  recommendations.

## Success criteria

- An employee can ask a natural-language marketing question and receive a
  concise, sourced answer.
- An answer cannot be presented as factual unless it is supported by retrieved
  Honeycrumb documents or earlier conversation context.
- Follow-up questions retain enough conversation context to work as standalone
  searches.
- The system clearly identifies when the documents do not contain an answer.
- Marketing teams can explore customer sentiment and sales for every product.
- An insights report is traceable to database statistics and real review text.
- Users can distinguish AI-generated results from generated demonstration data.
- The application remains usable if AI generation is unavailable, by returning
  retrieved passages or a clear not-found response.
