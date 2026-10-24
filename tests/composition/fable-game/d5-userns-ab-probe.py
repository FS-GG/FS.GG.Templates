#!/usr/bin/env python3
"""Hosted-runner A/B probe for the D5 user-namespace prerequisite (FS-GG/.github#4849).

Observation only. It never changes a sysctl, a profile, NNP or a namespace flag; the
single permitted host change (arm B) is a separate reviewed workflow step. Each
subcommand writes one bounded JSON document and always exits 0 so the workflow can
retain failures as data. Never run this on Home or self-hosted machines.

  snapshot LABEL OUT       kernel/AppArmor/userns state (before/after the arm step)
  probe FORM OUT           literal unshare argv plus a post-CLONE uid_map write
  kernlog SINCE_EPOCH OUT  readable kernel/audit lines (AppArmor, userns, DENIED)
"""
import json
import os
import re
import subprocess
import sys
import time

SYSCTLS = (
    "/proc/sys/kernel/apparmor_restrict_unprivileged_userns",
    "/proc/sys/kernel/apparmor_restrict_unprivileged_unconfined",
    "/proc/sys/kernel/unprivileged_userns_clone",
    "/proc/sys/user/max_user_namespaces",
    "/proc/sys/kernel/dmesg_restrict",
    "/proc/sys/kernel/yama/ptrace_scope",
    "/proc/sys/fs/suid_dumpable",
)
UNSHARE_ARGV = ["/usr/bin/unshare", "--user", "--map-root-user", "--net", "--", "/usr/bin/true"]
CAP = 16384


def read(path, limit=CAP):
    try:
        with open(path, "rb") as stream:
            return {"status": "observed", "value": stream.read(limit).decode("utf-8", "replace").strip()}
    except OSError as error:
        return {"status": "Unknown", "errno": error.errno, "reason": f"{type(error).__name__}: {error}"[:256]}


def status_fields(text):
    keep = ("Uid", "Gid", "CapInh", "CapPrm", "CapEff", "CapBnd", "CapAmb", "NoNewPrivs", "Seccomp")
    return {key: value.strip() for line in text.splitlines() if ":" in line
            for key, value in [line.split(":", 1)] if key in keep}


def process_state():
    status = read("/proc/self/status")
    return {
        "status": status_fields(status.get("value", "")),
        "attrCurrent": read("/proc/self/attr/current"),
        "cgroup": read("/proc/self/cgroup"),
        "userNamespace": os.readlink("/proc/self/ns/user"),
        "uid": list(os.getresuid()),
    }


def command(argv, timeout=20, env=None, limit=CAP):
    try:
        result = subprocess.run(argv, capture_output=True, timeout=timeout, env=env, check=False)
        return {"argv": argv, "exit": result.returncode,
                "stdout": result.stdout.decode("utf-8", "replace")[:limit],
                "stderr": result.stderr.decode("utf-8", "replace")[:CAP]}
    except Exception as error:  # observation must not abort the arm
        return {"argv": argv, "exit": None, "reason": f"{type(error).__name__}: {error}"[:512]}


def write_json(path, value):
    data = json.dumps(value, indent=2, sort_keys=True) + "\n"
    if len(data.encode()) > 1048576:
        raise ValueError("metadata cap exceeded")
    with open(path, "w", encoding="utf-8") as stream:
        stream.write(data)


def snapshot(label, out):
    value = {
        "schema": "fsgg.d5.userns-ab.snapshot/1", "label": label,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sysctl": {path: read(path) for path in SYSCTLS},
        "lsm": read("/sys/kernel/security/lsm"),
        "apparmorEnabled": read("/sys/module/apparmor/parameters/enabled"),
        "process": process_state(),
        "aaStatus": command(["sudo", "-n", "aa-status"]),
        "unshareVersion": command(["/usr/bin/unshare", "--version"]),
    }
    write_json(out, value)


def clone_probe():
    """Post-CLONE state: unshare(CLONE_NEWUSER) in a child, then write its uid_map."""
    reader, writer = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(reader)
        report = {}
        try:
            uid = os.geteuid()
            os.unshare(os.CLONE_NEWUSER)
            report["unshare"] = "ok"
            status = read("/proc/self/status")
            report["postCloneStatus"] = status_fields(status.get("value", ""))
            report["postCloneAttrCurrent"] = read("/proc/self/attr/current")
            for name, text in (("setgroups", "deny"), ("uid_map", f"0 {uid} 1")):
                try:
                    with open(f"/proc/self/{name}", "w") as stream:
                        stream.write(text)
                    report[name] = "ok"
                except OSError as error:
                    report[name] = {"errno": error.errno, "errnoName": errno_name(error.errno),
                                    "reason": str(error)[:256]}
            report["postMapStatus"] = status_fields(read("/proc/self/status").get("value", ""))
        except OSError as error:
            report["unshare"] = {"errno": error.errno, "errnoName": errno_name(error.errno),
                                 "reason": str(error)[:256]}
        except BaseException as error:  # never leave the parent waiting
            report["error"] = f"{type(error).__name__}: {error}"[:256]
        os.write(writer, json.dumps(report).encode())
        os._exit(0)
    os.close(writer)
    data = b""
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        chunk = os.read(reader, 65536)
        if not chunk:
            break
        data += chunk
    os.close(reader)
    os.waitpid(pid, 0)
    try:
        return json.loads(data.decode())
    except ValueError:
        return {"error": "child report unreadable"}


def errno_name(number):
    import errno
    return errno.errorcode.get(number, str(number))


def probe(form, out):
    environment = {"LANG": "C.UTF-8", "TZ": "UTC", "PATH": "/usr/bin:/bin"}
    value = {
        "schema": "fsgg.d5.userns-ab.probe/1", "form": form,
        "utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "process": process_state(),
        "literalUnshare": command(UNSHARE_ARGV, env=environment),
        "postClone": clone_probe(),
    }
    literal = value["literalUnshare"]
    value["literalUnshare"]["passed"] = literal.get("exit") == 0
    value["literalUnshare"]["uidMapDenied"] = "write failed /proc/self/uid_map" in literal.get("stderr", "")
    write_json(out, value)


def kernlog(since, out):
    pattern = re.compile(r"apparmor|audit|userns|user namespace|DENIED|unshare", re.IGNORECASE)
    sources = {
        "dmesg": ["sudo", "-n", "dmesg", "--time-format=iso"],
        "journalKernel": ["sudo", "-n", "journalctl", "-k", "--no-pager", "-o", "short-iso",
                          "--since", f"@{int(since)}"],
        "journalAudit": ["sudo", "-n", "journalctl", "--no-pager", "-o", "short-iso",
                         "--since", f"@{int(since)}", "_TRANSPORT=audit"],
    }
    value = {"schema": "fsgg.d5.userns-ab.kernlog/1", "sinceEpoch": int(since)}
    for name, argv in sources.items():
        result = command(argv, timeout=30, limit=8388608)
        lines = result.pop("stdout", "") if result.get("exit") == 0 else ""
        matched = [line[:600] for line in lines.splitlines() if pattern.search(line)]
        result["totalLines"] = len(lines.splitlines())
        result["matchedLines"] = matched[-80:]
        value[name] = result
    audit_log = read("/var/log/audit/audit.log", 1)
    value["auditLogPresent"] = audit_log
    write_json(out, value)


def main(argv):
    try:
        if len(argv) == 4 and argv[1] == "snapshot":
            snapshot(argv[2], argv[3])
        elif len(argv) == 4 and argv[1] == "probe":
            probe(argv[2], argv[3])
        elif len(argv) == 4 and argv[1] == "kernlog":
            kernlog(float(argv[2]), argv[3])
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except Exception as error:  # data, not abort
        write_json(argv[-1], {"schema": "fsgg.d5.userns-ab.error/1",
                              "reason": f"{type(error).__name__}: {error}"[:512]})
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
