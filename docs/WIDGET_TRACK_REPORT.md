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

## 4. Widget config schema (CHAT-1 complete)

Schema implemented in `app/infra/models.py` (`WidgetConfig`) and migrated in `002_chat1_schema.py`:

| Column | Type | Purpose |
|---|---|---|
| `id` | UUID PK | Internal identifier |
| `public_widget_id` | UUID UNIQUE | Public tenant identifier for loader script |
| `owner_user_id` | UUID FK → users | Widget ownership |
| `allowed_origins` | JSONB list | Origin allowlist for CSP/CORS enforcement |
| `theme` | JSONB dict | Display theme overrides |
| `greeting` | Text nullable | Initial greeting message |
| `enabled_tools` | JSONB list | Subset of tools available in this widget |
| `is_active` | Boolean | Enable/disable without deleting |
| `created_at` / `updated_at` | Timestamptz | Audit timestamps |

Domain model: `WidgetConfigDomain` in `app/domain/models.py`.
Domain errors: `WidgetNotFoundError`, `WidgetInactiveError`, `WidgetOriginDeniedError` in `app/domain/widgets.py`.
Repository: `WidgetConfigRepository` with `get_by_public_widget_id` and `list_by_owner`.

## 5. Allowed origins/CSP plan

Origin allowlisting and CSP `frame-ancestors` should be enforced later. The plan must cover both API calls and embeddability.

## 6. Host app demo plan

A minimal host demo app should show how an external site loads `/widget.js` and initializes the widget. This is planned for a later implementation phase.

## 7. Bundle-size tracking placeholder

Bundle-size budget and reporting are pending. The implementation phase should define a target budget and CI check.

## 8. Open blockers

none

## 9. Next steps

1. Implement widget config read API endpoint (WIDGET-1).
2. Decide loader initialization contract and `/widget.js` serving strategy.
3. Plan host demo app.
