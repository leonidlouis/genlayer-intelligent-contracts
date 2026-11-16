# OriginalWorkRegistry live demo pages

Pages used by `demo_registry.mjs` on Studionet:

- `original-essay.md` - the registered work (canonical URL on raw.githubusercontent.com, CC BY-NC 4.0, credit + link required).
- `content-farm-copy.html` - an unattributed commercial copy of most of the essay with a new byline, served from a different host (jsDelivr). Expected: **UPHELD**.
- `attributed-review.html` - a newsletter that quotes one sentence with credit and a link. Expected: **REJECTED** (quotation / licence complied).

The essay text was written for this demo; the two "suspect" pages are staged fixtures, fetched live from the web by the validators.
