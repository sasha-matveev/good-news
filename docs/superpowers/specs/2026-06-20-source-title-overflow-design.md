# Source title overflow fix

## Problem

On the Sources page, a source with a long display name expands the title area and pushes the action buttons outside the visible card and viewport. The heading already requests ellipsis rendering, but its flex ancestors do not give it a constrained width to truncate against.

## Accepted behavior

- A long source title is truncated with an ellipsis instead of widening the card.
- The source action buttons remain visible and do not shrink.
- The page does not gain horizontal scrolling because of a long source title or URL.
- Short source titles retain their current appearance.
- The behavior is covered by a focused regression test.

## Design

Keep the change local to the source-card header. Make the left-hand identity area consume only the space remaining after the action group, allow its nested text container to shrink, and hide overflow within that area. Render the source URL as a block constrained to the same available width and truncate it with an ellipsis as well. Keep the action group non-shrinking.

Do not change the application shell grid or wrap the action buttons onto another row; both would broaden the scope or alter the established card layout.

## Verification

Add a Sources page test that renders an exceptionally long display name and URL and verifies the layout contract exposed by the relevant style rules. Run the focused Sources page test, the frontend test suite, and the frontend production build. Finally, inspect the page at a constrained viewport to confirm that the actions remain visible and no horizontal page overflow appears.
