# Workspace ownership

- Project root: `.` (this file's directory; one owner shared by every agent).
- Active source: `.` until existing CURRENT/version metadata identifies a snapshot.
- Versioning: preserve the established layout; Git tags for Git projects, explicit snapshots only when already appropriate.
- Repository: https://github.com/SenjuWoo/ReSkate-Forge (public, MIT), published at the owner's request on 2026-11-12. Workspaces, Studio binaries and local configuration stay out of it.
- Publication intent: local/private by default. A build or release candidate is not permission to publish.
- Explicit GitHub publication: public and MIT for original work by default, subject to rights/platform terms; preserve existing licences. Generic publication uses the appropriate destination (Nexus for Skyrim); do not create duplicate source hosting for mods needing no compilation.
- Existing-repository maintenance: preserve its remote/visibility and follow the requested update, documentation, push and release scope.
- Read-only inputs: installed products, game Data/staging/saves and supplied references.
- Release staging: separate runtime payload from source, ownership notes, STATE/PLAN/validation, changelogs, logs and backups. Keep required licences.
- Recovery: read STATE.md and version/build/run metadata before continuing; keep the last known-good artifact.


Read the existing evidence and update the active-source/version fields before substantive edits. Do not create another owner or move files merely to match a template.
