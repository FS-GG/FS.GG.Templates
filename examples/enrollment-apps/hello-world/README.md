# Hello-world browser app

This example renders **Hello, world!** from a browser-native JavaScript module.

From the repository root, install the shared browser harness, stage the examples,
and start the static server:

```console
npm --prefix examples/enrollment-apps ci --ignore-scripts
npm --prefix examples/enrollment-apps run build
npm --prefix examples/enrollment-apps run serve
```

Open <http://127.0.0.1:4197/hello-world/>. In another terminal, run its browser
journey with:

```console
npm --prefix examples/enrollment-apps run test:browser -- hello-world
```
