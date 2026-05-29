"""BridgeTracer source root.

Module layout intentionally splits UI-independent core from UI per the plan:

    src/
        core/         — event schema, recorder, filters, triggers, storage,
                        file refs, auth, schemas. No PySide6 imports.
        bridge_client/— Bearer-auth HTTP + SSE stream client. httpx only.
        ui/           — PySide6 layer. Deferred until final form/layout is
                        approved (see BridgeTracer.md "Important Design Notes").
        app/          — entrypoint.
"""
