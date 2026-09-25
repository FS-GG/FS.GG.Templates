namespace FS.GG.Templates.SvgWorkspaceArchive

open System
open System.IO
open System.Runtime.InteropServices
open Microsoft.Win32.SafeHandles

type internal PinnedFile = { Bytes: byte[]; Mode: int }

/// Linux-only read capture. Every relative component is opened from its
/// already-open parent; no path check is used as authority for the read.
/// A captured inode may be renamed after opening, and absent destinations
/// have no file handle. These observations cannot authorize later path writes.
module internal LinuxPinnedReceiver =
    [<Literal>]
    let private noFollow = 0o400000
    [<Literal>]
    let private directory = 0o200000
    [<Literal>]
    let private closeOnExec = 0o2000000
    [<Literal>]
    let private nonBlock = 0o4000
    [<Literal>]
    let private emptyPath = 0x1000
    [<Literal>]
    let private typeAndMode = 0x3u
    let private maxReceiverBytes = 8_000_000L

    [<DllImport("libc", EntryPoint = "open", SetLastError = true, CharSet = CharSet.Ansi)>]
    extern int private openPath(string path, int flags)

    [<DllImport("libc", EntryPoint = "openat", SetLastError = true, CharSet = CharSet.Ansi)>]
    extern int private openAt(int directoryFd, string path, int flags)

    [<DllImport("libc", EntryPoint = "statx", SetLastError = true, CharSet = CharSet.Ansi)>]
    extern int private statx(int fd, string path, int flags, uint32 mask, nativeint buffer)

    let private fail label = raise (InvalidDataException label)
    let private number (fd: SafeFileHandle) = fd.DangerousGetHandle().ToInt32()
    let private handle raw = new SafeFileHandle(nativeint raw, true)
    let private errno () = Marshal.GetLastPInvokeError()

    let private checkedMode (fd: SafeFileHandle) =
        // linux/stat.h fixes stx_mode at byte 28 in the 256-byte statx ABI.
        let buffer = Marshal.AllocHGlobal 256
        try
            for offset in 0 .. 255 do Marshal.WriteByte(buffer, offset, 0uy)
            if statx(number fd, "", emptyPath, typeAndMode, buffer) <> 0 then fail "receiver-statx-unavailable"
            if Marshal.ReadInt32(buffer, 0) &&& int typeAndMode <> int typeAndMode then
                fail "receiver-statx-mode-unavailable"
            int (uint16 (Marshal.ReadInt16(buffer, 28)))
        finally
            Marshal.FreeHGlobal buffer

    let private validRelative (relative: string) =
        not (String.IsNullOrEmpty relative)
        && not (relative.StartsWith "/")
        && not (relative.Contains '\\' || relative.Contains ':' || relative.Contains(char 0))
        && (relative.Split '/' |> Array.forall (fun part -> part <> "" && part <> "." && part <> ".."))

    let openRoot (path: string) =
        if not (OperatingSystem.IsLinux()) then fail "physical-receiver-unsupported"
        if not (Path.IsPathFullyQualified path) then fail "workspace-root-unsafe"
        let flags = directory ||| noFollow ||| closeOnExec
        let raw = openPath("/", flags)
        if raw < 0 then fail "workspace-root-unsafe"
        let mutable fd = handle raw
        try
            for part in path.Split('/', StringSplitOptions.RemoveEmptyEntries) do
                let next = openAt(number fd, part, flags)
                if next < 0 then fail "workspace-root-unsafe"
                let child = handle next
                fd.Dispose()
                fd <- child
            if checkedMode fd &&& 0o170000 <> 0o040000 then fail "workspace-root-unsafe"
            fd
        with _ ->
            fd.Dispose()
            reraise()

    let solutionNames (root: SafeFileHandle) =
        // /proc/self/fd refers to the pinned directory, including after rename.
        let directoryPath = $"/proc/self/fd/{number root}"
        Directory.GetFiles(directoryPath, "*.slnx", SearchOption.TopDirectoryOnly)
        |> Array.map Path.GetFileName

    let capture (root: SafeFileHandle) (relative: string)
                (beforeFinalOpen: string -> unit) (afterFinalOpen: string -> unit) =
        if not (validRelative relative) then fail $"output-path-unsafe:{relative}"
        let parts = relative.Split '/'
        let rec walk (parent: SafeFileHandle) index =
            let name = parts[index]
            if index < parts.Length - 1 then
                let raw = openAt(number parent, name, directory ||| noFollow ||| closeOnExec)
                if raw < 0 then
                    match errno () with
                    | 2 -> None // Missing parent; destination is absent.
                    | 20 | 40 -> fail $"output-symlink-or-parent-unsafe:{relative}"
                    | _ -> fail $"output-open-failed:{relative}"
                else
                    use child = handle raw
                    if checkedMode child &&& 0o170000 <> 0o040000 then
                        fail $"output-symlink-or-parent-unsafe:{relative}"
                    walk child (index + 1)
            else
                beforeFinalOpen relative
                let raw = openAt(number parent, name, noFollow ||| nonBlock ||| closeOnExec)
                if raw < 0 then
                    match errno () with
                    | 2 -> None
                    | 20 | 40 -> fail $"output-symlink-or-parent-unsafe:{relative}"
                    | _ -> fail $"output-open-failed:{relative}"
                else
                    use fd = handle raw
                    afterFinalOpen relative
                    let mode = checkedMode fd
                    if mode &&& 0o170000 <> 0o100000 then fail $"output-nonregular:{relative}"
                    use stream = new FileStream(fd, FileAccess.Read)
                    use output = new MemoryStream()
                    let buffer = Array.zeroCreate<byte> 8192
                    let mutable count = stream.Read(buffer, 0, buffer.Length)
                    while count > 0 do
                        if output.Length + int64 count > maxReceiverBytes then fail $"output-too-large:{relative}"
                        output.Write(buffer, 0, count)
                        count <- stream.Read(buffer, 0, buffer.Length)
                    Some { Bytes = output.ToArray(); Mode = mode &&& 0o7777 }
        walk root 0
