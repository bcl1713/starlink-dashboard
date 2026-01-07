# Spec: Time Input Consistency

## Capability ID

`time-input-consistency`

## Overview

Ensures consistent use of 24-hour time format throughout the mission planner frontend for both time input fields and time display, eliminating cognitive switching between 12-hour and 24-hour formats.

## ADDED Requirements

### Requirement: Time inputs use 24-hour format

All time input fields throughout the mission planner frontend SHALL consistently use 24-hour format (HH:mm) to match the existing display format and align with professional aviation/maritime standards.

#### Scenario: User enters departure time adjustment

**Given** a mission leg with a route and timeline
**And** the TimingSection component is displayed
**When** the user clicks on the departure time input field
**Then** the input should display and accept time in 24-hour format (HH:mm)
**And** helper text should indicate "24-hour format" or show an example "(HH:mm)"
**And** the input should have `step="60"` for 1-minute precision
**And** the time should be labeled as "(UTC)" to indicate timezone

#### Scenario: User enters Ka outage window times

**Given** the Ka outage configuration interface is displayed
**And** the user wants to add a new outage window
**When** the user enters start time and end time
**Then** both inputs should display and accept time in 24-hour format (HH:mm)
**And** helper text should clarify the expected format
**And** both inputs should have `step="60"` for 1-minute precision
**And** validation should accept 24-hour format values (00:00 to 23:59)

#### Scenario: User enters Ku outage window times

**Given** the Ku outage configuration interface is displayed
**And** the user wants to add a new outage window
**When** the user enters start time and end time
**Then** both inputs should display and accept time in 24-hour format (HH:mm)
**And** helper text should clarify the expected format
**And** both inputs should have `step="60"` for 1-minute precision
**And** validation should accept 24-hour format values (00:00 to 23:59)

### Requirement: Time displays use consistent 24-hour format

All time displays throughout the mission planner frontend SHALL use a consistent 24-hour format pattern to eliminate ambiguity and provide a uniform user experience.

#### Scenario: Display outage window times in tables

**Given** Ka or Ku outage windows have been configured
**When** the outage windows are displayed in the table
**Then** the start time should be formatted in 24-hour format as "YYYY-MM-DD HH:mm:ss" or "YYYY-MM-DD HH:mm"
**And** the end time should use the same 24-hour format pattern
**And** no AM/PM indicators should be shown

#### Scenario: Display route timing information on map

**Given** a route with timeline segments is displayed on the map
**When** the user hovers over a route segment or POI
**Then** the tooltip should display time in 24-hour format as "YYYY-MM-DD HH:mm:ss"
**And** no AM/PM indicators should be shown
**And** the format should be consistent across all map tooltips

#### Scenario: Display leg timing in TimingSection

**Given** a mission leg with calculated timeline
**When** the TimingSection displays departure and arrival times
**Then** both times should be formatted in 24-hour format as "YYYY-MM-DD HH:mm:ssZ"
**And** the timezone (UTC) should be clearly indicated
**And** the format should match all other time displays in the application

### Requirement: Utility functions provide consistent time formatting

The application SHALL provide reusable utility functions for consistent 24-hour time formatting across the application, reducing code duplication and ensuring uniform output.

#### Scenario: Format ISO 8601 datetime to 24-hour display format

**Given** an ISO 8601 datetime string (e.g., "2025-01-07T14:30:00Z")
**When** the `formatTime24Hour()` utility function is called
**Then** it should return a formatted string in 24-hour format
**And** the format should be "YYYY-MM-DD HH:mm:ss" or "YYYY-MM-DD HH:mm"
**And** the function should handle UTC timezone properly
**And** the function should gracefully handle invalid or empty inputs

#### Scenario: Replace legacy toLocaleString calls with explicit 24-hour formatting

**Given** legacy code using `toLocaleString()` without explicit locale options
**When** the code is updated to use explicit 24-hour formatting
**Then** the output format should be deterministic and consistent
**And** the format should not depend on browser locale settings
**And** all instances across the codebase should use the same approach

## Implementation Notes

### Browser Compatibility

The HTML5 `datetime-local` input type does not provide a standard mechanism to force 24-hour format across all browsers. The displayed format is determined by:

1. Browser locale settings
2. Operating system locale settings
3. User preferences

**Recommended Approach:**
- Add `step="60"` attribute to enforce minute precision
- Provide clear helper text indicating 24-hour format expected
- Use explicit locale options for all display formatting: `toLocaleString('en-CA', { hour12: false, ... })`
- Consider custom time picker component in future if inconsistency is problematic

### Locale Choice for Formatting

Use `'en-CA'` locale for consistent 24-hour formatting:
```typescript
new Date(isoString).toLocaleString('en-CA', {
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hour12: false,
  timeZone: 'UTC'
});
```

This ensures consistent output regardless of user's browser locale.

### Testing Considerations

Manual testing required across browsers:
- Chrome (Windows, macOS, Linux)
- Firefox (Windows, macOS, Linux)
- Safari (macOS)
- Edge (Windows)

Verify that:
1. Input fields accept times in 24-hour format
2. Displays show times in 24-hour format
3. Validation logic works correctly
4. Backend receives correct ISO 8601 format

## Related Capabilities

- **leg-time-adjustment** - Uses time inputs for departure time adjustment
- **mission-export** - Exports time data; should use consistent 24-hour format

## Dependencies

None - this is a frontend-only change.

## Success Metrics

1. All time inputs consistently use 24-hour format across all supported browsers
2. All time displays consistently use 24-hour format pattern
3. No user reports of time format confusion or AM/PM ambiguity
4. Zero regression in time validation or data submission functionality
