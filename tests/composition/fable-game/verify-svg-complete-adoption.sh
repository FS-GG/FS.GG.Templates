#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
candidate="${1:?materialized complete candidate or template source root required}"
public_archives="${2:?directory containing public 0.10.0 through 0.13.0 archives required}"
out="${3:?empty evidence directory required}"
[[ ! -e "$out" ]]
mkdir -p "$out"

adopter="$root/scripts/apply-svg-foundation-preview.sh"
manifest="$root/scripts/svg-complete-workspace-baselines.json"
tree_sha() {
  python3 - "$1" <<'PY'
from pathlib import Path
import hashlib, os, stat, sys
root=Path(sys.argv[1]); rows=[]
for path in sorted(root.rglob('*')):
    rel=path.relative_to(root).as_posix(); mode=stat.S_IMODE(path.lstat().st_mode)
    if path.is_symlink(): kind='symlink'; value=os.readlink(path).encode()
    elif path.is_file(): kind='file'; value=path.read_bytes()
    else: continue
    rows.append(f'{kind}\t{mode:o}\t{hashlib.sha256(value).hexdigest()}\t{rel}\n')
print(hashlib.sha256(''.join(rows).encode()).hexdigest())
PY
}
preserved_sha() {
  sha256sum \
    "$1/.agents/skills/local-gameplay/SKILL.md" \
    "$1/authored/level.json" \
    "$1/authored/keymap-v1.json" \
    "$1/authored/replay-v1.json"
}
validate_selected_skills() {
  python3 - "$1" "$2" "$3" "${@:4}" <<'PY'
from pathlib import Path
import hashlib, json, sys
candidate, workspace, prior = map(Path, sys.argv[1:4])
mirrors = sys.argv[4:]
source = json.loads((candidate/'.agents/skills/skill-manifest.json').read_text())
package=[row for row in source['skills']
         if row.get('scope') == 'product'
         and row.get('supplied-by','').startswith('template/product-skills/fable-')]
package_ids={row['id'] for row in package}
before=json.loads((prior/'.agents/skills/skill-manifest.json').read_text())
preserved=[row for row in before['skills'] if row['id'] not in package_ids and row['id'] != 'fable-remoting']
expected={'schemaVersion':1,'skills':sorted(preserved+package,key=lambda row:row['id'])}
assert json.loads((workspace/'.agents/skills/skill-manifest.json').read_text()) == expected
missing=[]
for row in expected['skills']:
    body=workspace/row['resolvablePath']
    if body.is_file():
        assert hashlib.sha256(body.read_bytes()).hexdigest() == row['sha256']
    else:
        missing.append(row['id'])
assert missing == ['fable-bindings']
for mirror in mirrors:
    mirror_root=workspace/mirror
    assert json.loads((mirror_root/'skill-manifest.json').read_text()) == expected
    for row in expected['skills']:
        relative=Path(row['resolvablePath']).relative_to('.agents/skills')
        body=mirror_root/relative
        if row['id'] == 'fable-bindings':
            assert not body.exists()
        else:
            assert body.is_file()
            assert hashlib.sha256(body.read_bytes()).hexdigest() == row['sha256']
PY
}

for version in 0.10.0 0.11.0 0.12.0 0.13.0; do
  archive="$public_archives/FS.GG.Workspace.Template.$version.nupkg"
  [[ -f "$archive" ]]
  expected="$(jq -r --arg version "$version" '.sourceArchives[] | select(.version==$version) | .sha256' "$manifest")"
  [[ -n "$expected" && "$(sha256sum "$archive" | cut -d' ' -f1)" == "$expected" ]]
  home="$out/home-$version"
  workspace="$out/retained-$version"
  mkdir -p "$home"
  DOTNET_CLI_HOME="$home" dotnet new install "$archive" --force >/dev/null
  args=(dotnet new fs-gg-fable-game -n "Retained${version//./}" -o "$workspace" --lifecycle none)
  if [[ "$version" != 0.10.0 ]]; then args+=(--svgFoundation true); fi
  DOTNET_CLI_HOME="$home" "${args[@]}" >/dev/null

  mkdir -p "$workspace/.agents/skills/local-gameplay" "$workspace/authored"
  printf '%s\n' '# Retained local gameplay skill' >"$workspace/.agents/skills/local-gameplay/SKILL.md"
  printf '%s\n' '{"level":"retained","hiddenPresentation":true}' >"$workspace/authored/level.json"
  printf '%s\n' '{"schema":1,"interact":"e"}' >"$workspace/authored/keymap-v1.json"
  printf '%s\n' '{"schema":1,"positions":[[1,2]]}' >"$workspace/authored/replay-v1.json"
  preserved_sha "$workspace" >"$out/$version-preserved.before"
  cp -a "$workspace" "$out/original-$version"

  "$adopter" complete-inventory "$candidate" "$workspace" "$manifest" \
    "$out/$version-inventory.json" "$out/$version-review.diff"
  jq -e '.ready==true and (.changes|length)>0 and (.conflicts|length)==0 and (.preserved|length)>0' \
    "$out/$version-inventory.json" >/dev/null
  grep -F 'a/.agents/skills/fable-remoting/SKILL.md' "$out/$version-review.diff" >/dev/null
  grep -F '+++ /dev/null' "$out/$version-review.diff" >/dev/null
  "$adopter" complete-apply "$candidate" "$workspace" "$manifest" \
    "$out/$version-inventory.json" "$out/$version-backup"
  preserved_sha "$workspace" >"$out/$version-preserved.after"
  cmp "$out/$version-preserved.before" "$out/$version-preserved.after"
  test -f "$workspace/Domain/ArenaRules.fs"
  test -f "$workspace/Conformance/SceneSchema.fs"
  test -f "$workspace/SvgFoundation/Examples/Tactical/scene.json"
  test -f "$workspace/SvgFoundation/Examples/Arcade/scene.json"
  test -f "$workspace/.github/workflows/product-ci.yml"
  test -f "$workspace/.agents/skills/fable-http-codecs/SKILL.md"
  test ! -e "$workspace/.agents/skills/fable-remoting/SKILL.md"
  test ! -e "$workspace/.claude"
  test ! -e "$workspace/.codex"
  validate_selected_skills "$candidate" "$workspace" "$out/original-$version"
  test -x "$workspace/build.sh"
  grep -F "Retained${version//./}" "$workspace/Domain/ArenaRules.fs" >/dev/null
  grep -F "Retained${version//./}.slnx" "$workspace/build.sh" >/dev/null
  (cd "$workspace" && dotnet restore "Retained${version//./}.slnx" --locked-mode \
    && dotnet build "Retained${version//./}.slnx" --no-restore) >"$out/$version-build.log" 2>&1
done

# A real union manifest can contain an independently owned product row. The
# transaction authenticates legacy Fable rows individually, merges the new
# package rows, and preserves the unrelated declaration and body byte-for-byte.
cp -a "$out/original-0.13.0" "$out/union"
python3 - "$out/union" <<'PY'
from pathlib import Path
import hashlib, json, sys
root=Path(sys.argv[1])
manifest=root/'.agents/skills/skill-manifest.json'
value=json.loads(manifest.read_text())
body=root/'.agents/skills/local-gameplay/SKILL.md'
value['skills'].append({
    'id':'local-gameplay', 'scope':'product',
    'sha256':hashlib.sha256(body.read_bytes()).hexdigest(),
    'resolvablePath':'.agents/skills/local-gameplay/SKILL.md',
    'materializes-when':'local receiver', 'supplied-by':'receiver/local-gameplay/'})
value['skills'].sort(key=lambda row:row['id'])
manifest.write_text(json.dumps(value,indent=2)+'\n')
PY
cp -a "$out/union" "$out/union-before"
"$adopter" complete-inventory "$candidate" "$out/union" "$manifest" \
  "$out/union-inventory.json" "$out/union-review.diff" >/dev/null
"$adopter" complete-apply "$candidate" "$out/union" "$manifest" \
  "$out/union-inventory.json" "$out/union-backup" >/dev/null
validate_selected_skills "$candidate" "$out/union" "$out/union-before"
cmp "$out/union/.agents/skills/local-gameplay/SKILL.md" "$out/union-before/.agents/skills/local-gameplay/SKILL.md"

# A package row is authenticated as a whole declaration. Changing its metadata
# while leaving its body digest intact refuses the inventory before writes.
cp -a "$out/union-before" "$out/skill-row-metadata-collision"
python3 - "$out/skill-row-metadata-collision/.agents/skills/skill-manifest.json" <<'PY'
from pathlib import Path
import json,sys
p=Path(sys.argv[1]); value=json.loads(p.read_text())
next(row for row in value['skills'] if row['id']=='fable-project')['materializes-when']='always'
p.write_text(json.dumps(value,indent=2)+'\n')
PY
skill_row_before="$(tree_sha "$out/skill-row-metadata-collision")"
if "$adopter" complete-inventory "$candidate" "$out/skill-row-metadata-collision" "$manifest" \
  "$out/skill-row-metadata-inventory.json" "$out/skill-row-metadata-review.diff" \
  >"$out/skill-row-metadata.log" 2>&1; then
  echo 'edited package skill manifest row unexpectedly accepted' >&2; exit 1
fi
jq -e '.ready==false and any(.conflicts[]; .path==".agents/skills/skill-manifest.json")' \
  "$out/skill-row-metadata-inventory.json" >/dev/null
[[ "$skill_row_before" == "$(tree_sha "$out/skill-row-metadata-collision")" ]]

# Existing supported skill mirrors are updated as one product-skill transaction;
# absent mirror roots are not invented. Both known mirror layouts exercise the
# same selected manifest and body digests while unrelated local skills survive.
cp -a "$out/union-before" "$out/configured-mirrors"
for mirror in .claude/skills; do
  mkdir -p "$out/configured-mirrors/$mirror"
  cp -a "$out/configured-mirrors/.agents/skills/fable-"* "$out/configured-mirrors/$mirror/"
  cp -a "$out/configured-mirrors/.agents/skills/local-gameplay" "$out/configured-mirrors/$mirror/"
  cp "$out/configured-mirrors/.agents/skills/skill-manifest.json" "$out/configured-mirrors/$mirror/skill-manifest.json"
done
mirror_preserved_before="$(sha256sum "$out/configured-mirrors/.agents/skills/local-gameplay/SKILL.md" | cut -d' ' -f1)"
"$adopter" complete-inventory "$candidate" "$out/configured-mirrors" "$manifest" \
  "$out/configured-mirrors-inventory.json" "$out/configured-mirrors-review.diff" >/dev/null
"$adopter" complete-apply "$candidate" "$out/configured-mirrors" "$manifest" \
  "$out/configured-mirrors-inventory.json" "$out/configured-mirrors-backup" >/dev/null
validate_selected_skills "$candidate" "$out/configured-mirrors" "$out/union-before" .claude/skills
test ! -e "$out/configured-mirrors/.claude/skills/fable-remoting/SKILL.md"
[[ "$mirror_preserved_before" == "$(sha256sum "$out/configured-mirrors/.agents/skills/local-gameplay/SKILL.md" | cut -d' ' -f1)" ]]
"$adopter" complete-rollback "$out/configured-mirrors" "$out/configured-mirrors-backup" >/dev/null
test -f "$out/configured-mirrors/.claude/skills/fable-remoting/SKILL.md"

# A customized shared Domain path is authored product code. Refuse the complete
# transaction before creating a journal or changing any workspace byte.
cp -a "$out/original-0.13.0" "$out/collision"
printf '%s\n' '// retained owner edit' >>"$out/collision/Domain/Room.fs"
collision_before="$(tree_sha "$out/collision")"
if "$adopter" complete-inventory "$candidate" "$out/collision" "$manifest" \
  "$out/collision-inventory.json" "$out/collision-review.diff" >"$out/collision.log" 2>&1; then
  echo 'complete adoption collision unexpectedly accepted' >&2; exit 1
fi
jq -e '.ready==false and any(.conflicts[]; .path=="Domain/Room.fs" and .reason=="edited or unsupported managed content")' \
  "$out/collision-inventory.json" >/dev/null
[[ "$collision_before" == "$(tree_sha "$out/collision")" && ! -e "$out/collision-backup" ]]

# Package-owned skill paths follow the same collision rule. A receiver edit to
# an active skill or an obsolete skill that would otherwise be retired refuses
# the whole transaction while unrelated local skills remain preserved.
cp -a "$out/original-0.13.0" "$out/skill-collision"
printf '%s\n' '# retained owner edit' >>"$out/skill-collision/.agents/skills/fable-project/SKILL.md"
skill_collision_before="$(tree_sha "$out/skill-collision")"
if "$adopter" complete-inventory "$candidate" "$out/skill-collision" "$manifest" \
  "$out/skill-collision-inventory.json" "$out/skill-collision-review.diff" >"$out/skill-collision.log" 2>&1; then
  echo 'edited product skill unexpectedly accepted' >&2; exit 1
fi
jq -e '.ready==false and any(.conflicts[]; .path==".agents/skills/fable-project/SKILL.md")' \
  "$out/skill-collision-inventory.json" >/dev/null
[[ "$skill_collision_before" == "$(tree_sha "$out/skill-collision")" ]]

cp -a "$out/original-0.13.0" "$out/retired-skill-collision"
printf '%s\n' '# retained owner edit' >>"$out/retired-skill-collision/.agents/skills/fable-remoting/SKILL.md"
retired_collision_before="$(tree_sha "$out/retired-skill-collision")"
if "$adopter" complete-inventory "$candidate" "$out/retired-skill-collision" "$manifest" \
  "$out/retired-skill-inventory.json" "$out/retired-skill-review.diff" >"$out/retired-skill.log" 2>&1; then
  echo 'edited retired product skill unexpectedly deleted' >&2; exit 1
fi
jq -e '.ready==false and any(.conflicts[]; .path==".agents/skills/fable-remoting/SKILL.md" and .reason=="edited retired product skill")' \
  "$out/retired-skill-inventory.json" >/dev/null
[[ "$retired_collision_before" == "$(tree_sha "$out/retired-skill-collision")" ]]

# Both sides of the reviewed transaction include executable modes. Changing a
# candidate or receiver mode after inventory makes that inventory stale before
# a backup or workspace write.
cp -a "$candidate" "$out/mode-candidate"
cp -a "$out/original-0.13.0" "$out/mode-candidate-workspace"
"$adopter" complete-inventory "$out/mode-candidate" "$out/mode-candidate-workspace" "$manifest" \
  "$out/mode-candidate-inventory.json" "$out/mode-candidate-review.diff" >/dev/null
chmod u+x "$out/mode-candidate/Domain/Room.fs"
mode_candidate_before="$(tree_sha "$out/mode-candidate-workspace")"
if "$adopter" complete-apply "$out/mode-candidate" "$out/mode-candidate-workspace" "$manifest" \
  "$out/mode-candidate-inventory.json" "$out/mode-candidate-backup" >"$out/mode-candidate.log" 2>&1; then
  echo 'candidate mode change after inventory unexpectedly accepted' >&2; exit 1
fi
grep -F 'inventory is stale or mismatched at candidateManagedSha256' "$out/mode-candidate.log" >/dev/null
[[ "$mode_candidate_before" == "$(tree_sha "$out/mode-candidate-workspace")" && ! -e "$out/mode-candidate-backup" ]]

cp -a "$out/original-0.13.0" "$out/mode-workspace"
"$adopter" complete-inventory "$candidate" "$out/mode-workspace" "$manifest" \
  "$out/mode-workspace-inventory.json" "$out/mode-workspace-review.diff" >/dev/null
chmod u+x "$out/mode-workspace/Domain/Room.fs"
mode_workspace_changed="$(tree_sha "$out/mode-workspace")"
if "$adopter" complete-apply "$candidate" "$out/mode-workspace" "$manifest" \
  "$out/mode-workspace-inventory.json" "$out/mode-workspace-backup" >"$out/mode-workspace.log" 2>&1; then
  echo 'workspace mode change after inventory unexpectedly accepted' >&2; exit 1
fi
grep -F 'inventory is stale or mismatched at workspaceTreeSha256' "$out/mode-workspace.log" >/dev/null
[[ "$mode_workspace_changed" == "$(tree_sha "$out/mode-workspace")" && ! -e "$out/mode-workspace-backup" ]]

# A symlinked managed parent could redirect writes outside the receiver. It is
# a structural collision even when the external files happen to match.
cp -a "$out/original-0.13.0" "$out/symlink-collision"
mv "$out/symlink-collision/Domain" "$out/symlink-collision/Domain.real"
ln -s Domain.real "$out/symlink-collision/Domain"
symlink_before="$(tree_sha "$out/symlink-collision")"
if "$adopter" complete-inventory "$candidate" "$out/symlink-collision" "$manifest" \
  "$out/symlink-inventory.json" "$out/symlink-review.diff" >"$out/symlink.log" 2>&1; then
  echo 'managed-parent symlink unexpectedly accepted' >&2; exit 1
fi
[[ "$symlink_before" == "$(tree_sha "$out/symlink-collision")" ]]

# Injected interruption runs through the real apply loop and must restore every
# file byte from its prepared journal. The retained journal remains inspectable.
cp -a "$out/original-0.12.0" "$out/interrupted"
interrupted_before="$(tree_sha "$out/interrupted")"
"$adopter" complete-inventory "$candidate" "$out/interrupted" "$manifest" \
  "$out/interrupted-inventory.json" "$out/interrupted-review.diff" >/dev/null
if FSGG_SVG_COMPLETE_FAIL_AFTER=37 "$adopter" complete-apply "$candidate" "$out/interrupted" "$manifest" \
  "$out/interrupted-inventory.json" "$out/interrupted-backup" >"$out/interrupted.log" 2>&1; then
  echo 'injected complete adoption interruption unexpectedly succeeded' >&2; exit 1
fi
[[ "$interrupted_before" == "$(tree_sha "$out/interrupted")" ]]
jq -e '.status=="rolled-back"' "$out/interrupted-backup/journal.json" >/dev/null

# Rollback is not a downgrade operation. A newer edit to an adopted managed
# scene makes the whole rollback refuse before changing any path.
printf '%s\n' ' ' >>"$out/retained-0.13.0/SvgFoundation/Examples/Arcade/scene.json"
edited_before="$(tree_sha "$out/retained-0.13.0")"
if "$adopter" complete-rollback "$out/retained-0.13.0" "$out/0.13.0-backup" \
  >"$out/edited-rollback.log" 2>&1; then
  echo 'rollback unexpectedly overwrote a newer managed edit' >&2; exit 1
fi
grep -F 'rollback refused before writes: managed path changed after adoption' "$out/edited-rollback.log" >/dev/null
[[ "$edited_before" == "$(tree_sha "$out/retained-0.13.0")" ]]

# A committed apply remains explicitly reversible to byte-identical managed and
# preserved content; recovery uses the same journal reader as manual rollback.
cp -a "$out/interrupted" "$out/rollback"
rollback_before="$(tree_sha "$out/rollback")"
"$adopter" complete-inventory "$candidate" "$out/rollback" "$manifest" \
  "$out/rollback-inventory.json" "$out/rollback-review.diff" >/dev/null
"$adopter" complete-apply "$candidate" "$out/rollback" "$manifest" \
  "$out/rollback-inventory.json" "$out/rollback-backup" >/dev/null
"$adopter" complete-recover "$out/rollback" "$out/rollback-backup" >/dev/null
[[ "$rollback_before" == "$(tree_sha "$out/rollback")" ]]

# An interruption during an explicit rollback leaves a durable rolling-back
# journal. Recovery accepts only the recorded before/after mixture and resumes
# to the exact pre-adoption bytes and modes.
cp -a "$out/original-0.10.0" "$out/rollback-interrupted"
rollback_interrupted_before="$(tree_sha "$out/rollback-interrupted")"
"$adopter" complete-inventory "$candidate" "$out/rollback-interrupted" "$manifest" \
  "$out/rollback-interrupted-inventory.json" "$out/rollback-interrupted-review.diff" >/dev/null
"$adopter" complete-apply "$candidate" "$out/rollback-interrupted" "$manifest" \
  "$out/rollback-interrupted-inventory.json" "$out/rollback-interrupted-backup" >/dev/null
if FSGG_SVG_COMPLETE_ROLLBACK_FAIL_AFTER=37 "$adopter" complete-rollback \
  "$out/rollback-interrupted" "$out/rollback-interrupted-backup" \
  >"$out/rollback-interrupted.log" 2>&1; then
  echo 'injected rollback interruption unexpectedly succeeded' >&2; exit 1
fi
jq -e '.status=="rolling-back"' "$out/rollback-interrupted-backup/journal.json" >/dev/null
"$adopter" complete-recover "$out/rollback-interrupted" "$out/rollback-interrupted-backup" >/dev/null
[[ "$rollback_interrupted_before" == "$(tree_sha "$out/rollback-interrupted")" ]]
jq -e '.status=="rolled-back"' "$out/rollback-interrupted-backup/journal.json" >/dev/null

# Corrupting even a late backup object refuses before any earlier restore write.
cp -a "$out/original-0.11.0" "$out/corrupt-backup"
"$adopter" complete-inventory "$candidate" "$out/corrupt-backup" "$manifest" \
  "$out/corrupt-inventory.json" "$out/corrupt-review.diff" >/dev/null
"$adopter" complete-apply "$candidate" "$out/corrupt-backup" "$manifest" \
  "$out/corrupt-inventory.json" "$out/corrupt-journal" >/dev/null
corrupt_before="$(tree_sha "$out/corrupt-backup")"
printf '%s\n' corrupt >>"$out/corrupt-journal/files/build.sh"
if "$adopter" complete-rollback "$out/corrupt-backup" "$out/corrupt-journal" \
  >"$out/corrupt-rollback.log" 2>&1; then
  echo 'rollback unexpectedly accepted corrupt backup object' >&2; exit 1
fi
[[ "$corrupt_before" == "$(tree_sha "$out/corrupt-backup")" ]]

jq -n \
  --arg manifestSha256 "$(sha256sum "$manifest" | cut -d' ' -f1)" \
  --arg candidate "$(realpath "$candidate")" \
  --argjson versions "$(printf '%s\n' 0.10.0 0.11.0 0.12.0 0.13.0 | jq -R . | jq -s .)" \
  '{schema:"fsgg.svg-complete-adoption-qualification/v1",result:"passed",candidate:$candidate,manifestSha256:$manifestSha256,publicBaselines:$versions,managedCollision:"refused-before-write",productSkillCollision:"refused-before-write",packageSkillRowMetadata:"refused-before-write",unrelatedManifestRows:"preserved-exact",editedRetiredSkill:"preserved-and-refused-before-write",retiredProductSkill:"deleted-with-review-and-rollback",selectedSkillManifest:"materialized-product-bodies-digest-matched",configuredSkillMirrors:"declared-agents-claude-roots-transactionally-matched",managedParentSymlink:"refused-before-write",candidateModeChange:"stale-inventory-refused-before-write",workspaceModeChange:"stale-inventory-refused-before-write",interruption:"rolled-back",interruptedRollback:"recovered-byte-and-mode-identical",explicitRecovery:"byte-and-mode-identical",newerManagedEdit:"rollback-refused-before-write",corruptBackup:"rollback-refused-before-write",authoredFiles:"preserved"}' \
  >"$out/qualification.json"
echo "complete workspace adoption qualification: passed; evidence=$out/qualification.json"
