# Shared authored Node implementation; the two source-language contracts stay distinct.
node_prepare() {
  npm ci --offline --ignore-scripts --no-audit --no-fund --userconfig=/dev/null --globalconfig=/dev/null --cache "${NPM_CONFIG_CACHE:?selected private locked cache required}"
}
node_build() {
  node node_modules/typescript/bin/tsc --project tsconfig.json
  case "$FSGG_POLYGLOT_PROVIDER" in
    javascript-cli) node --check src/main.js; node --check src/domain.js ;;
    typescript-cli) test -s dist/main.js; test -s dist/domain.js ;;
    *) echo 'closed Node provider required' >&2; return 3 ;;
  esac
}
node_lint() { node node_modules/typescript/bin/tsc --project tsconfig.json --noEmit; }
node_test() { node --test tests/cli.test.mjs; }
node_surface() {
  case "$FSGG_POLYGLOT_PROVIDER" in typescript-cli) entry=dist/main.js ;; javascript-cli) entry=src/main.js ;; *) return 3;; esac
  [ "$(node "$entry" hello 'surface text')" = 'hello surface text' ]
}
node_package() { npm pack --ignore-scripts --userconfig=/dev/null --globalconfig=/dev/null --json --pack-destination . > package-result.json; }
