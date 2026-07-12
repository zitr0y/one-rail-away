# Booking date picker design

## Purpose

Let a traveller choose the date used by the Trainline booking link, so the
external search opens for the intended day rather than an implicit default.

## Interface

When the planner has an origin, a destination, and a valid journey, TripDetails
shows a native `input[type=date]` directly above the booking CTA. It is hidden
whenever TripDetails is not rendered.

The control defaults to tomorrow in the traveller's local calendar and prevents
selecting a past date. Existing planner styles/theme tokens should give the
native control basic visual continuity, while retaining native browser behavior.

## Data flow

TripDetails owns the selected booking date. It initializes it when the rendered
origin/destination pair changes, retains user edits while that pair remains
selected, and passes it to `bookingUrl`. The helper serializes the supplied date
in Trainline's path-based search URL. Map reachability remains based on the
existing representative data sample; the selected booking date changes only the
external booking search.

## Error handling and testing

The Book CTA remains available with the default date. Booking URL tests cover a
caller-supplied date and preserve URL encoding/affiliate behavior. Component
tests cover the date field's visibility, default, minimum date, and link update.

If the native input proves visually unsuitable in browser review, replace only
the control with the repository's existing TypeScript date-picker approach;
the state and booking URL contract stay unchanged.
