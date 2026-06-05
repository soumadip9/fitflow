import os
import re
import requests
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote_plus
from typing import Any, Dict, List, Optional, Set, Tuple

# Minimum products to return when suggestions exist (merged into one group if topped up).
_MIN_SHOPPING_ITEMS = 3

# After all suggestion queries, if still short or empty, try in order until ≥3 unique items.
_FALLBACK_QUERY_CHAIN_MALE: List[str] = [
    "men accessories fashion",
    "formal shoes men",
    "casual sneakers men",
    "minimalist watch men",
    "leather belt men",
]
_FALLBACK_QUERY_CHAIN_FEMALE: List[str] = [
    "women accessories fashion",
    "women formal heels",
    "women casual sneakers",
    "minimalist watch women",
    "women leather belt",
]

_CLEAN_STOPWORDS = frozenset({"add", "replace", "with", "consider", "try", "or"})

# Final fallback when nothing else matches (never send raw suggestion).
_FALLBACK_QUERY_MALE = "men fashion clothing india"
_FALLBACK_QUERY_FEMALE = "women fashion clothing india"

def _norm_gender_shop(g: Optional[str]) -> str:
    v = (g or "").lower().strip()
    if v in ("male", "m", "man", "men"):
        return "male"
    if v in ("female", "f", "woman", "women", "girl"):
        return "female"
    return ""


def _is_female_shop(g: Optional[str]) -> bool:
    return _norm_gender_shop(g) == "female"


# Keyword → shopping query (longer keys first). Heel/heels rows added per-gender in _keyword_rows.
_SHOPPING_KEYWORD_BASE: List[Tuple[str, str]] = [
    ("formal_shirt", "men dress shirt formal"),
    ("t-shirt", "men crew neck t-shirt"),
    ("longsleeve", "men long sleeve shirt"),
    ("sweatshirt", "men sweatshirt"),
    ("cardigan", "men cardigan"),
    ("pullover", "men pullover sweater"),
    ("sneakers", "casual sneakers men"),
    ("sneaker", "casual sneakers men"),
    ("trousers", "men dress trousers"),
    ("blazer", "men blazer"),
    ("sweaters", "men sweater"),
    ("hoodie", "men hoodie"),
    ("shorts", "men athletic shorts"),
    ("boots", "formal boots men"),
    ("boot", "formal boots men"),
    ("slides", "men slides sandals"),
    ("slide", "men slides sandals"),
    ("sandals", "mens leather sandals summer"),
    ("sandal", "mens leather sandals summer"),
    ("watch", "minimalist watch men"),
    ("belt", "leather belt men"),
    ("jeans", "men jeans"),
    ("skirt", "men chino shorts"),
    ("dress", "men smart casual outfit"),
    ("vest", "men vest"),
    ("top", "men smart casual shirt"),
    ("sport", "men running shoes"),
    ("casual", "men casual outfit"),
]


def _keyword_rows(gender: Optional[str]) -> List[Tuple[str, str]]:
    """Heels only map to womens shopping queries for female profile; else mens dress shoes."""
    rows = list(_SHOPPING_KEYWORD_BASE)
    if _is_female_shop(gender):
        # insert after shorts / before boots — order: longer keys first
        heel_rows = [("heels", "women heels"), ("heel", "women heels")]
    else:
        heel_rows = [
            ("heels", "mens leather dress shoes"),
            ("heel", "mens oxford dress shoes formal"),
        ]
    # place heel pairs before boot entries for stable matching
    insert_at = next((i for i, (k, _) in enumerate(rows) if k == "boots"), len(rows))
    for i, pair in enumerate(heel_rows):
        rows.insert(insert_at + i, pair)
    return rows


def _norm_suggestion_text(s: str) -> str:
    return re.sub(r"[^\w\s-]", " ", (s or "").lower()).strip()


def _strip_trailing_for_occasion(s: str) -> str:
    return re.sub(r"\s+for\s+[a-z0-9\s_-]+$", "", (s or "").strip(), flags=re.I).strip()


def _map_keyword_to_query(norm: str, gender: Optional[str] = None) -> str:
    if not norm:
        return ""
    for kw, query in _keyword_rows(gender):
        if re.search(rf"(?<![a-z0-9_-]){re.escape(kw)}(?![a-z0-9_-])", norm):
            return query
    return ""


def _first_alternative_match(lowercase_text: str, gender: Optional[str] = None) -> str:
    parts = re.split(r"\s+or\s+", (lowercase_text or "").strip(), flags=re.I)
    for part in parts:
        part = _strip_trailing_for_occasion(part.strip())
        if not part:
            continue
        q = _map_keyword_to_query(_norm_suggestion_text(part), gender=gender)
        if q:
            return q
    return ""


def suggestion_to_shopping_query(suggestion: str, gender: Optional[str] = None) -> str:
    raw = (suggestion or "").strip()
    if not raw:
        return ""
    low = raw.lower()
    norm = _norm_suggestion_text(raw)

    if " with " in low:
        tail = low.split(" with ", 1)[1]
        tail = _strip_trailing_for_occasion(tail)
        q = _map_keyword_to_query(_norm_suggestion_text(tail), gender=gender)
        if q:
            return q

    if re.search(r"\s+or\s+", low):
        q = _first_alternative_match(low, gender=gender)
        if q:
            return q

    if low.startswith("add "):
        q = _first_alternative_match(low[4:], gender=gender)
        if q:
            return q

    return _map_keyword_to_query(norm, gender=gender)


def _fallback_token_query(text: str) -> str:
    if not text or not str(text).strip():
        return ""
    s = str(text).lower()
    s = re.sub(r"[^\w\s-]", " ", s)
    parts: List[str] = []
    for raw in s.split():
        token = raw.strip().lower()
        if not token:
            continue
        bare = token.strip("-")
        if bare in _CLEAN_STOPWORDS:
            continue
        parts.append(token)
    q = " ".join(parts).strip()
    if len(q) > 80:
        q = q[:80].rsplit(" ", 1)[0].strip()
    return q


def _fallback_query_for_gender(gender: Optional[str]) -> str:
    return _FALLBACK_QUERY_FEMALE if _is_female_shop(gender) else _FALLBACK_QUERY_MALE


def clean_query(suggestion: str, gender: Optional[str] = None) -> str:
    """
    Map outfit suggestion text → a safe Google Shopping search query.
    """
    raw = (suggestion or "").strip()
    if not raw:
        return _fallback_query_for_gender(gender)

    low = raw.lower()

    # Footwear upgrades: sneakers/sandals → leather boots (office / formal feedback).
    if re.search(r"replace.*(sneakers?|sandals?|slides?)", low) and re.search(
        r"leather boots|boots|oxford|dress shoes|chelsea", low
    ):
        return (
            "women leather ankle boots block heel"
            if _is_female_shop(gender)
            else "mens leather chelsea boots brown formal"
        )
    if "sandals" in low and ("boot" in low or "leather" in low) and "replace" in low:
        return (
            "women leather ankle boots"
            if _is_female_shop(gender)
            else "mens leather chelsea boots formal"
        )

    # Explicit phrase rules (examples from product spec).
    if re.search(r"replace\s+sneaker\s+with\s+boot\s+or\s+heel", low):
        return (
            "women formal heels ankle boots"
            if _is_female_shop(gender)
            else "formal boots men"
        )
    if "boot or heel" in low and "sneaker" in low and "replace" in low:
        return (
            "women formal heels ankle boots"
            if _is_female_shop(gender)
            else "formal boots men"
        )

    if re.search(r"add\s+watch\s+or\s+belt", low):
        return (
            "minimalist watch women"
            if _is_female_shop(gender)
            else "minimalist watch men"
        )

    if re.search(r"^add\s+accessory\b", low) or re.search(r"\badd\s+accessory\b", low):
        return (
            "women accessories fashion"
            if _is_female_shop(gender)
            else "men accessories fashion"
        )

    q = suggestion_to_shopping_query(raw, gender=gender)
    if q:
        return q

    if re.search(r"\bshoes?\b", low):
        return "casual shoes women" if _is_female_shop(gender) else "casual shoes men"

    q = _fallback_token_query(raw)
    if q:
        return q

    return _fallback_query_for_gender(gender)


def google_shopping_search_url(search_query: str) -> str:
    """Direct Google Shopping tab URL (no third-party API)."""
    q = (search_query or "").strip() or "fashion clothing"
    return f"https://www.google.com/search?tbm=shop&hl=en&gl=in&q={quote_plus(q)}"


def _product_dedupe_key(p: Dict[str, Any]) -> str:
    return f"{p.get('link')}|{p.get('title')}"


def _dedupe_products(products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Set[str] = set()
    out: List[Dict[str, Any]] = []
    for p in products:
        k = _product_dedupe_key(p)
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def _enforce_gender_in_query(query: str, gender: Optional[str]) -> str:
    """
    Ensure the SerpAPI query only returns gender-appropriate results.
    For male users: strip any 'women/woman/female' tokens, append 'men' if not present.
    For female users: strip any 'men/man/male' tokens (not 'women'), append 'women' if needed.
    """
    g = _norm_gender_shop(gender)
    q = (query or "").strip()
    if not q or not g:
        return q

    if g == "male":
        # Remove female tokens
        q = re.sub(r"\b(women|woman|female|ladies|girls?)\b", "", q, flags=re.I).strip()
        q = re.sub(r"\s{2,}", " ", q).strip()
        # Add 'men' if no male marker present
        if not re.search(r"\b(men|man|male|mens|gents)\b", q, re.I):
            q = q + " men"
    elif g == "female":
        # Remove male tokens (but not 'women')
        q = re.sub(r"\b(?<!wo)(men|man|male|mens|gents)\b", "", q, flags=re.I).strip()
        q = re.sub(r"\s{2,}", " ", q).strip()
        if not re.search(r"\b(women|woman|female|ladies)\b", q, re.I):
            q = q + " women"

    return q.strip()


def get_products(search_query: str, limit: int = 5, gender: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch top products using SerpApi Google Shopping API.
    Gracefully falls back to direct search link on failure or missing API key.
    Gender is enforced in the query to prevent cross-gender results.
    """
    q = _enforce_gender_in_query((search_query or "").strip(), gender)
    if not q:
        return []
        
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        display = q if len(q) <= 160 else q[:157] + "…"
        url = google_shopping_search_url(q)
        return [{
            "title": display,
            "image": None,
            "link": url,
            "price": "Google Shopping",
        }]

    params = {
        "engine": "google_shopping",
        "q": q,
        "api_key": api_key,
        "hl": "en",
        "gl": "in",
    }
    
    try:
        response = requests.get("https://serpapi.com/search", params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("shopping_results", [])
        products = []
        for res in results[:limit]:
            products.append({
                "title": res.get("title"),
                "image": res.get("thumbnail"),
                "link": res.get("product_link") or res.get("link") or google_shopping_search_url(q),
                "price": res.get("price"),
            })
            
        if not products:
            # Fallback if no shopping results
            display = q if len(q) <= 160 else q[:157] + "…"
            url = google_shopping_search_url(q)
            return [{
                "title": display,
                "image": None,
                "link": url,
                "price": "Google Shopping",
            }]
            
        return products
    except Exception as e:
        print(f"[shopping] SerpApi error for {q}: {e}")
        display = q if len(q) <= 160 else q[:157] + "…"
        url = google_shopping_search_url(q)
        return [{
            "title": display,
            "image": None,
            "link": url,
            "price": "Google Shopping",
        }]


def test_products() -> List[Dict[str, Any]]:
    return get_products("black casual shoes men", limit=3)


def _flatten_group_products(grouped: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    flat: List[Dict[str, Any]] = []
    for g in grouped:
        flat.extend(g.get("products") or [])
    return _dedupe_products(flat)


def _fallback_chain_for_gender(gender: Optional[str]) -> List[str]:
    if _is_female_shop(gender):
        return _FALLBACK_QUERY_CHAIN_FEMALE
    return _FALLBACK_QUERY_CHAIN_MALE


def _top_up_with_fallback_chain(
    existing: List[Dict[str, Any]],
    gender: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], str]:
    """
    Merge unique products from `existing`, then walk gendered fallback chain in order
    until we have at least _MIN_SHOPPING_ITEMS or the chain is exhausted.
    Returns (products[:_MIN_SHOPPING_ITEMS], query_label).
    """
    chain = _fallback_chain_for_gender(gender)
    prods = _dedupe_products(list(existing))
    label = ""
    if len(prods) >= _MIN_SHOPPING_ITEMS:
        return prods[: _MIN_SHOPPING_ITEMS], ""

    seen = {_product_dedupe_key(p) for p in prods}
    for fq in chain:
        print("[shopping] FALLBACK CHAIN QUERY:", fq)
        batch = get_products(fq, limit=_MIN_SHOPPING_ITEMS, gender=gender)
        if not batch:
            continue
        if not label:
            label = fq
        for p in batch:
            k = _product_dedupe_key(p)
            if k in seen:
                continue
            seen.add(k)
            prods.append(p)
            if len(prods) >= _MIN_SHOPPING_ITEMS:
                return prods[: _MIN_SHOPPING_ITEMS], label or fq

    return prods[: _MIN_SHOPPING_ITEMS], label


def outfit_slot_missing(slot: Any) -> bool:
    """True if API slot has no usable garment (null/empty or missing name/category)."""
    if slot is None:
        return True
    if not isinstance(slot, dict):
        return False
    cat = (slot.get("category") or "").strip()
    name = (slot.get("display_name") or slot.get("name") or "").strip()
    return not (cat or name)


# ── Occasion-wise gap rules (Strict) ────────────────────────────────
OCCASION_GAP_RULES: Dict[str, Dict[str, List[str]]] = {
    "office": {
        "top": ["formal shirt white", "navy blazer professional"],
        "bottom": ["black trousers professional", "grey skirt professional"],
        "shoes": ["black leather boots", "formal black heels"],
    },
    "formal_event": {
        "top": ["formal blazer black", "white dress shirt tuxedo style"],
        "bottom": ["black formal trousers", "elegant formal skirt", "black evening dress"],
        "shoes": ["black heels elegant", "black leather oxford boots"],
    },
    "casual_day": {
        "top": ["casual t-shirt cotton", "plain grey hoodie", "comfy sweatshirt"],
        "bottom": ["blue denim jeans", "relaxed fit shorts"],
        "shoes": ["white casual sneakers", "leather slides"],
    },
    "party": {
        "top": ["black slim fit blazer", "stylish party shirt", "statement jacket"],
        "bottom": ["black slim jeans", "stylish trousers", "leather skirt"],
        "shoes": ["white stylish sneakers", "black leather boots", "heels"],
    },
    "date_night": {
        "top": ["navy cardigan", "slim fit blazer", "fitted longsleeve"],
        "bottom": ["fitted black jeans", "stylish skirt", "dark trousers"],
        "shoes": ["black leather boots", "heels", "stylish sneakers"],
    },
    "gym": {
        "top": ["dry fit sports t-shirt", "running hoodie", "gym sweatshirt"],
        "bottom": ["black gym shorts", "running joggers"],
        "shoes": ["white running sneakers", "training sneakers"],
    },
    "travel": {
        "top": ["oversized hoodie", "soft sweatshirt", "comfy t-shirt", "knit cardigan"],
        "bottom": ["jogger style jeans", "stretch chinos", "comfy travel shorts"],
        "shoes": ["comfortable walking sneakers", "travel slides"],
    },
}

def preset_queries_for_outfit_gaps(
    occasion: str,
    outfit: Optional[Dict[str, Any]],
    gender: Optional[str] = None,
) -> List[str]:
    """
    Generate strict, occasion-appropriate shopping queries for missing wardrobe pieces.
    Follows neutral color preferences (black, white, navy, gray, beige).
    """
    outfit = outfit or {}
    occ = (occasion or "casual_day").lower()
    female = _is_female_shop(gender)
    top, bottom, shoes = outfit.get("top"), outfit.get("bottom"), outfit.get("shoes")
    q: List[str] = []

    gap_rules = OCCASION_GAP_RULES.get(occ, OCCASION_GAP_RULES["casual_day"])

    def _get_q(slot: str) -> List[str]:
        raw = gap_rules.get(slot, [])
        return [f"{r} {'women' if female else 'men'}" for r in raw]

    if outfit_slot_missing(top):
        q.extend(_get_q("top"))

    if outfit_slot_missing(bottom):
        q.extend(_get_q("bottom"))

    if outfit_slot_missing(shoes):
        q.extend(_get_q("shoes"))

    # Dedupe while keeping order
    seen: Set[str] = set()
    out: List[str] = []
    for s in q:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def build_shopping_links(
    suggestions: Optional[List[str]],
    limit: int = 5,
    gender: Optional[str] = None,
    preset_queries: Optional[List[str]] = None,
    is_smart_query: bool = False,
) -> List[Dict[str, Any]]:
    grouped: List[Dict[str, Any]] = []
    print("[shopping-debug] ---------- shopping pipeline ----------")
    print("[shopping-debug] 1. SUGGESTIONS RECEIVED:", suggestions)
    print("[shopping-debug] 1b. PRESET GAP QUERIES:", preset_queries)

    if not suggestions and not (preset_queries or []):
        return grouped

    has_nonempty_suggestion = any(str(s or "").strip() for s in (suggestions or []))
    has_nonempty_preset = any(str(p or "").strip() for p in (preset_queries or []))

    seen_queries: Set[str] = set()

    # Collect unique, ordered queries first so the independent SerpAPI calls can
    # run in parallel instead of sequentially (each call can take several seconds;
    # serial fetches are the main cause of the rating request exceeding its timeout).
    ordered_queries: List[str] = []

    for suggestion in suggestions or []:
        if suggestion is None:
            continue
        s = str(suggestion).strip()
        if not s:
            continue

        print("[shopping-debug] suggestion raw text:", repr(s))
        q = s if is_smart_query else clean_query(s, gender=gender)
        print("[shopping-debug] 2. CLEANED QUERY:", repr(q))

        ql = q.lower()
        if q and ql not in seen_queries:
            seen_queries.add(ql)
            ordered_queries.append(q)

    for pq in preset_queries or []:
        pq = (pq or "").strip()
        if not pq:
            continue
        pl = pq.lower()
        if pl in seen_queries:
            continue
        print("[shopping-debug] gap preset query (direct):", repr(pq))
        seen_queries.add(pl)
        ordered_queries.append(pq)

    if ordered_queries:
        with ThreadPoolExecutor(max_workers=min(6, len(ordered_queries))) as pool:
            results = list(
                pool.map(
                    lambda q: get_products(q, limit=limit, gender=gender),
                    ordered_queries,
                )
            )
        for q, products in zip(ordered_queries, results):
            if products:
                grouped.append({"query": q, "products": products})

    if not has_nonempty_suggestion and not has_nonempty_preset:
        print("build_shopping_links: no suggestions and no preset_queries")
        return grouped

    flat_count = len(_flatten_group_products(grouped))
    need_fallback = flat_count == 0 or flat_count < _MIN_SHOPPING_ITEMS

    if need_fallback:
        print(
            f"[shopping] need fallback: primary_total={flat_count}, target>={_MIN_SHOPPING_ITEMS}"
        )
        merged, fb_label = _top_up_with_fallback_chain(
            _flatten_group_products(grouped), gender=gender
        )
        if merged:
            chain0 = _fallback_chain_for_gender(gender)[0]
            q_label = fb_label or chain0
            grouped = [{"query": q_label, "products": merged}]
            print(
                f"[shopping] after fallback chain: {len(merged)} products, query_label={q_label!r}"
            )
        else:
            print("[shopping] fallback chain returned no products")

    total = sum(len(g.get("products") or []) for g in grouped)
    if total < _MIN_SHOPPING_ITEMS and (has_nonempty_suggestion or has_nonempty_preset):
        print(f"[shopping] NOTE: only {total} link(s) (expected up to {_MIN_SHOPPING_ITEMS})")

    print(
        "[shopping-debug] FINAL shopping_products groups=",
        len(grouped),
        "total_products=",
        total,
    )
    if (has_nonempty_suggestion or has_nonempty_preset) and total == 0:
        print("ERROR: no shopping links built")

    print("[shopping-debug] ---------- end shopping pipeline ----------")
    return grouped


def get_shopping_products(
    suggestions,
    occasion: str = "casual_day",
    per_query: int = 3,
    max_queries: int = 4,
    gender: Optional[str] = None,
) -> List[Dict[str, Any]]:
    _ = occasion, max_queries
    return build_shopping_links(
        suggestions,
        limit=max(1, min(int(per_query), 3)),
        gender=gender,
    )
