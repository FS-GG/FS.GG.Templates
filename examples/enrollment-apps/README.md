# Enrolled browser apps

These four independent source samples are opt-in. They are outside packaged template content and do not change generated workspaces or lifecycle defaults.

From the Templates repository root:

```sh
npm --prefix examples/enrollment-apps ci --ignore-scripts
npm --prefix examples/enrollment-apps run build
npm --prefix examples/enrollment-apps run serve
```

Open `http://127.0.0.1:4197/` and choose an app. The build stages exact HTML, JavaScript and CSS source bytes and records their SHA-256 hashes; these browser-native modules need no transpiler. `ENROLLMENT_APP_PORT` selects another loopback port.

Stop the serving process before running the checks:

```sh
npm --prefix examples/enrollment-apps run test:domain
npm --prefix examples/enrollment-apps run test:browser
```

Browser checks use actual staged entry points with a fresh owned static server. Install Chromium with `npx playwright install chromium` from this directory, or supply a compatible executable through `PLAYWRIGHT_EXECUTABLE_PATH`. App-specific checks accept a path filter, for example `npm --prefix examples/enrollment-apps run test:browser -- todo`.

The owning roadmaps distinguish tested source, native delivery and protected readback from publication or installed scaffold adoption. Planning, staging and individual checks do not count as completed cohort items.
