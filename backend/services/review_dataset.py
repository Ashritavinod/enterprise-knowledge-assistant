"""The customer reviews dataset: Honeycrumb's products, reviews and monthly sales.

The products, prices and seasonal windows come from the company documents
(product marketing guide and 2026 seasonal roadmap). The reviews and sales
figures are *generated sample data* for the demo: there is no real review
export to load. Generation is deterministic (fixed random seed), so every
database gets the same dataset.

The data covers November 2024 to October 2026, so it contains two holiday
seasons. Patterns are built in on purpose so the AI agent has something real
to find: holiday items peak in December, gelato only sells in summer, the
gluten-free almond cake has weak reviews and falling sales, and so on.
"""

import logging
import math
import random
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.db.models import Product, ProductSale, Review

logger = logging.getLogger(__name__)

SEED = 2026
FIRST_MONTH = date(2024, 11, 1)
MONTH_COUNT = 24  # November 2024 to October 2026
YEARLY_GROWTH = 1.23  # company revenue growth, from the 2026 marketing strategy


def months() -> list[date]:
    out = []
    year, month = FIRST_MONTH.year, FIRST_MONTH.month
    for _ in range(MONTH_COUNT):
        out.append(date(year, month, 1))
        month += 1
        if month == 13:
            year, month = year + 1, 1
    return out


@dataclass
class ProductSpec:
    sku: str
    name: str
    category: str
    price: float
    availability: str
    description: str
    base_units: int  # typical units in an on-sale month
    rating: float  # average star rating the reviews are drawn around
    review_target: int  # reviews over the whole period
    season: dict[int, float] = field(default_factory=dict)  # calendar month -> demand multiplier
    on_sale: set[int] | None = None  # calendar months on the menu; None = all year
    first_month: date | None = None  # launch month
    trend: float = 1.0  # extra yearly growth or decline on top of company growth
    good: tuple[str, ...] = ()
    bad: tuple[str, ...] = ()
    holiday: bool = False  # reviews mention holidays/gifting in Nov-Dec


PRODUCTS: tuple[ProductSpec, ...] = (
    ProductSpec(
        "PAS-001", "Honey Butter Croissant", "Signature Pastries", 4.75, "Year-round",
        "27-layer croissant with cultured butter, brushed with Oregon wildflower honey. Best-seller since 2011.",
        175_000, 4.7, 95, season={12: 1.1},
        good=("flaky layers and that warm honey glaze", "buttery and crisp every single time",
              "worth every penny, still warm when I got it", "the honey brush on top is perfection"),
        bad=("sold out by noon again", "a bit too sweet for me", "the price went up and the size didn't",
             "was cold and a little soggy this morning"),
    ),
    ProductSpec(
        "PAS-002", "Cardamom Morning Bun", "Signature Pastries", 4.50, "Year-round",
        "Laminated morning bun with cardamom sugar.",
        42_000, 4.5, 45,
        good=("the cardamom sugar is so fragrant", "soft inside with crunchy caramelised edges",
              "my weekend ritual with a latte"),
        bad=("too much sugar on the outside", "a little dense this time"),
    ),
    ProductSpec(
        "PAS-003", "Pain au Chocolat", "Signature Pastries", 4.50, "Year-round",
        "Classic chocolate croissant.",
        38_000, 3.9, 40, season={1: 1.1, 2: 1.1, 12: 1.1},
        good=("good dark chocolate inside", "nice and flaky"),
        bad=("dry and stale by the afternoon", "barely any chocolate in the middle",
             "tasted like it was from yesterday"),
    ),
    ProductSpec(
        "CAK-001", "Raspberry Swirl Cheesecake", "Celebration Cakes", 38.00, "Year-round",
        "Celebration cheesecake with a raspberry swirl. 6-inch from $38.",
        2_600, 4.6, 40, season={2: 1.8, 5: 1.3, 12: 1.3},
        good=("creamy and not too sweet, the raspberry swirl is gorgeous", "the star of our anniversary dinner",
              "looked as good as it tasted"),
        bad=("the 48-hour pre-order is a hassle", "smaller than I expected for the price"),
    ),
    ProductSpec(
        "CAK-002", "Triple Cocoa Layer Cake", "Celebration Cakes", 38.00, "Year-round",
        "Three-layer chocolate celebration cake.",
        3_100, 4.4, 40, season={11: 1.15, 12: 1.4},
        good=("rich, moist and a huge hit at the birthday party", "the chocolate ganache is incredible",
              "fed the whole office and everyone asked where it was from"),
        bad=("very rich, a small slice is enough", "frosting was melting when we picked it up"),
    ),
    ProductSpec(
        "CAK-003", "Lemon Honey Chiffon", "Celebration Cakes", 38.00, "Year-round",
        "Light lemon chiffon cake with honey cream.",
        1_500, 3.8, 30, season={1: 0.7, 2: 0.7, 4: 1.6, 5: 1.6, 6: 1.2, 7: 1.2, 12: 0.7},
        good=("light and fresh, perfect for spring", "lovely lemon flavour"),
        bad=("the cake had collapsed in the box", "the sponge was bland", "dried out quickly"),
    ),
    ProductSpec(
        "COO-001", "Brown Butter Chocolate Chunk Cookie", "Cookies and Bars", 3.25, "Year-round",
        "Brown butter cookie with dark chocolate chunks.",
        65_000, 4.6, 60, season={12: 1.2},
        good=("gooey centre and crispy edges", "the best cookie in town, no contest",
              "huge chocolate chunks and a hint of sea salt"),
        bad=("smaller than it used to be", "a bit overbaked today"),
    ),
    ProductSpec(
        "COO-002", "Salted Honey Blondie", "Cookies and Bars", 3.75, "Year-round",
        "Chewy blondie with honey and flaky salt.",
        21_000, 3.6, 30,
        good=("chewy with a nice honey flavour", "great salty-sweet balance"),
        bad=("way too salty", "overly sweet and greasy", "dry around the edges"),
    ),
    ProductSpec(
        "GF-001", "Almond Orange Cake (GF)", "Free & Fabulous Gluten-Free", 6.00, "Year-round",
        "Gluten-free almond and orange cake from the dedicated GF kitchen.",
        6_000, 3.1, 30, trend=0.65,
        good=("great to have a real gluten-free option", "nice orange zest"),
        bad=("very dry and crumbly", "fell apart before I could eat it", "too expensive for such a small slice",
             "tasted stale"),
    ),
    ProductSpec(
        "GF-002", "GF Chocolate Brownie", "Free & Fabulous Gluten-Free", 4.50, "Year-round",
        "Gluten-free fudgy chocolate brownie.",
        9_000, 4.5, 30, trend=1.25,
        good=("you would never know it's gluten-free", "fudgy and rich", "my celiac daughter's favourite treat"),
        bad=("a little too dense", "sold out at my café twice this week"),
    ),
    ProductSpec(
        "HOM-001", "Bake-at-Home Croissant 6-Pack", "Honeycrumb at Home", 12.99, "Year-round",
        "Six frozen croissants to bake at home, sold in grocery stores.",
        7_000, 3.7, 35, season={1: 0.8, 3: 0.8, 4: 0.8, 5: 0.8, 6: 0.7, 7: 0.7, 8: 0.7, 9: 0.8, 11: 1.5, 12: 2.6},
        holiday=True,
        good=("made our Christmas morning breakfast feel special", "almost as good as in the café",
              "easy to bake and smelled amazing"),
        bad=("the baking instructions were confusing", "didn't rise properly in my oven",
             "came out flat and pale"),
    ),
    ProductSpec(
        "SEA-001", "Pumpkin Spice Croissant", "Seasonal", 4.95, "Sep–Nov",
        "Fall seasonal hero, returns every September.",
        48_000, 4.4, 40, season={9: 1.0, 10: 1.2, 11: 0.9}, on_sale={9, 10, 11},
        good=("tastes exactly like fall", "the pumpkin filling is so creamy", "I wait all year for this"),
        bad=("too much spice for me", "wish it stayed on the menu longer"),
    ),
    ProductSpec(
        "SEA-002", "Holiday Cookie Tin", "Seasonal", 35.00, "Nov–Dec",
        "Holiday Bake Shop cookie tin, a favourite for gifts.",
        9_000, 4.7, 55, season={11: 0.6, 12: 1.6}, on_sale={11, 12}, holiday=True,
        good=("the perfect Christmas gift, everyone loved it", "beautiful tin and every cookie was delicious",
              "ordered ten for family and friends", "the gingerbread ones were the best"),
        bad=("the tin arrived dented", "delivery came two days late, just before Christmas"),
    ),
    ProductSpec(
        "SEA-003", "Yule Log", "Seasonal", 42.00, "Nov–Dec",
        "Chocolate yule log from the Holiday Bake Shop.",
        3_000, 4.2, 40, season={11: 0.3, 12: 1.8}, on_sale={11, 12}, holiday=True,
        good=("stunning centrepiece for Christmas dinner", "rich chocolate and beautifully decorated"),
        bad=("sold out everywhere by December 20th", "you have to pre-order weeks ahead",
             "a bit dry in the middle"),
    ),
    ProductSpec(
        "GIF-001", "Corporate Gift Box", "Gifting", 28.00, "Year-round",
        "Six-pastry gift box; corporate orders of 50 or more get custom ribbons.",
        1_800, 4.3, 35, season={1: 0.6, 2: 0.7, 3: 0.6, 4: 0.7, 5: 0.8, 6: 0.6, 7: 0.5, 8: 0.5, 9: 0.6,
                                10: 0.8, 11: 1.8, 12: 3.5},
        holiday=True,
        good=("our clients loved the holiday boxes", "made our team feel appreciated",
              "beautiful packaging with the custom ribbon"),
        bad=("the order process for large quantities was slow", "a couple of boxes were delivered late"),
    ),
    ProductSpec(
        "SEA-004", "Summer Scoops Gelato", "Seasonal", 5.50, "Jun–Sep",
        "New in 2026: 12 small-batch gelato flavours including Honeycomb Crunch.",
        70_000, 4.5, 45, season={6: 0.6, 7: 1.2, 8: 1.2, 9: 0.6}, on_sale={6, 7, 8, 9},
        first_month=date(2026, 6, 1),
        good=("Honeycomb Crunch is unreal", "the croissant sundae is genius", "so creamy and full of flavour"),
        bad=("melted before I got to the car", "the line was 30 minutes long"),
    ),
    ProductSpec(
        "SEA-005", "Valentine's Heart Cookies", "Seasonal", 4.00, "Feb 1–14",
        "Heart-shaped sugar cookies for Love at First Bite.",
        30_000, 4.2, 25, season={2: 1.0}, on_sale={2},
        good=("so cute, my partner loved them", "perfect little Valentine's treat"),
        bad=("mostly sugar, not much flavour", "broken in the bag"),
    ),
)

FIRST_NAMES = (
    "Ava", "Ben", "Chloe", "Daniel", "Emma", "Farah", "Grace", "Hiro", "Isla", "Jamal", "Kira", "Leo",
    "Maya", "Noah", "Olivia", "Priya", "Quinn", "Rosa", "Sam", "Tara", "Uma", "Victor", "Wen", "Yusuf", "Zoe",
)
CITIES = ("Portland", "Portland", "Seattle", "Eugene", "Tacoma", "Beaverton", "San Francisco", "Sacramento", "Denver")
CHANNELS = ("In-café", "In-café", "Mobile app", "Google", "Delivery app", "Website")

OPENERS = {
    "positive": ("Absolutely loved the {p}.", "The {p} was fantastic.", "Best {p} I've had in a long time.",
                 "Can't stop buying the {p}.", "Really impressed with the {p}."),
    "mixed": ("The {p} was okay.", "Mixed feelings about the {p}.", "Decent {p}, nothing amazing.",
              "The {p} was fine overall."),
    "negative": ("Disappointed with the {p}.", "Not happy with the {p} this time.", "The {p} let me down.",
                 "Expected a lot more from the {p}."),
}
CLOSERS = {
    "positive": ("Staff were lovely too.", "Will definitely be back!", "Highly recommend.", ""),
    "mixed": ("Might try something else next time.", "", "Staff were friendly though."),
    "negative": ("Not great for the price.", "Won't be ordering it again.", "Service was slow as well.", ""),
}
HOLIDAY_NOTES = ("Bought it for the holidays.", "Perfect for our Christmas party.", "Got it as a holiday gift.")


def _demand(spec: ProductSpec, month: date, index: int) -> float:
    if spec.first_month and month < spec.first_month:
        return 0.0
    if spec.on_sale is not None and month.month not in spec.on_sale:
        return 0.0
    growth = (YEARLY_GROWTH * spec.trend) ** (index / 12)
    return spec.base_units * spec.season.get(month.month, 1.0) * growth


def _rating(rng: random.Random, mean: float) -> int:
    weights = [math.exp(-((r - mean) ** 2) / 1.6) + 0.02 for r in range(1, 6)]
    return rng.choices(range(1, 6), weights=weights)[0]


def _sentence(text: str) -> str:
    return text[:1].upper() + text[1:]


def _review_text(rng: random.Random, spec: ProductSpec, rating: int, month: date) -> str:
    name = spec.name.replace(" (GF)", "").lower() if not spec.name.startswith("Valentine") else spec.name
    if rating >= 4:
        tone, detail = "positive", _sentence(rng.choice(spec.good)) + "."
        if rating == 4 and rng.random() < 0.25:  # happy overall, with a gripe
            detail += f" Only complaint: {rng.choice(spec.bad)}."
    elif rating == 3:
        tone = "mixed"
        detail = f"{_sentence(rng.choice(spec.good))}, but {rng.choice(spec.bad)}."
    else:
        tone, detail = "negative", _sentence(rng.choice(spec.bad)) + "."
    parts = [rng.choice(OPENERS[tone]).format(p=name), detail]
    if spec.holiday and month.month in (11, 12) and rng.random() < 0.6:
        parts.append(rng.choice(HOLIDAY_NOTES))
    parts.append(rng.choice(CLOSERS[tone]))
    return " ".join(p for p in parts if p)


def _review_day(rng: random.Random, spec: ProductSpec, month: date) -> date:
    last = 28 if month.month == 2 else 30
    first = 1
    if spec.sku == "SEA-004" and month.month == 6:
        first = 15  # gelato launched June 15
    if spec.sku == "SEA-005":
        last = 20  # sold Feb 1-14; a few reviews come in after
    return month.replace(day=rng.randint(first, last))


def generate() -> tuple[list[dict], list[dict], list[dict]]:
    """Build (products, sales, reviews) rows. Same output on every call."""
    rng = random.Random(SEED)
    all_months = months()
    products, sales, reviews = [], [], []
    for spec in PRODUCTS:
        products.append({
            "sku": spec.sku, "name": spec.name, "category": spec.category, "price": spec.price,
            "availability": spec.availability, "description": spec.description,
        })
        demand = [_demand(spec, m, i) for i, m in enumerate(all_months)]
        for month, expected in zip(all_months, demand):
            if expected <= 0:
                continue
            units = max(1, round(expected * rng.uniform(0.92, 1.08)))
            sales.append({"sku": spec.sku, "month": month, "units": units, "revenue": round(units * spec.price, 2)})
        # Spread the product's reviews over the months in proportion to demand.
        total = sum(demand)
        for month, expected in zip(all_months, demand):
            if expected <= 0:
                continue
            share = spec.review_target * expected / total
            count = int(share) + (1 if rng.random() < share - int(share) else 0)
            for _ in range(count):
                rating = _rating(rng, spec.rating)
                reviews.append({
                    "sku": spec.sku,
                    "customer": f"{rng.choice(FIRST_NAMES)} {rng.choice('ABCDEFGHJKLMNPRSTW')}.",
                    "rating": rating,
                    "text": _review_text(rng, spec, rating, month),
                    "channel": rng.choice(CHANNELS),
                    "city": rng.choice(CITIES),
                    "review_date": _review_day(rng, spec, month),
                })
    reviews.sort(key=lambda r: r["review_date"])
    return products, sales, reviews


def seed(db: Session, reset: bool = False) -> bool:
    """Load the dataset into PostgreSQL. Skips when products exist, unless `reset`."""
    if reset:
        for model in (Review, ProductSale, Product):
            db.execute(delete(model))
    elif db.scalar(select(func.count()).select_from(Product)):
        return False
    products, sales, reviews = generate()
    by_sku = {}
    for row in products:
        product = Product(**row)
        db.add(product)
        by_sku[row["sku"]] = product
    db.flush()
    db.add_all(ProductSale(product_id=by_sku[r.pop("sku")].id, **r) for r in sales)
    db.add_all(Review(product_id=by_sku[r.pop("sku")].id, topics=[], **r) for r in reviews)
    db.flush()
    logger.info("Seeded reviews dataset: %d products, %d monthly sales rows, %d reviews",
                len(products), len(sales), len(reviews))
    return True
