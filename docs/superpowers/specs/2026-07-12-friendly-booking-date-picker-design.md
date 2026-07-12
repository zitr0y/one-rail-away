# Friendly booking date picker design

## Purpose

Replace the raw date field with a compact, obvious date control that makes the
default—tomorrow—clear at a glance while preserving a fast way to select any
future booking date.

## Interface

TripDetails replaces the native field and checkout fine print with one large
blue three-part control:

```text
[ ‹ ]  [ Tomorrow ]  [ › ]
```

All three buttons use the brand blue treatment with white content. The centre
button is wider and displays `Today`, `Tomorrow`, or an abbreviated future date
such as `Tue 14 Jul`. The left arrow moves one local-calendar day backward and
is disabled on today; the right arrow moves one day forward. Selecting the
centre button opens the browser's native date calendar.

## Data flow and compatibility

TripDetails continues to own the ISO booking-date state. New pure booking-date
helpers format the friendly label and move an ISO date by calendar days. The
existing hidden-but-rendered native date input synchronizes direct calendar
selection with this state; the centre button opens it through `showPicker()`
with a programmatic click fallback. The booking URL continues to receive the
same ISO date, so no reachability or Trainline URL contract changes.

## Accessibility and tests

Each arrow has an explicit accessible label. The centre button exposes the
current friendly date as its accessible name, and keyboard focus uses the
existing visible blue focus treatment. Tests cover the label/date helpers,
today's disabled previous button, friendly default label, native calendar input
constraints, and the selected date in the booking URL.
