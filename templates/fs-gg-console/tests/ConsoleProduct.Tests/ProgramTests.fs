module ConsoleProductNamespace.ProgramTests

open System.Threading
open Expecto
open ConsoleProductNamespace

let run arguments cancelled =
    let output = ResizeArray<string>()
    let errors = ResizeArray<string>()
    use source = new CancellationTokenSource()
    if cancelled then source.Cancel()
    let ports: Program.ConsolePorts = { WriteOut = output.Add; WriteError = errors.Add }
    let exitCode = Program.run ports source.Token arguments |> Async.AwaitTask |> Async.RunSynchronously
    exitCode, List.ofSeq output, List.ofSeq errors

let runWaitThenCancel () =
    let output = ResizeArray<string>()
    let errors = ResizeArray<string>()
    use source = new CancellationTokenSource()
    let ports: Program.ConsolePorts = { WriteOut = output.Add; WriteError = errors.Add }
    let pending = Program.run ports source.Token [| "--wait" |]
    source.Cancel()
    let exitCode = pending |> Async.AwaitTask |> Async.RunSynchronously
    exitCode, List.ofSeq output, List.ofSeq errors

let tests =
    testList "console contract" [
        testCase "arguments are written to stdout" <| fun _ ->
            let code, output, errors = run [| "hello"; "world" |] false
            Expect.equal code 0 "successful arguments exit zero"
            Expect.equal output [ "hello world" ] "stdout is deterministic"
            Expect.isEmpty errors "stderr is empty on success"
        testCase "failure is written to stderr" <| fun _ ->
            let code, output, errors = run [| "--fail" |] false
            Expect.equal code 1 "requested failure exits nonzero"
            Expect.isEmpty output "failure emits no stdout"
            Expect.equal errors [ "requested failure" ] "stderr is deterministic"
        testCase "pre-cancelled work shuts down cleanly" <| fun _ ->
            let code, _, errors = run [| "hello" |] true
            Expect.equal code 130 "cancellation uses conventional exit status"
            Expect.equal errors [ "cancelled" ] "cancellation is observable"
        testCase "waiting work observes cancellation and shuts down" <| fun _ ->
            let code, output, errors = runWaitThenCancel ()
            Expect.equal code 130 "waiting cancellation uses conventional exit status"
            Expect.isEmpty output "waiting cancellation emits no stdout"
            Expect.equal errors [ "cancelled" ] "the wait cancellation path is observable"
    ]

[<EntryPoint>]
let main arguments = runTestsWithCLIArgs [] arguments tests
