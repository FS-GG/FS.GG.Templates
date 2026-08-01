module ConsoleProductNamespace.Program

open System
open System.Threading
open System.Threading.Tasks

type ConsolePorts =
    { WriteOut: string -> unit
      WriteError: string -> unit }

let private defaultPorts =
    { WriteOut = Console.Out.WriteLine
      WriteError = Console.Error.WriteLine }

let run (ports: ConsolePorts) (cancellationToken: CancellationToken) (arguments: string array) =
    task {
        if cancellationToken.IsCancellationRequested then
            ports.WriteError "cancelled"
            return 130
        elif arguments = [| "--fail" |] then
            ports.WriteError "requested failure"
            return 1
        elif arguments = [| "--wait" |] then
            try
                do! Task.Delay(Timeout.InfiniteTimeSpan, cancellationToken)
                return 0
            with :? OperationCanceledException ->
                ports.WriteError "cancelled"
                return 130
        else
            ports.WriteOut (String.concat " " arguments)
            return 0
    }

[<EntryPoint>]
let main arguments =
    use cancellation = new CancellationTokenSource()
    Console.CancelKeyPress.Add(fun eventArgs ->
        eventArgs.Cancel <- true
        cancellation.Cancel())
    run defaultPorts cancellation.Token arguments
    |> Async.AwaitTask
    |> Async.RunSynchronously
