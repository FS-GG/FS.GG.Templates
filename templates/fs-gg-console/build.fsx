open System
open System.Diagnostics

let run file arguments =
    use process = Process.Start(ProcessStartInfo(file, arguments, UseShellExecute = false))
    process.WaitForExit()
    if process.ExitCode <> 0 then failwith $"{file} {arguments} exited {process.ExitCode}"

match fsi.CommandLineArgs |> Array.skip 1 |> Array.toList with
| [ "build" ] -> run "dotnet" "build ConsoleProduct.slnx --locked-mode"
| [ "test" ] -> run "dotnet" "run --project tests/ConsoleProduct.Tests --no-build"
| _ -> failwith "usage: dotnet fsi build.fsx [build|test]"
