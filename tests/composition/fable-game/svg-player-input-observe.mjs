import { chromium, firefox, webkit } from "@playwright/test";

const family=process.argv[2];
const address=process.argv[3];
const kind={chromium,firefox,webkit}[family];
if(!kind||!address) throw new Error("usage: node svg-player-input-observe.mjs <chromium|firefox|webkit> <address>");
const external=family==="chromium"?process.env.PLAYWRIGHT_EXECUTABLE_PATH:family==="firefox"?process.env.PLAYWRIGHT_FIREFOX_EXECUTABLE_PATH:process.env.PLAYWRIGHT_WEBKIT_EXECUTABLE_PATH;
const browser=await kind.launch({headless:true,executablePath:external||undefined});
try {
  const page=await browser.newPage();
  await page.goto(address,{waitUntil:"networkidle"});
  const scope=page.locator("#foundation-tactical-compatibility-host");
  await scope.waitFor();
  await scope.focus();
  for(const [key,command] of [["n","game.focus-next"],["p","game.focus-previous"],["a","game.activate"]]) {
    await page.keyboard.press(key);
    await page.waitForFunction(expected=>document.querySelector("#foundation-tactical-compatibility-host")?.getAttribute("data-last-game-command")===expected,command);
  }
  const selected=await scope.locator("[data-selected='true']").count();
  const command=await scope.getAttribute("data-last-game-command");
  if(selected!==1||command!=="game.activate") throw new Error(JSON.stringify({selected,command}));
  console.log(JSON.stringify({family,result:"passed",journey:"generated-player-input",selected,command}));
} finally { await browser.close(); }
