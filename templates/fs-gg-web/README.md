# WebWorkspace

This neutral workspace keeps one F# ASP.NET Core server and one plain TypeScript/Vite client. It deliberately does not choose a client framework.

Run `./build.sh` for the root restore, build, server lane, client lane, and browser lane. Development uses two terminals: `dotnet run --project Server/WebWorkspace.Server.fsproj` and `npm run dev --prefix Web`; Vite proxies `/api` to `http://localhost:5000`. For production, run `npm ci --prefix Web && npm run build --prefix Web` before publishing Server: the server serves `Web/dist`.

The lanes are `Server`, `Web`, `Server.Tests`, `Web/tests`, and `Browser.Tests`. `build.sh` writes the server TRX and browser JUnit evidence to `artifacts/test-results/`; import those observed reports with `fsgg-sdd evidence --from-test-report`. SDD remains the single lifecycle owner.
