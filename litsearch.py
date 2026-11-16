"""Literature search over OpenAlex.

No API key and no account needed. We stay out of the "polite pool" because that
would mean putting a personal email address in every request; the common pool is
rate limited but ample for a demo.
"""

import time
import requests

API = "https://api.openalex.org/works"
UA = "nullspace-prototype/0.1 (negative-results research prototype)"
_session = requests.Session()
_session.headers["User-Agent"] = UA


def _abstract(work):
    """OpenAlex ships abstracts as an inverted index; rebuild the text."""
    idx = work.get("abstract_inverted_index")
    if not idx:
        return ""
    positions = []
    for word, spots in idx.items():
        for spot in spots:
            positions.append((spot, word))
    positions.sort()
    return " ".join(word for _, word in positions)


def _author_list(work):
    out = []
    for a in work.get("authorships", []) or []:
        author = a.get("author") or {}
        name = author.get("display_name")
        if not name:
            continue
        institutions = [
            i.get("display_name")
            for i in (a.get("institutions") or [])
            if i.get("display_name")
        ]
        out.append({
            "name": name,
            "openalex_id": author.get("id"),
            "orcid": author.get("orcid"),
            "institutions": institutions,
            "position": a.get("author_position"),
        })
    return out


def _shape(work):
    loc = work.get("primary_location") or {}
    source = loc.get("source") or {}
    return {
        "openalex_id": work.get("id"),
        "doi": work.get("doi"),
        "title": work.get("title") or work.get("display_name") or "(untitled)",
        "year": work.get("publication_year"),
        "venue": source.get("display_name"),
        "cited_by_count": work.get("cited_by_count", 0),
        "abstract": _abstract(work)[:2000],
        "authors": _author_list(work),
        "url": (work.get("doi") or work.get("id") or ""),
    }


def search(query, from_year=None, to_year=None, per_page=8, retries=3):
    """Search OpenAlex. from_year/to_year bound publication date inclusively."""
    filters = []
    if from_year:
        filters.append(f"from_publication_date:{int(from_year)}-01-01")
    if to_year:
        filters.append(f"to_publication_date:{int(to_year)}-12-31")
    params = {
        "search": query,
        "per-page": per_page,
        "select": ",".join([
            "id", "doi", "title", "display_name", "publication_year",
            "abstract_inverted_index", "authorships", "cited_by_count",
            "primary_location",
        ]),
    }
    if filters:
        params["filter"] = ",".join(filters)
    last_error = None
    for attempt in range(retries):
        try:
            r = _session.get(API, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            r.raise_for_status()
            return [_shape(w) for w in r.json().get("results", [])]
        except Exception as exc:  # noqa: BLE001 - a demo should degrade, not die
            last_error = exc
            time.sleep(1 + attempt)
    raise RuntimeError(f"OpenAlex search failed for {query!r}: {last_error}")


def multi_search(queries, from_year=None, to_year=None, per_query=6, cap=28):
    """Run several queries, dedupe by OpenAlex id, keep the order discovered."""
    seen, out = set(), []
    for q in queries:
        try:
            hits = search(q, from_year=from_year, to_year=to_year, per_page=per_query)
        except RuntimeError:
            continue
        for h in hits:
            key = h["openalex_id"]
            if key in seen:
                continue
            seen.add(key)
            h["found_by"] = q
            out.append(h)
        if len(out) >= cap:
            break
    return out[:cap]


if __name__ == "__main__":
    hits = search("bisected T7 RNA polymerase fragments reassemble", per_page=3)
    for h in hits:
        print(h["year"], "|", h["title"][:90], "|", h["venue"])
