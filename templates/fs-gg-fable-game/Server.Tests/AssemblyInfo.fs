module FableGameWorkspaceNamespace.Server.Tests.AssemblyInfo

// `RoomAuthority` (see ../Server/RoomAuthority.fs) is deliberately process-wide static
// state, shared by every `WebApplicationFactory` host created in this test process.
// xUnit runs different test classes as separate collections *in parallel* by default,
// which would let two test classes race on that shared state even though each resets it
// on construction. Disabling parallelization here keeps the test suite deterministic
// without adding per-room scoping this minimal template does not otherwise need.
[<assembly: Xunit.CollectionBehavior(DisableTestParallelization = true)>]
do ()
