open System
open System.IO
open System.Diagnostics

let run (file: string) (arguments: string) =
    let startInfo = ProcessStartInfo(file, arguments)
    startInfo.UseShellExecute <- false
    use child = Process.Start(startInfo)
    child.WaitForExit()
    if child.ExitCode <> 0 then failwith $"{file} {arguments} exited {child.ExitCode}"

/// The lockfiles must have SHIPPED with this workspace (FS.GG.Templates#384).
///
/// `--locked-mode` with no lock file on disk does not fail: NuGet quietly AUTHORS one
/// from whatever the ambient machine resolves, and every later restore then enforces
/// that unreviewed lock. That is not a hypothetical — `dotnet new`'s default source
/// exclude list contains `**/*.lock.json`, and this template additionally committed no
/// lockfiles at all, so for the whole of 0.8.0 every generated console workspace
/// arrived with zero locks and silently invented its own on first restore. The symptom
/// in the sibling fable-game template was `NU1403: Package content hash validation
/// failed`, three steps downstream and nowhere near the cause; this template carried
/// the same defect and merely had not been observed to red.
///
/// So assert presence BEFORE restoring. A missing lock here means the template stopped
/// delivering it, and the correct outcome is a loud red at the boundary that owns the
/// guarantee — not a restore that succeeds by inventing the thing it was meant to check.
let requireLockFiles () =
    let expected =
        [ Path.Combine("src", "ConsoleProduct", "packages.lock.json")
          Path.Combine("tests", "ConsoleProduct.Tests", "packages.lock.json") ]

    let missing = expected |> List.filter (File.Exists >> not)

    if not missing.IsEmpty then
        eprintfn "build.fsx: refusing to restore — this workspace shipped without NuGet lockfiles:"
        missing |> List.iter (eprintfn "  missing: %s")
        eprintfn "A --locked-mode restore would not fail on this; it would AUTHOR a lock from"
        eprintfn "whatever this machine resolves, which is exactly how FS.GG.Templates#380"
        eprintfn "produced NU1403. Regenerate the template's lockfiles, or repair the template's"
        eprintfn "'sources' exclude list so they reach a generated product."
        exit 1

match fsi.CommandLineArgs |> Array.skip 1 |> Array.toList with
| [ "build" ] ->
    requireLockFiles ()
    run "dotnet" "restore ConsoleProduct.slnx --locked-mode"
    run "dotnet" "build ConsoleProduct.slnx --no-restore"
| [ "test" ] -> run "dotnet" "run --project tests/ConsoleProduct.Tests --no-build"
| _ -> failwith "usage: dotnet fsi build.fsx [build|test]"
