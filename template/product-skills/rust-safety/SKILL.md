---
name: rust-safety
description: Maintain the generated rust safety product contract.
---

Keep forbid(unsafe_code) unless a separately reviewed safety policy explicitly changes it. Review dependencies, FFI and build scripts as executable closure. A zero-dependency crate does not waive the declared advisory policy or toolchain security evidence. Preserve scanner/advisory provenance and fail closed when it is absent.

The executable product operations and declared capability bindings remain authoritative. Skills do not grant publication or runtime admission.
