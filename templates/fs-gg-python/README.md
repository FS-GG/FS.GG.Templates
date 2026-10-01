# PythonProduct

This minimal Python workspace uses the canonical Python Hello fixture authored by
FS.GG.Coordination. The template package projects the reviewed `app.py`, `build.py`, and
`test.py` bytes from that source; this repository does not maintain another implementation.

Run the product entry point with Python 3.14:

```sh
python3 python/app.py
```

The portable executor's sole reviewed operation runs `python/test.py` inside its qualified
image. That operation also runs the fixed build helper and writes its verification output
beneath `/output`. Product build, test, and journey operations are not separately selectable.

`portable-workspace-profile.template.json` is an inert preparation template. After committing
the generated receiver, qualification tooling copies it to a private request directory and
binds `WORKSPACE_SCOPE`, `RECEIVER_COMMIT`, and `QUALIFIED_IMAGE_REFERENCE` to the authorized
facts. Do not commit the bound profile back into this workspace: a file cannot contain the
commit identity that already includes that file. The profile template is not an enrollment,
grant, or claim of installed portable execution support.

Direct `dotnet new fs-gg-python` generation creates no `.fsgg` content. When this provider is
selected through `fsgg-sdd scaffold`, SDD owns its lifecycle files and scaffold provenance.
