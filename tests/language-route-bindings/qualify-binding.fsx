#load "../../eng/language-route-bindings/BindingSupport.fsx"

open System
open System.IO
open System.Text
open System.Text.Json
open System.Threading
open System.Threading.Tasks
open FS.GG.Coordination.Orchestration.Execution
open BindingSupport.LanguageRouteBindingSupport

let policyPath=Path.GetFullPath fsi.CommandLineArgs[1]
let root=JsonDocument.Parse(File.ReadAllBytes policyPath).RootElement
let unalignedNow=DateTimeOffset(2098,1,1,0,0,0,TimeSpan.Zero).AddTicks 7L
let fixedNow=portableNowFrom unalignedNow
if fixedNow.Ticks%10L<>0L || fixedNow.Ticks=unalignedNow.Ticks then failwith "portable clock was not normalized"
for kind in ["rust";"go"] do
    let trustedImage=root.GetProperty("qualifiedImages").GetProperty(kind)
    let boundJson=sprintf """{"archiveSha256":"%s","configDigest":"%s","imageId":"%s","manifestDigest":"%s"}""" (trustedImage.GetProperty("archiveSha256").GetString()) (trustedImage.GetProperty("configDigest").GetString()) (trustedImage.GetProperty("configDigest").GetString()) (trustedImage.GetProperty("retainedOciManifestDigest").GetString())
    let bound=JsonDocument.Parse(boundJson).RootElement
    if qualifiedImageReference trustedImage bound<>trustedImage.GetProperty("qualifiedReference").GetString() then failwith "trusted image was not selected"
    let tampered=JsonDocument.Parse(boundJson.Replace(trustedImage.GetProperty("retainedOciManifestDigest").GetString(),"sha256:"+String.replicate 64 "0")).RootElement
    try
        qualifiedImageReference trustedImage tampered |> ignore
        failwith "caller-controlled manifest was accepted"
    with
    | :? InvalidOperationException as ex when ex.Message="binding-qualified-image-mismatch" -> ()
let sourceRevision="66ce4faacc122ef4a2d2331a0c10fe388e7c3b69"

let observation output terminated =
    { ExecutionStarted=true;ExitCode=(if terminated then Some 0 else None);StandardOutput=Array.empty;StandardError=Array.empty;CancellationRequested=false;TerminationObserved=terminated;Interrupted=not terminated;OutputLimitExceeded=false;OutputComplete=terminated;SourceTree=Some(String.replicate 40 "b");SnapshotSha256=Some(String.replicate 64 "c");RuntimeIdentity=Some "podman-test";ContainerIdentity=Some "closed-runner";VerificationObserved=terminated;VerificationOutput=(if terminated then Some output else None);VerificationCustodyLimitExceeded=false;Refusal=None }

type ClosedRunner(output:byte array, firstTerminates:bool) =
    let mutable runs=0
    member _.Runs=runs
    interface IPortableProcessRunner with
        member _.RunAsync(_,_) = runs<-runs+1;Task.FromResult(observation output firstTerminates)
        member _.RecoverAsync(_,_) = Task.FromResult(observation output true)
        member _.CleanupAsync(_,_) = Task.FromResult true

let qualify kind =
    let opId=if kind="rust" then "rust-tic-tac-toe-journey" else "go-snake-journey"
    let componentId=if kind="rust" then "rust-tic-tac-toe" else "go-snake"
    let toolchainId,version=if kind="rust" then "rust","1.98.1" else "go","1.27.1"
    let op=root.GetProperty("operations").GetProperty(opId)
    let working=op.GetProperty("workingDirectory").GetString()
    let wrapper=op.GetProperty("arguments").EnumerateArray() |> Seq.head |> fun value->value.GetString()
    let verification=if kind="rust" then "{\"journey\":\"rust-tic-tac-toe\",\"schema\":\"fsgg.language-route.rust-tic-tac-toe/1\",\"toolchain\":\"1.98.1\"}\n" else "{\"journey\":\"go-snake\",\"schema\":\"fsgg.language-route.go-snake/1\",\"toolchain\":\"1.27.1\"}\n"
    let output=Encoding.UTF8.GetBytes verification
    let image="localhost/fsgg-language-route@sha256:"+(if kind="rust" then "26f02aa5ca5b0ba3316603402e314c9b568d1c318c98cedb2d052798fe043c34" else "a0d59ccedc4f09c9517ecf8d72677f62795a75286e0787e3d0710622a7a57319")
    let scope="fs-gg/templates/language-route/"+kind
    let part={Id=componentId;Language=kind;WorkingDirectory=working;Toolchain={Id=toolchainId;Version=version};EntryPoints={Build=opId;Test=opId;Lint=None;Artifact=None}}
    let rawProfile={ProfileId="language-route-"+kind+"-v1";Revision=1UL;WorkspaceScope=scope;SourceRevision=sourceRevision;QualifiedImage=image;Components=[part];ProductBuild=opId;ProductTest=opId;ProductJourney=opId;MaximumRuntimeSeconds=120UL;MaximumOutputBytes=262144UL}
    let profileBytes=PortableWorkspaceContract.profileBytes rawProfile |> Result.defaultWith invalidOp
    let profile=PortableWorkspaceContract.parseProfile profileBytes |> Result.defaultWith invalidOp
    let command={CommandId=Guid.Parse(if kind="rust" then "10000000-0000-0000-0000-000000000001" else "20000000-0000-0000-0000-000000000001");IdempotencyId="source-proof-"+kind;WorkspaceScope=scope;ProfileId=profile.ProfileId;ProfileRevision=1UL;SourceRevision=sourceRevision;ExpectedWorkflowRevision=1UL;FenceGeneration=1UL;CausationId=None;Deadline=DateTimeOffset(2099,1,1,0,0,0,123,456,TimeSpan.Zero);Operation="test";ComponentId=Some componentId}
    let commandBytes=PortableWorkspaceContract.commandBytes command |> Result.defaultWith invalidOp
    let command=PortableWorkspaceContract.parseCommand commandBytes |> Result.defaultWith invalidOp
    let reviewed={EntryPoint=opId;OperationIdentity="test";ComponentId=Some componentId;WorkingDirectory=working;QualifiedImage=image;RequiredToolchains=[(toolchainId,version)];Executable="/bin/sh";Arguments=[wrapper];VerificationIdentity=op.GetProperty("verificationIdentity").GetString();VerificationPath=op.GetProperty("verificationPath").GetString();VerificationSha256=op.GetProperty("verificationSha256").GetString();RecipeSha256=op.GetProperty("recipeSha256").GetString()}
    let state=Path.Combine(Path.GetTempPath(),"fsgg-language-binding-"+Guid.NewGuid().ToString("N"))
    Directory.CreateDirectory state|>ignore
    let runtime={GitExecutable="/usr/bin/git";TarExecutable="/usr/bin/tar";PodmanExecutable="/usr/bin/podman";PodmanGlobalArguments=[];StateRoot=state;ContainerPath="/usr/local/bin:/usr/bin:/bin";ContainerUser="32768:32768";HostEnvironment=Map["HOME",state;"PATH","/usr/bin:/bin"];ContainerEnvironment=Map["HOME","/output/home";"PATH","/usr/local/bin:/usr/bin:/bin"];MaximumSnapshotBytes=1024UL;TerminationGrace=TimeSpan.FromSeconds 1.}
    let policy={WorkspaceRoot=Path.GetFullPath ".";WorkspaceScope=scope;SourceRevision=sourceRevision;QualifiedImage=image;MaximumRuntimeSeconds=120UL;MaximumOutputBytes=262144UL;Operations=[reviewed];Runtime=runtime}
    let authority={WorkspaceScope=scope;WorkflowRevision=1UL;FenceGeneration=1UL;ObservedAt=fixedNow}
    let refusedRunner=ClosedRunner(output,true)
    let refusedPolicy={policy with Operations=[{reviewed with OperationIdentity="journey"}]}
    match PortableWorkspaceExecutor.Executor(refusedPolicy,refusedRunner,(fun()->fixedNow)).ExecuteAsync(authority,profile,command,CancellationToken.None).Result with | Refused "portable-executor-operation-refused" -> () | other -> failwithf "%s invalid operation was admitted: %A" kind other
    if refusedRunner.Runs<>0 then failwithf "%s invalid operation launched" kind
    let runner=ClosedRunner(output,true)
    let first=PortableWorkspaceExecutor.Executor(policy,runner,(fun()->fixedNow)).ExecuteAsync(authority,profile,command,CancellationToken.None).Result
    match first with | Completed receipt when receipt.Result.Error.IsNone && receipt.CleanupCompleted -> () | other -> failwithf "%s first launch refused: %A" kind other
    let reconstructed=PortableWorkspaceExecutor.Executor(policy,runner,(fun()->fixedNow))
    match reconstructed.ExecuteAsync(authority,profile,command,CancellationToken.None).Result with | Duplicate receipt when receipt.Result.Error.IsNone -> () | other -> failwithf "%s duplicate failed: %A" kind other
    match reconstructed.RecoverAsync(profile,command,CancellationToken.None).Result with | Duplicate _ -> () | other -> failwithf "%s settled recovery failed: %A" kind other
    if runner.Runs<>1 then failwithf "%s duplicate relaunched" kind
    let changedCommand={command with Deadline=command.Deadline.AddSeconds 1.}
    match reconstructed.ExecuteAsync(authority,profile,changedCommand,CancellationToken.None).Result with | Refused "portable-executor-idempotency-conflict" -> () | other -> failwithf "%s changed command was not fenced: %A" kind other
    if runner.Runs<>1 then failwithf "%s changed command launched" kind
    Directory.Delete(state,true)
    if kind="rust" then
        let recoveryState=state+"-recovery"
        let recoveryRuntime={runtime with StateRoot=recoveryState}
        let recoveryPolicy={policy with Runtime=recoveryRuntime}
        let interrupted=ClosedRunner(output,false)
        let original=PortableWorkspaceExecutor.Executor(recoveryPolicy,interrupted,(fun()->fixedNow))
        match original.ExecuteAsync(authority,profile,command,CancellationToken.None).Result with | Completed receipt when not receipt.TerminationObserved -> () | other -> failwithf "interrupted launch was not retained: %A" other
        let recovered=PortableWorkspaceExecutor.Executor(recoveryPolicy,interrupted,(fun()->fixedNow))
        match recovered.RecoverAsync(profile,command,CancellationToken.None).Result with | Completed receipt when receipt.Result.Error.IsNone && receipt.CleanupCompleted -> () | other -> failwithf "interrupted reconstruction failed: %A" other
        if interrupted.Runs<>1 then failwith "recovery relaunched"
        Directory.Delete(recoveryState,true)

qualify "rust"
qualify "go"
printfn "{\"codecAndBindingPassed\":true,\"nativeExecutionAccepted\":false,\"operations\":2}"
