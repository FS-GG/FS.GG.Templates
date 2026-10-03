# shellcheck shell=bash
# Bind the provider assertion to the same installed apphost and its exact tool version directory.
sdd_commands_assembly() {
  local apphost version tool_root assembly
  apphost="$(command -v fsgg-sdd)" || return 1
  [[ -f "$apphost" ]] || return 1
  apphost="$(realpath "$apphost")" || return 1
  version="$("$apphost" --version)" || return 1
  [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || return 1
  tool_root="$(dirname "$apphost")/.store/fs.gg.sdd.cli/$version/fs.gg.sdd.cli/$version/tools/net10.0/any"
  assembly="$tool_root/FS.GG.SDD.Commands.dll"
  [[ -f "$assembly" && -f "$tool_root/FS.GG.SDD.Cli.dll" ]] || return 1
  printf '%s\n' "$assembly"
}
