open System
open System.Globalization
open System.IO
open FS.GG.Coordination.Orchestration.Execution

let options = fsi.CommandLineArgs |> Array.skip 1 |> Array.chunkBySize 2 |> Array.map (function | [|k;v|] when k.StartsWith("--") -> k[2..],v | _ -> invalidArg "args" "use --name value") |> Map.ofArray
let need name = options |> Map.tryFind name |> Option.defaultWith (fun () -> invalidArg name "missing")
let kind=need "kind"
if kind<>"rust" && kind<>"go" then invalidArg "kind" "rust or go required"
let deadline =
    match DateTimeOffset.TryParseExact(need "deadline","yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'",CultureInfo.InvariantCulture,DateTimeStyles.AssumeUniversal ||| DateTimeStyles.AdjustToUniversal) with
    | true,value when value.Offset=TimeSpan.Zero && value.Ticks%10L=0L -> value
    | _ -> invalidArg "deadline" "exact UTC timestamp with six fractional digits required"
let componentId=if kind="rust" then "rust-tic-tac-toe" else "go-snake"
let scope="fs-gg/templates/language-route/"+kind
let command={CommandId=Guid.ParseExact(need "command-id","D");IdempotencyId=need "idempotency-id";WorkspaceScope=scope;ProfileId="language-route-"+kind+"-v1";ProfileRevision=1UL;SourceRevision=need "source-revision";ExpectedWorkflowRevision=1UL;FenceGeneration=1UL;CausationId=None;Deadline=deadline;Operation="test";ComponentId=Some componentId}
let bytes=PortableWorkspaceContract.commandBytes command |> Result.defaultWith invalidOp
let decoded=PortableWorkspaceContract.parseCommand bytes |> Result.defaultWith invalidOp
let roundtrip=PortableWorkspaceContract.commandBytes decoded |> Result.defaultWith invalidOp
if not(roundtrip.AsSpan().SequenceEqual(bytes.AsSpan())) then invalidOp "portable-command-codec-roundtrip-refused"
let output=need "output" |> Path.GetFullPath
let stream=new FileStream(output,FileMode.CreateNew,FileAccess.Write,FileShare.None)
stream.Write bytes
stream.Flush true
stream.Dispose()
if not (OperatingSystem.IsWindows()) then File.SetUnixFileMode(output,UnixFileMode.UserRead ||| UnixFileMode.UserWrite)
