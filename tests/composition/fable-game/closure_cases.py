"""The closure oracle's cases (FS.GG.Templates#841): one crafted project each, with the verdict real MSBuild gives.

Each case is a tiny tree: `P/P.fsproj` (an SDK project with default items off) plus `P/Ok.fs` (managed) and `P/Gen.fs`
(a file the candidate carries and the manifest does not manage), and whatever else the case needs. `refused` says whether
the closure check must report a conflict: True when a project of the tree names a file the manifest does not manage (by
an item of any type, a glob, an import, a property, a condition, a target) or MSBuild cannot evaluate it, False when
MSBuild resolves every item to a managed file. The cases are the independent review's of #845 (B1 to B5 and N1) and
the controls beside them. Environment variables are not part of the evaluated configuration (case 01).
"""

GEN_ITEM = '<Compile Include="Gen.fs"/>'


def group(item=GEN_ITEM, condition=None):
    attribute = f' Condition="{condition}"' if condition else ""
    return f"<ItemGroup{attribute}>{item}</ItemGroup>"


OK_ONLY = '<ItemGroup><Compile Include="Ok.fs"/></ItemGroup>'
IMPORT_EXTRA = '<Project><ItemGroup><Compile Include="Gen.fs"/></ItemGroup></Project>'

# name -> (project body, extra files, unmanaged files besides P/Gen.fs, refused)
CASES = {
    "00-unconditional-unmanaged": ('<ItemGroup><Compile Include="Ok.fs"/><Compile Include="Gen.fs"/></ItemGroup>', {}, (), True),
    "01-env-variable-is-not-configuration": (group(condition="'$(CI)' == 'true'"), {}, (), False),
    "02-release-configuration": (group(condition="'$(Configuration)' == 'Release'"), {}, (), True),
    "03-debug-configuration": (group(condition="'$(Configuration)' == 'Debug'"), {}, (), True),
    "04-property-function-in-condition": (group(condition="'$([MSBuild]::IsOSPlatform(Linux))' == 'true'"), {}, (), True),
    "05-property-function-bare": (group(condition="$([MSBuild]::IsOSPlatform('Linux'))"), {}, (), True),
    "06-property-names-are-case-insensitive": ("<PropertyGroup><Flag>yes</Flag></PropertyGroup>" + group(condition="'$(FLAG)' == 'yes'"), {}, (), True),
    "07-item-type-is-case-insensitive": ('<ItemGroup><compile Include="Gen.fs"/></ItemGroup>', {}, (), True),
    "08-glob-doublestar-reaches-direct-children": ('<ItemGroup><Compile Include="**/*.fs"/></ItemGroup>', {}, (), True),
    "09-glob-star-reaches-direct-children": ('<ItemGroup><Compile Include="*.fs"/></ItemGroup>', {}, (), True),
    "10-glob-in-parent-directory": ('<ItemGroup><Compile Include="../P/*.fs"/></ItemGroup>', {}, (), True),
    "11-glob-doublestar-subdirectory": ('<ItemGroup><Compile Include="**/*.fs"/></ItemGroup>', {"P/sub/S.fs": "x"}, ("P/sub/S.fs",), True),
    "12-glob-doublestar-only": ('<ItemGroup><None Include="**"/></ItemGroup>', {}, (), True),
    "13-glob-with-prefix": ('<ItemGroup><Compile Include="sub/**/*.fs"/></ItemGroup>', {"P/sub/S.fs": "x"}, ("P/sub/S.fs",), True),
    "14-glob-over-managed-files-only": ('<ItemGroup><Compile Include="Ok.fs"/><Compile Include="*.fs" Exclude="Gen.fs"/></ItemGroup>', {}, (), False),
    "15-item-in-a-target": (f'<Target Name="Gen" BeforeTargets="CoreCompile"><ItemGroup>{GEN_ITEM}</ItemGroup></Target>', {}, (), True),
    "16-exists-empty-negated": (group(condition="!Exists('$(Unset)')"), {}, (), True),
    "17-exists-empty": (group(condition="Exists('$(Unset)')"), {}, (), False),
    "18-exists-literal-empty": (group(condition="Exists('')"), {}, (), False),
    "19-item-list-in-condition": (OK_ONLY + group(condition="'@(Compile)' != ''"), {}, (), True),
    "20-item-list-equals-empty": (group(condition="'@(Compile)' == ''"), {}, (), True),
    "21-item-metadata-in-condition": (group('<Compile Include="Gen.fs" Condition="\'%(Extension)\' == \'.fs\'"/>'), {}, (), True),
    "22-os-property": (group(condition="'$(OS)' == 'Unix'"), {}, (), True),
    "23-project-name": (group(condition="'$(MSBuildProjectName)' == 'P'"), {}, (), True),
    "24-project-extension": (group(condition="'$(MSBuildProjectExtension)' == '.fsproj'"), {}, (), True),
    "25-target-framework": (group(condition="'$(TargetFramework)' == 'net10.0'"), {}, (), True),
    "26-condition-is-case-insensitive": (group(condition="'YES' == 'yes'"), {}, (), True),
    "27-condition-true-literal": (group(condition="true"), {}, (), True),
    "28-undefined-property-is-empty": (group('<Compile Include="Gen.fs" Condition="\'$(Foo)\' == \'\'"/>'), {}, (), True),
    "29-choose-when": ('<Choose><When Condition="true"><ItemGroup><Compile Include="Gen.fs"/></ItemGroup></When></Choose>', {}, (), True),
    "30-property-list": ('<PropertyGroup><L>Ok.fs;Gen.fs</L></PropertyGroup><ItemGroup><Compile Include="$(L)"/></ItemGroup>', {}, (), True),
    "31-property-accumulates": ('<PropertyGroup><L>Ok.fs</L><L>$(L);Gen.fs</L></PropertyGroup><ItemGroup><Compile Include="$(L)"/></ItemGroup>', {}, (), True),
    "32-property-set-after-use": (group(condition="'$(Mode)' == 'b'") + "<PropertyGroup><Mode>b</Mode></PropertyGroup>", {}, (), True),
    "33-property-overridden-by-project": (group(condition="'$(Mode)' == 'a'") + "<PropertyGroup><Mode>b</Mode></PropertyGroup>",
                                          {"Directory.Build.props": "<Project><PropertyGroup><Mode>a</Mode></PropertyGroup></Project>"}, (), False),
    "34-remove-only": ('<ItemGroup><Compile Include="Ok.fs"/><Compile Remove="Gen.fs"/></ItemGroup>', {}, (), False),
    "35-resource-item": ('<ItemGroup><Resource Include="Gen.fs"/></ItemGroup>', {}, (), True),
    "36-compile-before-item": ('<ItemGroup><CompileBefore Include="Gen.fs"/></ItemGroup>', {}, (), True),
    "37-compile-after-item": ('<ItemGroup><CompileAfter Include="Gen.fs"/></ItemGroup>', {}, (), True),
    "38-embedded-resource-item": ('<ItemGroup><EmbeddedResource Include="Gen.fs"/></ItemGroup>', {}, (), True),
    "39-content-item": ('<ItemGroup><Content Include="Gen.fs"/></ItemGroup>', {}, (), True),
    "40-additional-files-item": ('<ItemGroup><AdditionalFiles Include="Gen.fs"/></ItemGroup>', {}, (), True),
    "41-property-names-a-file-only": ("<PropertyGroup><ApplicationManifest>Gen.fs</ApplicationManifest></PropertyGroup>" + OK_ONLY, {}, (), False),
    "42-project-directory-valid": ('<ItemGroup><Compile Include="$(MSBuildProjectDirectory)/Ok.fs"/></ItemGroup>', {}, ("P/Gen.fs",), False),
    "43-project-directory-unmanaged": ('<ItemGroup><Compile Include="$(MSBuildProjectDirectory)/Gen.fs"/></ItemGroup>', {"P/P/Gen.fs": "decoy"}, (), True),
    "44-this-file-directory-valid": ('<ItemGroup><Compile Include="$(MSBuildThisFileDirectory)Ok.fs"/></ItemGroup>', {}, ("P/Gen.fs",), False),
    "45-import-glob": ('<Import Project="*.targets" />', {"P/a.targets": IMPORT_EXTRA}, ("P/a.targets",), True),
    "46-import-when-exists": ('<Import Project="x.props" Condition="Exists(\'x.props\')"/>', {"P/x.props": IMPORT_EXTRA}, (), True),
    "47-import-of-unmanaged-file": ('<Import Project="x.props" />', {"P/x.props": "<Project/>"}, ("P/x.props",), True),
    "48-import-by-property-path": ('<Import Project="$(MSBuildThisFileDirectory)flags.props" /><ItemGroup Condition="\'$(Flag)\' == \'1\'"><Compile Include="Gen.fs"/></ItemGroup>',
                                   {"P/flags.props": "<Project><PropertyGroup><Flag>1</Flag></PropertyGroup></Project>"}, (), True),
    "49-import-projitems": ('<Import Project="Shared.projitems" />', {"P/Shared.projitems": IMPORT_EXTRA}, (), True),
    "50-import-unusual-extension": ('<Import Project="Shared.tasks" />', {"P/Shared.tasks": IMPORT_EXTRA}, (), True),
    "51-import-of-missing-file": ('<Import Project="missing.props" />', {}, (), True),
    "52-directory-build-props-relative-item": (OK_ONLY, {"Directory.Build.props": '<Project><ItemGroup><Compile Include="Extra.fs"/></ItemGroup></Project>',
                                                       "Extra.fs": "root", "P/Extra.fs": "in-project"}, ("P/Extra.fs",), True),
    "53-directory-build-props-this-file": ('<ItemGroup><Compile Include="$(Shared)"/></ItemGroup>',
                                           {"Directory.Build.props": "<Project><PropertyGroup><Shared>$(MSBuildThisFileDirectory)lib/L.fs</Shared></PropertyGroup></Project>",
                                            "lib/L.fs": "root-lib", "P/lib/L.fs": "project-lib"}, ("lib/L.fs",), True),
    "54-directory-build-props-gate": (group(condition="'$(Gate)' != 'off'"),
                                      {"Directory.Build.props": "<Project><PropertyGroup><Gate>off</Gate></PropertyGroup></Project>"}, (), False),
    "55-directory-build-targets-item": (OK_ONLY, {"Directory.Build.targets": '<Project><ItemGroup><Compile Include="$(MSBuildProjectDirectory)/Gen.fs"/></ItemGroup></Project>'}, (), True),
    # MSBuild resolves a relative include of an imported file against the importing project's directory, not the file's.
    "56-directory-build-targets-relative-to-project": (OK_ONLY, {"Directory.Build.targets": '<Project><ItemGroup><Compile Include="Gen.fs"/></ItemGroup></Project>', "Gen.fs": "root-managed"}, ("P/Gen.fs",), True),
    "56b-directory-build-targets-relative-managed": (OK_ONLY, {"Directory.Build.targets": '<Project><ItemGroup><Compile Include="Ok.fs"/></ItemGroup></Project>'}, ("P/Gen.fs",), False),
    "57-directory-build-targets-property": (group(condition="'$(Late)' == '1'"), {"Directory.Build.targets": "<Project><PropertyGroup><Late>1</Late></PropertyGroup></Project>"}, (), True),
    "58-managed-everything": (OK_ONLY, {}, ("P/Gen.fs",), False),
    # Out-of-tree items and the shapes an evaluation cannot see (#849).
    "60-compile-outside-the-tree": ('<ItemGroup><Compile Include="Ok.fs"/><Compile Include="../../Outside.fs"/></ItemGroup>', {}, (), True),
    "61-project-reference-outside-the-tree": ('<ItemGroup><ProjectReference Include="../../Other/Other.fsproj"/></ItemGroup>', {}, (), True),
    "62-multi-targeted-project": ("<PropertyGroup><TargetFrameworks>net10.0;net9.0</TargetFrameworks></PropertyGroup>" + OK_ONLY, {}, (), True),
    "63-create-item-task-in-a-target": ('<Target Name="T" BeforeTargets="CoreCompile"><CreateItem Include="Gen.fs"><Output TaskParameter="Include" ItemName="Compile"/></CreateItem></Target>', {}, (), True),
    "64-target-without-items": ('<Target Name="T"><Message Text="hello"/></Target>' + OK_ONLY, {}, (), False),
    # Directories the tree observation ignores are not exempt from the closure.
    "68-closure-item-under-vendor": ('<ItemGroup><Compile Include="vendor/V.fs"/></ItemGroup>', {"P/vendor/V.fs": "x"}, ("P/vendor/V.fs",), True),
    "69-closure-item-under-output": ('<ItemGroup><Compile Include="output/O.fs"/><Compile Include="dist/D.fs"/></ItemGroup>', {"P/output/O.fs": "x", "P/dist/D.fs": "x"}, ("P/output/O.fs", "P/dist/D.fs"), True),
    "70-managed-file-under-an-ignored-directory": ('<ItemGroup><Compile Include="output/O.fs"/></ItemGroup>', {"P/output/O.fs": "x"}, (), False),
    "71-unmanaged-vendor-glob": ('<ItemGroup><Compile Include="vendor/*.fs"/></ItemGroup>', {"P/vendor/V.fs": "x"}, ("P/vendor/V.fs",), True),
    "72-unmanaged-vendor-exists": ('<ItemGroup Condition="Exists(\'vendor/V.fs\')"><Compile Include="vendor/V.fs"/></ItemGroup>', {"P/vendor/V.fs": "x"}, ("P/vendor/V.fs",), True),
    "73-managed-output-glob": ('<ItemGroup><Compile Include="output/*.fs"/></ItemGroup>', {"P/output/O.fs": "x"}, (), False),
}
