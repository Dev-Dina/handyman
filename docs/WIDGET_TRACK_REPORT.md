# Widget Track Report

## 1. Widget requirements checklist

| Requirement | Status |
|---|---|
| Standalone React widget bundle | Planned |
| Loader script served from `/widget.js` | Planned |
| Widget config loaded from database | Planned |
| Shared FastAPI backend | Planned |
| Host demo app | Planned |
| Origin allowlisting | Later |
| CSP `frame-ancestors` policy | Later |
| Bundle-size tracking | Planned |

## 2. React widget architecture

The widget should be a standalone React bundle that can be embedded into a host page through a loader script. It should call the shared FastAPI backend and avoid duplicating chat, memory, or tool logic.

No widget files are created in CHAT-0.

## 3. Loader script plan

The backend should eventually serve `/widget.js`. The loader should read a site/widget identifier, fetch config, mount the React widget, and isolate widget styles from the host page.

## 4. Widget config plan

Widget config should come from the database. Planned config fields include:
- site/widget identifier
- display name
- allowed origins
- theme settings
- enabled tools
- default prompt/options

No schema or migration is created in CHAT-0.

## 5. Allowed origins/CSP plan

Origin allowlisting and CSP `frame-ancestors` should be enforced later. The plan must cover both API calls and embeddability.

## 6. Host app demo plan

A minimal host demo app should show how an external site loads `/widget.js` and initializes the widget. This is planned for a later implementation phase.

## 7. Bundle-size tracking placeholder

Bundle-size budget and reporting are pending. The implementation phase should define a target budget and CI check.

## 8. Open blockers

none

## 9. Next steps

1. Design widget config schema.
2. Decide loader initialization contract.
3. Plan host demo app.
