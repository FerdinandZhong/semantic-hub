# Visual and interaction design

The workspace follows the user-provided UOB governance reference.
Use a pale application shell, UOB navy/red branding, blue navigation and compact white panels.
Keep the existing data preparation and query workflows visible and usable.

## Tokens

Use variables in [styles.css](demo/static/styles.css).

| Role | Value |
| --- | --- |
| Shell background | `#f7f8fc` |
| Heading/navy | `#152c65` |
| Main text | `#292f3d` |
| Secondary text | `#667085` |
| Borders | `#e9edf4` |
| Primary action/navigation | `#2d62df` |
| Blue surface | `#edf3ff` |
| UOB mark | `#e42932` |
| Success | `#13866d` |
| Warning | `#98691b` |

Use the system sans-serif stack and 10 px panel corners.
Reserve red for the brand mark. Use blue for actions, links and selected navigation.
Use white surfaces with subtle borders; avoid decorative shadows outside dialogs and search results.

## Layout

The left rail contains UOB branding and Prepare/Explore navigation groups.
The top bar contains a local page finder, Models, Access settings and shared-workspace context.
A compact breadcrumb sits above the page heading.
Query pages show source context cards, the question/results panel and an execution-evidence panel.
Preparation pages use the same forms, tables, notices and panel spacing.
The reference's classifications and certification controls are not added as unsupported demo features.

```text
UOB navigation | Page finder + shared workspace actions
               | Breadcrumb + compact page heading
               | Source context / preparation controls
               | Main evidence panel | execution context
```

## Typography and components

Use 25 px desktop page headings, 13 px section headings and 12–13 px content text.
Use consistent inline stroke SVGs for navigation.
Keep control heights at least 35 px on desktop and primary mobile actions at least 40 px.
Use blue sample notices and preserve explicit synthetic labels.
Keep tables compact with pale headers, light row separators and subtle hover backgrounds.
Technical names should remain readable; tables scroll within their containers at narrow widths.

## Responsive behavior

Use breakpoints at 1250, 980 and 700 px.
The desktop rail is 205 px wide, reducing to 190 px on smaller desktops.
On mobile, navigation wraps into a three-column grid above the header.
The page finder fills the mobile header width; shared actions wrap below it.
Forms become one column. Evidence panels stack below the query panel.
Dialogs use internal scrolling and stay inside the viewport.
Preserve readable content at 390 px without horizontal page overflow.

## Interaction and verification

The page finder searches existing workspace pages only, using local browser code.
It supports mouse selection, arrow keys, Enter, Escape and Cmd/Ctrl+K.
Do not present dataset search, administrator roles or domain filtering that the app does not implement.
Keep visible keyboard focus, associated form labels and native dialog semantics.
Preserve sample/live separation, failure visibility and escaped rendering of external content.
Saving, validating, publishing and activating remain separate preparation actions.
Update stylesheet versions and screenshots after UI changes.

Run the three browser checks against an isolated server.
Check all five pages, configuration dialogs, page finder, mobile overflow and JavaScript errors.

## Sources connection controls

Align preparation mode and the connection button along their bottom edges.
Keep their heights equal on desktop and mobile.
Show the lakehouse connection form directly on Sources.
Show saved, unverified, verified, unavailable and unsaved states separately.
Keep live discovery an explicit choice beside the offline sample.

## Observability context review

Keep the review table inside the existing Observability preparation panel.
Use compact rows, a filter toolbar and an explicit selection count.
Use human-readable dashboard/panel titles with technical identifiers available in details.
Selection, release inclusion and reviewed status are independent states.
Distinguish selection on the current page from selection across all matching results.
Retain selections across filters/pages and show how many selected rows are hidden.
Use contextual bulk actions and a native dialog for explicit group review.
A right-aligned native dialog edits one definition; mobile dialogs remain inside the viewport.
Keep discovered metadata immutable and render external descriptions as text.
Mark source metadata, AI suggestions, existing drafts and edited meanings separately.
Saving draft progress, publication and activation remain distinct actions.

## Metric definition evidence

Observability results show an expanded **Metric definitions and log fields** disclosure.
Compact text cards show meaning, units, labels, aggregation rules, limits and origin.
Use existing border tokens and wrap long technical names within the result panel.
Render descriptions as text; never interpret source descriptions as HTML.
The panel displays at most 14 definitions and states when additional definitions remain in the response.

## Banking retrieval evidence

Data Understanding results show **Retrieved semantic definitions** in the existing answer panel.
Display selected names, lexical scores, dataset/field counts, context size and release/policy identity.
Wrap long hashes and technical names within the panel.
Banking clarification guidance asks for a business definition rather than log timestamp controls.
The server enforces analyst restrictions; this increment does not add a separate analyst navigation layout.
