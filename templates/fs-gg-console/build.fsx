open System
open System.Diagnostics

let run (file: string) (arguments: string) =
    let startInfo = ProcessStartInfo(file, arguments)
    startInfo.UseShellExecute <- false
    use child = Process.Start(startInfo)
    child.WaitForExit()
    if child.ExitCode <> 0 then failwith $"{file} {arguments} exited {child.ExitCode}"

match fsi.CommandLineArgs |> Array.skip 1 |> Array.toList with
| [ "build" ] ->
    run "dotnet" "restore ConsoleProduct.slnx --locked-mode"
    run "dotnet" "build ConsoleProduct.slnx --no-restore"
| [ "test" ] -> run "dotnet" "run --project tests/ConsoleProduct.Tests --no-build"
| _ -> failwith "usage: dotnet fsi build.fsx [build|test]"
