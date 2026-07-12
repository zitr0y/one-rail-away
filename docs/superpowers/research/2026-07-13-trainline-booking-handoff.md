# Trainline booking handoff research (2026-07-13)

## Current decision

The Book CTA opens `https://www.thetrainline.com/`, the ordinary public
Trainline landing page. It is a deliberate temporary fallback: it does **not**
transfer the selected origin, destination, or date from onestopeurope.

## Why the old link was removed

- The previous `https://www.trainline.eu/search/{origin}/{destination}/{date}/`
  pattern returns a static Trainline hand-off today, not a reliable search-results
  experience. An HTTP 200 response alone was misleading.
- Chronotrains' example `https://prf.hn/click/camref:1101l3LQa9` redirects through
  its affiliate tracker to a normal `thetrainline.com` landing page. It provides a
  better landing experience but does not carry a chosen route/date.
- The old TradeDoubler deep-link PDF conflicts with Trainline's current affiliate
  page, which describes Partnerize links to landing pages and a widget for selected
  partners. Treat the former as legacy guidance, not a public URL contract.

## Future Partnerize integration checklist

1. Apply to [Trainline's Affiliate Programme](https://www.thetrainline.com/about-us/partnerships/affiliates)
   and complete Partnerize onboarding.
2. After approval, create a campaign link with the Partnerize Quicklink tooling.
   Store the provided complete URL/configuration; do not append a guessed `aff`
   parameter to a Trainline URL.
3. Use that approved campaign link for the landing-page CTA and manually verify
   attribution plus a clean search/booking flow in an incognito browser.
4. Ask Trainline's affiliate team for the supported way to retain origin,
   destination, and travel date. Their current page advertises a customisable
   booking widget for selected partners; that is the likely supported route.
5. Only after Trainline provides an approved deep-link or widget contract, design
   the integration, keep its credentials/configuration out of the client bundle,
   and add an end-to-end manual verification checklist.

## Contact and source

- Official programme page: <https://www.thetrainline.com/about-us/partnerships/affiliates>
- The page names `affiliates@thetrainline.com` for affiliate questions and says
  Partnerize manages partner links and reporting.
