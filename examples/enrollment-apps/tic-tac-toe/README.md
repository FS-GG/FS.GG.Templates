# Tic-tac-toe

A dependency-free, local two-player browser game. The shared enrollment-app harness serves this directory at `/tic-tac-toe/` and discovers the local Node and Playwright tests.

From `examples/enrollment-apps`, install the shared test tools and run its documented test and browser-test commands. For a quick manual launch from the repository root:

```console
python3 -m http.server 4197 --directory examples/enrollment-apps
```

Then open <http://127.0.0.1:4197/tic-tac-toe/>.
