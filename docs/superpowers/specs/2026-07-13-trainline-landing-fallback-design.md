# Trainline landing-page fallback design

## Decision

Until onestopeurope has an approved Trainline partner integration, the booking
CTA opens the ordinary Trainline homepage. It does not attempt to pass the map's
origin, destination, or selected date through an undocumented URL format.

## Rationale

The previously used `trainline.eu/search/{origin}/{destination}/{date}/` route
now serves an unsuitable static hand-off rather than a reliable journey search.
The current Trainline affiliate programme describes Partnerize links to landing
pages and a booking widget for selected partners; neither is configured for this
project yet.

## Scope

`bookingUrl` becomes a zero-argument helper that returns
`https://www.thetrainline.com/`. TripDetails retains its date control for the
user's trip context but no longer implies that Trainline receives it. The stale
affiliate environment variable and README claim are removed.

The research note and feedback backlog record the Partnerize registration,
campaign-link configuration, and partner-approved deep-link/widget work needed
before route-prefilled booking can be restored.
