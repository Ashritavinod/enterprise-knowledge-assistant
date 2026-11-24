"""Content for the Honeycrumb Bakehouse marketing knowledge base.

Honeycrumb Bakehouse is a fictional company. Every document below describes the
same marketing organization, so names, numbers, colors and rules are kept
consistent across files. Edit the HTML here and rerun
`python scripts/generate_marketing_docs.py` to rebuild the PDFs.
"""

COMPANY = "Honeycrumb Bakehouse"


# When each document was last revised. Shown in the document's details table
# and in every page footer; edit here and regenerate the PDFs.
LAST_UPDATED = {
    "BrandGuidelines.pdf": "November 10, 2026",
    "MarketingStrategy2026.pdf": "November 3, 2026",
    "CampaignPlaybook.pdf": "November 17, 2026",
    "ProductMarketingGuide.pdf": "November 12, 2026",
    "MarketingFAQ.pdf": "November 20, 2026",
}


def meta_table(owner: str, version: str, effective: str, review: str, related: str, *, document: str) -> str:
    return f"""
<table class="meta">
<tr><td><b>Document owner</b></td><td>{owner}</td></tr>
<tr><td><b>Version</b></td><td>{version}</td></tr>
<tr><td><b>Effective date</b></td><td>{effective}</td></tr>
<tr><td><b>Last updated</b></td><td>{LAST_UPDATED[document]}</td></tr>
<tr><td><b>Next review</b></td><td>{review}</td></tr>
<tr><td><b>Classification</b></td><td>Internal Use Only</td></tr>
<tr><td><b>Related documents</b></td><td>{related}</td></tr>
</table>
"""


BRAND_GUIDELINES = f"""
<h1>Honeycrumb Bakehouse Brand Guidelines</h1>
<p class="sub">How Honeycrumb looks, sounds and shows up everywhere we bake, post and serve.</p>
{meta_table("Theo Marchetti, VP Brand &amp; Creative", "4.0", "January 6, 2026", "July 2026",
            "MarketingStrategy2026.pdf, CampaignPlaybook.pdf, ProductMarketingGuide.pdf, MarketingFAQ.pdf",
            document="BrandGuidelines.pdf")}

<h2>1. Company Overview</h2>
<p>Honeycrumb Bakehouse is a scratch bakery and dessert brand founded in 2011 in Portland, Oregon,
by baker Maya Okonkwo-Reyes, who is still our Founder and CEO. We started with a single
twelve-seat café on Alberta Street and a recipe for honey butter croissants. Today we operate
64 cafés across Oregon, Washington and California, sell celebration cakes for pickup and
delivery, run the Crumb Club loyalty program, and sell bake-at-home desserts through our
Honeycrumb at Home grocery line. 2025 revenue was $148M.</p>

<h2>2. Mission, Vision and Values</h2>
<p><b>Mission:</b> Bake everyday moments into celebrations.</p>
<p><b>Vision:</b> To be the neighborhood bakery people across the West Coast choose for every
moment worth sharing, from a Tuesday morning croissant to a wedding cake.</p>
<p><b>Values:</b></p>
<ul>
<li>Made from scratch, every morning. Nothing is baked from frozen dough in our cafés.</li>
<li>Real ingredients. Cultured butter from our Willamette Valley dairy partner, Oregon wildflower honey and seasonal fruit from Pacific Northwest farms.</li>
<li>Warmth first. Every guest is treated like a regular.</li>
<li>Waste less, share more. Unsold pastries are donated every evening.</li>
</ul>

<h2>3. Brand Positioning</h2>
<p>For people who want to make ordinary days feel special, Honeycrumb Bakehouse is the
neighborhood bakery that turns real, scratch-made treats into small celebrations. Unlike
national dessert chains, every Honeycrumb pastry is baked fresh in the café each morning with
local butter and honey.</p>
<p>Our tagline is <b>"Life's sweeter by the crumb."</b> It may be used on packaging, café signage,
email footers and paid social end cards. Do not rewrite or translate the tagline without
approval from Brand &amp; Creative.</p>

<h2>4. Brand Personality: The Warm Neighborhood Baker</h2>
<p>Honeycrumb sounds like the friendly baker who remembers your name and your order. The
personality has four traits: warm, playful, honest and generous. We are never snobby, never
preachy about food, and never use pressure tactics.</p>

<h2>5. Tone of Voice</h2>
<p>Our voice is constant; our tone flexes by moment. On social media we are most playful, using
light food puns (one per post at most). In email we are warm and personal, written in the
first person plural. On menus and packaging we are clear and appetizing: lead with flavor and
texture, then the ingredient story. In customer care and any allergen or food safety
conversation we are calm, direct and serious, with no jokes or emojis.</p>
<p><b>Writing style rules:</b></p>
<ul>
<li>Use sentence case for headlines and menu item descriptions.</li>
<li>Describe taste and texture with sensory words such as flaky, golden, gooey and tangy.</li>
<li>Never call a product "healthy", "guilt-free", "skinny" or "sinful". We do not moralize food.</li>
<li>Use "made from scratch" only for items baked in our cafés or our Portland bakehouse.</li>
<li>Limit emojis to two per social caption and none in subject lines for transactional email.</li>
</ul>

<h2>6. Logo</h2>
<p>The Honeycrumb logo combines the hexagon "crumb" mark (a croissant curled inside a honeycomb
cell) with the wordmark set in Fraunces. Keep clear space around the logo equal to the height
of the letter "H" in the wordmark. Minimum size is 24 px tall on screen and 0.4 inches in
print. Do not rotate, recolor outside the approved palette, add shadows or place the logo on
busy food photography without a Vanilla Cream backing panel.</p>

<h2>7. Color Palette</h2>
<table>
<tr><th>Color name</th><th>HEX</th><th>Role</th><th>Usage guidance</th></tr>
<tr><td>Honey Gold</td><td>#F5A623</td><td>Primary</td><td>Logo, primary highlights, Crumb Club materials</td></tr>
<tr><td>Raspberry Swirl</td><td>#E8456B</td><td>Accent</td><td>Call-to-action buttons, seasonal campaign accents, sale badges</td></tr>
<tr><td>Cocoa Bean</td><td>#4A2C2A</td><td>Primary dark</td><td>Headlines, body text on light backgrounds, menu boards</td></tr>
<tr><td>Pistachio</td><td>#8DBF6A</td><td>Accent</td><td>Gluten-free and plant-based markers, success states</td></tr>
<tr><td>Blueberry</td><td>#5B5FC7</td><td>Accent</td><td>Links, digital ordering UI, data charts</td></tr>
<tr><td>Vanilla Cream</td><td>#FFF6EC</td><td>Neutral</td><td>Page and packaging backgrounds, logo backing panel</td></tr>
</table>
<p>Honey Gold and Raspberry Swirl should never appear at equal weight in the same layout;
pick one as the hero color. Cocoa Bean text on Vanilla Cream is our default high-contrast pairing.</p>

<h2>8. Typography</h2>
<p>Approved typefaces are <b>Fraunces</b> for headlines and the wordmark, <b>Nunito Sans</b> for
body copy, menus and UI, and <b>Caveat</b> for handwritten accents. Use Caveat for no more
than one short phrase per asset (for example "fresh today!") and never for prices,
allergen information or legal text. Minimum body size is 16 px on web and 9 pt in print.</p>

<h2>9. Photography and Food Styling</h2>
<p>Shoot in natural light with real crumbs, real drips and real hands. Food must be the actual
product as sold: no glue, no lacquer, no inedible styling props and no retouching that
changes portion size. Show the cross-section of laminated pastries whenever possible. Lifestyle
shots should include diverse guests in real Honeycrumb cafés. Any image of a menu item used in
ordering channels must carry the correct allergen icons.</p>

<h2>10. Channel Standards</h2>
<h3>Social media</h3>
<p>Instagram and TikTok are our priority channels, followed by Pinterest and Facebook. Use no
more than three hashtags per post, and always include our branded hashtag #HoneycrumbMoments
on community and user-generated content. Respond to comments and direct messages within two
hours during café hours (7:00 a.m. to 8:00 p.m. Pacific). Any comment mentioning an allergic
reaction, foreign object or food safety concern must be escalated to Customer Care within 30
minutes and moved to a private channel.</p>
<h3>Website and ordering app</h3>
<p>Every product page must show price, allergens, and whether the item is available for same-day
pickup. Hero banners use one headline of eight words or fewer and one call to action.</p>
<h3>Email</h3>
<p>Subject lines must be 45 characters or fewer, with preheaders of 90 characters or fewer.
Every email must include the tagline in the footer, an unsubscribe link and our mailing address.</p>

<h2>11. Content Review and Brand Compliance Checklist</h2>
<p>Every asset must pass this checklist before it is published:</p>
<ul>
<li>Correct logo, clear space and approved colors.</li>
<li>Fraunces, Nunito Sans or Caveat only.</li>
<li>Food photography is unretouched and shows the real product.</li>
<li>Allergen icons and claims verified by Food Safety (Dr. Arun Mehta).</li>
<li>No banned words: healthy, guilt-free, skinny, sinful.</li>
<li>Discounts and offers match the limits in the Campaign Playbook.</li>
<li>Legal review by Nadia Farouk for any claim about nutrition, sourcing, organic or gluten-free status.</li>
</ul>
"""

MARKETING_STRATEGY = f"""
<h1>Honeycrumb Bakehouse Marketing Strategy 2026</h1>
<p class="sub">The CMO's annual plan: goals, audiences, channels, budget and roadmap.</p>
{meta_table("Olivia Hartwell, Chief Marketing Officer", "1.2", "January 12, 2026", "June 2026",
            "BrandGuidelines.pdf, CampaignPlaybook.pdf, ProductMarketingGuide.pdf, MarketingFAQ.pdf",
            document="MarketingStrategy2026.pdf")}

<h2>1. Executive Summary</h2>
<p>2026 is our expansion year. Honeycrumb will grow revenue from $148M in 2025 to $182M in 2026,
a 23% increase, by opening 12 new cafés, launching the Summer Scoops gelato line, and making
the Crumb Club the easiest way to order. Marketing's job is to build awareness in new markets,
grow loyalty membership and shift more orders to our own digital channels.</p>

<h2>2. 2026 Marketing Goals and Targets</h2>
<table>
<tr><th>Goal</th><th>2025 baseline</th><th>2026 target</th><th>Owner</th></tr>
<tr><td>Total revenue</td><td>$148M</td><td>$182M</td><td>Olivia Hartwell, CMO</td></tr>
<tr><td>Crumb Club members</td><td>410,000</td><td>600,000</td><td>Wen Li, Head of CRM &amp; Loyalty</td></tr>
<tr><td>Digital share of orders (app + web)</td><td>28%</td><td>35%</td><td>Sana Qureshi, Director of Growth Marketing</td></tr>
<tr><td>Same-café sales growth</td><td>+4%</td><td>+6%</td><td>Olivia Hartwell, CMO</td></tr>
<tr><td>Net Promoter Score</td><td>62</td><td>68</td><td>Reggie Thompson, Marketing Operations</td></tr>
<tr><td>Aided brand awareness in California</td><td>31%</td><td>45%</td><td>Theo Marchetti, VP Brand &amp; Creative</td></tr>
<tr><td>Celebration cake orders</td><td>96,000</td><td>120,000</td><td>Camille Dubois, Director of Product Marketing</td></tr>
</table>

<h2>3. Market and Expansion</h2>
<p>We will open 12 new cafés in 2026: eight in California (four in the Bay Area, two in
Sacramento and two in San Diego) and four in the Denver, Colorado metro area, our first market
outside the West Coast. New café openings follow the Tier 2 campaign process in the Campaign
Playbook, with a "First Crumb" grand-opening weekend that gives the first 200 guests a free
honey butter croissant.</p>

<h2>4. Target Audience and Personas</h2>
<p>Our core customers are urban and suburban adults aged 25 to 54 who see treats as a way to mark
moments. We focus on four personas:</p>
<ul>
<li><b>Sophie, the Weekend Treat Seeker</b> (28 to 40, urban professional). Discovers us on Instagram and TikTok, visits on weekends, loves seasonal specials. Key message: something new and beautiful to share.</li>
<li><b>Marcus, the Celebration Planner</b> (32 to 50, parent). Orders birthday and party cakes two or three times a year and wants reliability and easy ordering. Key message: stress-free celebrations, ready when you are.</li>
<li><b>Dev, the Morning Ritualist</b> (25 to 45, commuter). Buys coffee and a pastry four or more times a week, ideally through the app. Key message: your morning, made better and faster.</li>
<li><b>Elena, the Gift Giver</b> (30 to 55, office manager or HR lead). Buys corporate gift boxes and catering. Key message: thoughtful gifts that make teams feel appreciated.</li>
</ul>

<h2>5. Competitive Landscape</h2>
<p>Our three main competitors are <b>Sweetwell Patisserie</b>, a premium French-style chain with
higher prices and a formal feel; <b>Daily Dough Co.</b>, a value bakery chain that bakes from frozen
dough; and <b>Frostline Cupcakes</b>, a delivery-first dessert brand with strong TikTok presence
but no cafés. Honeycrumb wins on scratch baking, local ingredients and neighborhood warmth.
We never name competitors in advertising; comparative claims must be approved by Legal
(Nadia Farouk).</p>

<h2>6. SWOT Analysis</h2>
<ul>
<li><b>Strengths:</b> beloved hero product (the honey butter croissant), 410,000 loyalty members, scratch-baking story, strong Pacific Northwest awareness.</li>
<li><b>Weaknesses:</b> low awareness in California and Colorado, celebration cakes need 48 hours' notice, limited gluten-free range.</li>
<li><b>Opportunities:</b> gelato line for summer traffic, corporate gifting, delivery partnerships, Honeycrumb at Home grocery expansion.</li>
<li><b>Threats:</b> butter and cocoa price inflation, competitor discounting, and food safety incidents that could damage trust.</li>
</ul>

<h2>7. Channel Strategy</h2>
<h3>Social and creators</h3>
<p>Instagram and TikTok drive discovery. We will post five Instagram feed posts and four TikToks
per week, ten Pinterest pins per week, and run a paid creator program with 60 local food
creators across our markets.</p>
<h3>CRM and loyalty</h3>
<p>The Crumb Club is our growth engine. Members earn one crumb point per dollar, get a free slice
of cake on their birthday, and unlock a free pastry every 100 points. Growth tactics include
in-café sign-up at checkout and app-exclusive early access to seasonal launches.</p>
<h3>Paid media</h3>
<p>Paid social is our largest paid channel, with spend weighted 55% Instagram, 30% TikTok and
15% Pinterest. Search ads and delivery app promotions support café openings and holiday cake ordering.</p>
<h3>In-café and local</h3>
<p>Each café runs at least one community event per quarter, such as kids' cookie decorating or
a local school fundraiser, funded from the in-café and local events budget.</p>

<h2>8. 2026 Marketing Budget</h2>
<p>The total 2026 marketing budget is $11.8M, allocated as follows:</p>
<table>
<tr><th>Line item</th><th>Share</th><th>Amount</th></tr>
<tr><td>Paid social</td><td>26%</td><td>$3.07M</td></tr>
<tr><td>In-café and local events</td><td>17%</td><td>$2.01M</td></tr>
<tr><td>Content and photography</td><td>15%</td><td>$1.77M</td></tr>
<tr><td>CRM and loyalty</td><td>12%</td><td>$1.42M</td></tr>
<tr><td>Influencers and creators</td><td>10%</td><td>$1.18M</td></tr>
<tr><td>Search and delivery apps</td><td>9%</td><td>$1.06M</td></tr>
<tr><td>PR and partnerships</td><td>6%</td><td>$0.71M</td></tr>
<tr><td>Research and analytics</td><td>2%</td><td>$0.24M</td></tr>
<tr><td>Contingency</td><td>3%</td><td>$0.35M</td></tr>
</table>
<p>The contingency reserve is held by the CMO. Requests to use it go through Reggie Thompson in
Marketing Operations with a written business case.</p>

<h2>9. Seasonal Campaign Roadmap</h2>
<ul>
<li><b>Q1 - Love at First Bite</b> (February 1 to 14): Valentine's heart cookies, Raspberry Swirl Cheesecake and couples' gift boxes.</li>
<li><b>Q2 - Spring Bloom</b> (April 1 to May 10): lavender honey menu and Mother's Day cake pre-orders.</li>
<li><b>Q3 - Summer Scoops</b> (launches June 15, 2026): the gelato line in all cafés, our biggest launch of the year.</li>
<li><b>Q3 - Pumpkin Spice Croissant</b> (returns September 9, 2026): fall seasonal hero.</li>
<li><b>Q4 - Holiday Bake Shop</b> (November 1 to December 31): holiday cookie tins, yule logs and corporate gifting.</li>
</ul>

<h2>10. Measurement</h2>
<p>We report KPIs monthly in the Marketing Performance Dashboard. Marketing Operations owns data
quality. Campaign results must use the attribution rules in the Campaign Playbook.</p>
"""

CAMPAIGN_PLAYBOOK = f"""
<h1>Honeycrumb Bakehouse Campaign Playbook</h1>
<p class="sub">Step-by-step guide to planning, approving, launching and measuring campaigns.</p>
{meta_table("Sana Qureshi, Director of Growth Marketing, and Reggie Thompson, Marketing Operations Manager",
            "3.1", "January 20, 2026", "July 2026",
            "BrandGuidelines.pdf, MarketingStrategy2026.pdf, ProductMarketingGuide.pdf, MarketingFAQ.pdf",
            document="CampaignPlaybook.pdf")}

<h2>1. Campaign Planning Framework</h2>
<p>Every campaign starts with a one-page brief stating the goal, persona, offer, channels, budget,
success metric and launch date. Briefs are submitted in the marketing project tracker and
reviewed at the Monday campaign stand-up led by Sana Qureshi.</p>

<h2>2. Campaign Lifecycle</h2>
<p>Campaigns move through seven stages: Brief, Concept, Taste Test and Photo Shoot, Review and
Approval, Launch, Monitor, and Retrospective. No campaign may skip the Taste Test stage when it
features a new or changed menu item.</p>

<h2>3. Campaign Tiers and Approval Matrix</h2>
<table>
<tr><th>Tier</th><th>Definition</th><th>Approvers</th><th>Approval SLA</th><th>Brief due</th></tr>
<tr><td>Tier 1</td><td>Single-café or local social posts, budget under $5,000</td><td>Jordan Ellis, Head of Social &amp; Community</td><td>1 business day</td><td>1 week before launch</td></tr>
<tr><td>Tier 2</td><td>Regional campaigns, new café openings or budget $5,000 to $50,000</td><td>Theo Marchetti (VP Brand &amp; Creative) and Sana Qureshi (Director of Growth Marketing)</td><td>3 business days</td><td>4 weeks before launch</td></tr>
<tr><td>Tier 3</td><td>National or all-café campaigns, new product lines or budget over $50,000</td><td>Olivia Hartwell (CMO), Nadia Farouk (Legal) and Dr. Arun Mehta (Food Safety)</td><td>5 business days</td><td>10 weeks before launch</td></tr>
</table>
<p>Any asset with an allergen, nutrition, organic, gluten-free or sourcing claim needs Legal and
Food Safety review regardless of tier.</p>

<h2>4. Offers and Discount Rules</h2>
<ul>
<li>The maximum public discount is 25% off. Deeper discounts require written CMO approval.</li>
<li>Celebration cakes may never be discounted by more than 15%.</li>
<li>Buy-one-get-one offers are allowed only on cookies, bars and drip coffee.</li>
<li>Crumb Club member offers can stack with the birthday reward but not with other promotions.</li>
<li>Every offer needs an end date and a POS code set up by Marketing Operations.</li>
</ul>

<h2>5. Audience Selection</h2>
<p>Use Crumb Club segments for owned channels: Regulars (visited 8 or more times in 60 days),
Lapsed (no visit in 90 days), Celebrators (ordered a cake in the last 12 months) and New
Members (joined in the last 30 days). Paid campaigns target a radius of five miles around
participating cafés.</p>

<h2>6. Content Creation and Creative Review</h2>
<p>Creative requests go to the Brand &amp; Creative studio at least three weeks before the asset is
needed. Photo shoots happen on Tuesdays and Wednesdays at the Portland bakehouse test kitchen.
Every asset goes through two review rounds: brand review by the studio lead, then final approval
by the tier approver.</p>

<h2>7. Influencer and Creator Guidelines</h2>
<p>Paid creators must have at least 10,000 followers and disclose every paid post with #ad.
Gifted product for unpaid creators may not exceed $150 in retail value. All creator contracts are
issued through Marketing Operations (Reggie Thompson). Creators may not make health,
allergen or gluten-free claims.</p>

<h2>8. Launch Checklist</h2>
<ul>
<li>Allergen labels and menu cards verified by Food Safety.</li>
<li>POS codes live in all participating cafés 48 hours before launch.</li>
<li>Café staff tasting and talking-points training completed.</li>
<li>Delivery app and website menus updated with photos, prices and allergens.</li>
<li>Social and email assets scheduled and approved.</li>
<li>Customer Care briefed with an FAQ.</li>
</ul>

<h2>9. Sampling Events</h2>
<p>In-café and street sampling uses one-inch bite-size portions, served with tongs and gloves.
Every sampling tray must display an allergen card. Samples of items containing nuts are never
served at outdoor events.</p>

<h2>10. Campaign Monitoring</h2>
<p>Campaign owners check performance daily for the first week and weekly after that. If a paid
campaign's cost per acquisition is more than 30% above target after five days, pause it and
review creative with the Growth team.</p>

<h2>11. A/B Testing Standards</h2>
<p>Test one variable at a time. Each variant needs at least 2,000 recipients or visitors. Run tests
for at least 7 days or until results reach 95% statistical confidence. Record all results in the
experiment log maintained by Marketing Operations.</p>

<h2>12. Reporting and Retrospectives</h2>
<p>The post-campaign report is due within 7 business days after a campaign ends and must cover
spend, reach, redemptions, incremental sales and Crumb Club sign-ups. Tier 2 and Tier 3
campaigns also hold a retrospective within 14 days of the end date.</p>

<h2>13. Worked Example Scenarios</h2>
<p><b>Summer Scoops gelato launch (Tier 3).</b> Budget $420,000. Brief due April 6, 2026 for a June 15
launch. Approved by Olivia Hartwell, Nadia Farouk and Dr. Arun Mehta. Crumb Club members get
early access from June 12.</p>
<p><b>Pumpkin Spice Croissant return (Tier 3).</b> Budget $180,000. Returns September 9, 2026 with a
TikTok creator countdown and app pre-orders.</p>
<p><b>Sacramento café opening (Tier 2).</b> Budget $38,000. First Crumb weekend with a free honey
butter croissant for the first 200 guests.</p>
"""

PRODUCT_GUIDE = f"""
<h1>Honeycrumb Bakehouse Product Marketing Guide</h1>
<p class="sub">Menu, positioning, messaging and selling guidance for every Honeycrumb product line.</p>
{meta_table("Camille Dubois, Director of Product Marketing", "2.3", "February 2, 2026", "August 2026",
            "BrandGuidelines.pdf, MarketingStrategy2026.pdf, CampaignPlaybook.pdf, MarketingFAQ.pdf",
            document="ProductMarketingGuide.pdf")}

<h2>1. Product Lines</h2>
<table>
<tr><th>Line</th><th>Hero items</th><th>Price</th></tr>
<tr><td>Signature Pastries</td><td>Honey Butter Croissant, Cardamom Morning Bun, Pain au Chocolat</td><td>$4.25 to $5.50</td></tr>
<tr><td>Celebration Cakes</td><td>Raspberry Swirl Cheesecake, Triple Cocoa Layer Cake, Lemon Honey Chiffon</td><td>From $38</td></tr>
<tr><td>Cookies and Bars</td><td>Brown Butter Chocolate Chunk Cookie, Salted Honey Blondie</td><td>$3.25 to $4.50</td></tr>
<tr><td>Summer Scoops Gelato (new for 2026)</td><td>12 flavors including Honeycomb Crunch and Raspberry Swirl</td><td>$5.50 single, $7.50 double</td></tr>
<tr><td>Free &amp; Fabulous Gluten-Free</td><td>Almond Orange Cake, GF Chocolate Brownie</td><td>$4.50 to $6.00</td></tr>
<tr><td>Honeycrumb at Home</td><td>Bake-at-home croissant 6-pack, cookie dough tubs</td><td>$12.99 croissant 6-pack</td></tr>
</table>

<h2>2. Hero Product: The Honey Butter Croissant</h2>
<p>Our best-seller since 2011. A 27-layer laminated croissant made with cultured Willamette Valley
butter and brushed with warm Oregon wildflower honey. We sold 2.1 million honey butter croissants
in 2025. Price: $4.75. It is the face of grand openings and the default reward for Crumb Club
points.</p>

<h2>3. Celebration Cakes</h2>
<p>Celebration cakes come in three sizes: 6-inch (serves 6 to 8) for $38, 8-inch (serves 10 to 14)
for $54, and 10-inch (serves 18 to 24) for $72. Standard cakes must be ordered at least 48 hours
ahead for pickup or delivery. Custom designed cakes need 5 days' notice and are quoted
individually. Wedding cakes are handled by the Honeycrumb Events team with a minimum order of
$450.</p>

<h2>4. Summer Scoops Gelato</h2>
<p>Summer Scoops launches in all cafés on June 15, 2026, with Crumb Club early access from June 12.
The line has 12 flavors made in small batches at the Portland bakehouse, including Honeycomb
Crunch, Raspberry Swirl, Brown Butter Pecan and a dairy-free Mango Passionfruit sorbetto. Signature
pairing: a warm honey butter croissant split and filled with a scoop of gelato, sold as the
"Croissant Sundae" for $9.50.</p>

<h2>5. Gluten-Free Line: Free &amp; Fabulous</h2>
<p>Free &amp; Fabulous items are baked in our dedicated gluten-free kitchen in Beaverton, Oregon, and
tested to below 20 ppm gluten. Only these items may be called "gluten-free". Items from regular
café kitchens must be described as "made without gluten ingredients" only if Food Safety has
approved the wording, and must carry a cross-contact warning.</p>

<h2>6. Positioning Statement</h2>
<p>For people who want to make everyday moments feel special, Honeycrumb Bakehouse is the
neighborhood scratch bakery that bakes real-ingredient pastries and cakes fresh every morning.
Unlike national dessert chains, we bake in every café with local butter and honey, and we treat
every guest like a regular.</p>

<h2>7. Messaging Pillars</h2>
<ul>
<li><b>Made from scratch daily:</b> bakers start at 4:00 a.m. in every café; nothing is baked from frozen dough.</li>
<li><b>Real, local ingredients:</b> cultured Willamette Valley butter, Oregon wildflower honey, seasonal Pacific Northwest fruit.</li>
<li><b>Moments worth celebrating:</b> from a weekday croissant to a birthday cake, we help people mark the moments that matter.</li>
<li><b>Good neighbors:</b> 92% of our packaging is compostable and we donated 180,000 pastries to food banks in 2025.</li>
</ul>

<h2>8. Elevator Pitches</h2>
<p><b>10-second pitch:</b> Honeycrumb is the neighborhood scratch bakery that makes everyday moments
feel like a celebration.</p>
<p><b>30-second pitch:</b> Honeycrumb Bakehouse started in 2011 with one café in Portland and a honey
butter croissant people lined up for. Today we bake fresh every morning in 64 cafés with local
butter and Oregon honey, from croissants to custom celebration cakes. Join the Crumb Club and
your birthday slice is on us.</p>

<h2>9. Objection Handling</h2>
<ul>
<li><b>"It's more expensive than the supermarket."</b> Everything is baked from scratch that morning with real butter and local honey; Crumb Club members earn a free pastry every 100 points.</li>
<li><b>"I'm gluten-free."</b> Point guests to the Free &amp; Fabulous line from our dedicated gluten-free kitchen. Never promise that regular items are safe.</li>
<li><b>"I need a cake tomorrow."</b> Standard cakes need 48 hours, but every café keeps a small selection of ready-to-go 6-inch cakes daily.</li>
</ul>

<h2>10. Corporate Gifting and Catering</h2>
<p>Gift boxes start at $28 (six pastries) and holiday cookie tins at $35. Corporate orders of 50 or
more boxes get 10% off and free delivery within 15 miles of a café. Our largest 2025 corporate
client, Lumen Architects, ordered 1,200 holiday gift boxes.</p>

<h2>11. Customer Success Stories</h2>
<ul>
<li><b>Lumen Architects:</b> 1,200 holiday gift boxes delivered to clients in three states.</li>
<li><b>Riverside Elementary PTA:</b> a cookie-decorating fundraiser at our Tacoma café raised $14,000.</li>
<li><b>The Patel-Garcia wedding:</b> a five-tier Lemon Honey Chiffon cake featured in Portland Bride magazine.</li>
</ul>

<h2>12. Pricing Communication Rules</h2>
<p>Always show prices on menus and product pages. For custom cakes, say "from $38" and never publish
custom quotes. Price changes are announced by Product Marketing with at least 14 days' notice to
cafés. Do not compare our prices with competitors in any channel.</p>
"""

FAQ_ITEMS = [
    ("Brand guidelines", [
        ("What are Honeycrumb's brand colors?",
         "Our palette is Honey Gold (#F5A623, primary), Raspberry Swirl (#E8456B, accent for calls to action), Cocoa Bean (#4A2C2A, headlines and text), Pistachio (#8DBF6A, gluten-free and plant-based markers), Blueberry (#5B5FC7, links and digital UI) and Vanilla Cream (#FFF6EC, backgrounds). See BrandGuidelines.pdf section 7."),
        ("Which fonts are approved?",
         "Fraunces for headlines, Nunito Sans for body copy and menus, and Caveat for one handwritten accent phrase per asset. Caveat is never used for prices or allergen text."),
        ("What is our tagline?",
         "Our tagline is \"Life's sweeter by the crumb.\" Do not rewrite or translate it without Brand & Creative approval."),
        ("Which words are banned in our copy?",
         "Never describe products as healthy, guilt-free, skinny or sinful. We do not moralize food."),
    ]),
    ("Social media", [
        ("How many hashtags can I use in a social post?",
         "Use no more than three hashtags per post, and include #HoneycrumbMoments on community and user-generated content."),
        ("How quickly must we respond to comments and DMs?",
         "Within two hours during café hours, 7:00 a.m. to 8:00 p.m. Pacific. Food safety or allergy comments must be escalated to Customer Care within 30 minutes."),
        ("How often do we post on each channel?",
         "Five Instagram feed posts, four TikToks and ten Pinterest pins per week, owned by Jordan Ellis, Head of Social & Community."),
    ]),
    ("Campaign management", [
        ("Who approves Tier 3 campaigns?",
         "Tier 3 campaigns are approved by Olivia Hartwell (CMO), Nadia Farouk (Legal) and Dr. Arun Mehta (Food Safety), with a 5 business day SLA. The brief is due 10 weeks before launch."),
        ("What is the approval SLA for Tier 1 content?",
         "Tier 1 content is approved by Jordan Ellis within 1 business day."),
        ("What is the maximum discount we can offer?",
         "The maximum public discount is 25% off. Celebration cakes may never be discounted by more than 15%. Deeper discounts need written CMO approval."),
        ("When is the post-campaign report due?",
         "Within 7 business days after the campaign ends. Tier 2 and Tier 3 campaigns also need a retrospective within 14 days."),
        ("What is the minimum sample size for an A/B test?",
         "At least 2,000 recipients or visitors per variant, running for at least 7 days or until 95% confidence."),
    ]),
    ("Email and CRM", [
        ("What's the maximum subject line length for emails?",
         "Subject lines must be 45 characters or fewer and preheaders 90 characters or fewer."),
        ("When should marketing emails be sent?",
         "Send promotional emails on Tuesdays and Thursdays at 10:00 a.m. in the subscriber's local time. No subscriber should receive more than two promotional emails per week."),
        ("What do Crumb Club members get?",
         "One crumb point per dollar, a free pastry every 100 points, a free slice of cake on their birthday and early access to seasonal launches such as Summer Scoops."),
    ]),
    ("Product marketing", [
        ("When does Summer Scoops gelato launch?",
         "Summer Scoops launches in all cafés on June 15, 2026, with Crumb Club early access from June 12. A single scoop is $5.50."),
        ("How much do celebration cakes cost?",
         "6-inch cakes are $38, 8-inch $54 and 10-inch $72. Standard cakes need 48 hours' notice; custom cakes need 5 days."),
        ("What can we call gluten-free?",
         "Only Free & Fabulous items from the dedicated gluten-free kitchen in Beaverton, tested below 20 ppm, may be called gluten-free."),
        ("What is our best-selling product?",
         "The Honey Butter Croissant. We sold 2.1 million in 2025 at $4.75 each."),
    ]),
    ("Strategy and KPIs", [
        ("What is the 2026 revenue goal?",
         "Grow revenue from $148M in 2025 to $182M in 2026, a 23% increase."),
        ("How is the 2026 marketing budget allocated?",
         "The total 2026 marketing budget is $11.8M: paid social 26% ($3.07M); in-café and local events 17% ($2.01M); content and photography 15% ($1.77M); CRM and loyalty 12% ($1.42M); influencers and creators 10% ($1.18M); search and delivery apps 9% ($1.06M); PR and partnerships 6% ($0.71M); research and analytics 2% ($0.24M); and a 3% contingency ($0.35M) held by the CMO."),
        ("What is the Crumb Club membership target for 2026?",
         "Grow from 410,000 members to 600,000 members, owned by Wen Li, Head of CRM & Loyalty."),
        ("Who are our main competitors?",
         "Sweetwell Patisserie (premium French-style), Daily Dough Co. (value chain baking from frozen dough) and Frostline Cupcakes (delivery-first). We never name competitors in ads."),
        ("Where are the new cafés opening in 2026?",
         "Twelve new cafés: eight in California (Bay Area, Sacramento, San Diego) and four in the Denver, Colorado metro area."),
    ]),
    ("Governance", [
        ("Who reviews allergen and nutrition claims?",
         "Food Safety lead Dr. Arun Mehta verifies allergen claims and Legal counsel Nadia Farouk reviews any nutrition, sourcing, organic or gluten-free claim."),
        ("How do creators disclose sponsored posts?",
         "Paid creators must disclose every paid post with #ad. Contracts are issued through Reggie Thompson in Marketing Operations, and gifted product may not exceed $150."),
    ]),
]


def faq_html() -> str:
    parts = [
        "<h1>Honeycrumb Bakehouse Marketing FAQ</h1>",
        '<p class="sub">Quick answers for marketers, café managers, creators and agency partners.</p>',
        meta_table("Reggie Thompson, Marketing Operations Manager", "2.0", "February 9, 2026",
                   "May 2026",
                   "BrandGuidelines.pdf, MarketingStrategy2026.pdf, CampaignPlaybook.pdf, ProductMarketingGuide.pdf",
                   document="MarketingFAQ.pdf"),
    ]
    for topic, items in FAQ_ITEMS:
        parts.append(f"<h2>{topic}</h2>")
        for question, answer in items:
            parts.append(f"<p><b>Q: {question}</b> A: {answer}</p>")
    return "\n".join(parts)


DOCUMENTS = {
    "BrandGuidelines.pdf": BRAND_GUIDELINES,
    "MarketingStrategy2026.pdf": MARKETING_STRATEGY,
    "CampaignPlaybook.pdf": CAMPAIGN_PLAYBOOK,
    "ProductMarketingGuide.pdf": PRODUCT_GUIDE,
    "MarketingFAQ.pdf": faq_html(),
}
