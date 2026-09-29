# Local todo app

A standalone browser todo list with add, edit, complete, filter and delete controls. Tasks are stored under the versioned `fs-gg.todo.v1` localStorage key, so data belongs to one browser and origin. Clearing site data or changing the serving origin starts a fresh list.

From the repository root, install the locked shared tools, stage the static files, then start the shared server and open `http://127.0.0.1:4197/todo/`:

```console
npm --prefix examples/enrollment-apps ci --ignore-scripts
npm --prefix examples/enrollment-apps run build
npm --prefix examples/enrollment-apps run serve
```

The server uses port `4197` by default; set `ENROLLMENT_APP_PORT` to choose another port. In a second terminal, run the pure domain checks and focused Chromium journey through the shared harness:

```console
node --test examples/enrollment-apps/todo/domain.test.mjs
npm --prefix examples/enrollment-apps run test:browser -- todo
```

The app has no build step or runtime package dependency. Its checked-in HTML, CSS and ESM JavaScript are the files served to the browser.
