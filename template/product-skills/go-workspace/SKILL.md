---
name: go-workspace
description: Maintain the generated go workspace product contract.
---

Supply an explicit module path; do not infer it from a display name or F# identifier. Keep GOTOOLCHAIN=local and GOWORK=off so the selected compiler cannot download a replacement or inherit a parent workspace. Review go.mod and any real go.sum together; a stdlib-only product has no fabricated dependency lock.

The executable product operations and declared capability bindings remain authoritative. Skills do not grant publication or runtime admission.
