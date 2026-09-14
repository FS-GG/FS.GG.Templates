import { chromium, firefox, webkit } from "@playwright/test";

const family=process.argv[2];
const address=process.argv[3];
const kind={chromium,firefox,webkit}[family];
if(!kind||!address) throw new Error("usage: node svg-authoring-observe.mjs <chromium|firefox|webkit> <address>");
const browser=await kind.launch({headless:true,executablePath:family==="chromium"?(process.env.PLAYWRIGHT_EXECUTABLE_PATH||undefined):undefined});
try {
  const page=await browser.newPage();
  await page.goto(address,{waitUntil:"networkidle"});
  await page.waitForFunction(()=>window.svgGeneratedStudio);
  const click=async name=>page.getByRole("button",{name,exact:true}).click();
  await click("Rectangle");
  await click("Path");
  await click("Save asset");
  await click("Place two instances");
  await click("Edit scene properties");
  await click("Author grid and freeform");
  await click("Create asset revision");
  const conflicted=await page.evaluate(()=>window.svgGeneratedStudio.snapshot());
  await click("Resolve asset conflicts");
  await click("Undo scene change");
  const undone=await page.evaluate(()=>window.svgGeneratedStudio.snapshot());
  await click("Redo scene change");
  const combinedSave=page.getByRole("button",{name:"Save and reload scene",exact:true});
  if(await combinedSave.count()) {
    await combinedSave.click();
  } else {
    const beforePersist=await page.evaluate(()=>window.svgGeneratedStudio.snapshot());
    await click("Save scene in browser");
    await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent?.includes("persisted in browser storage"));
    await page.reload({waitUntil:"networkidle"});
    await page.waitForFunction(()=>window.svgGeneratedStudio);
    await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent?.includes("Persisted scene loaded"));
    const afterPersist=await page.evaluate(()=>window.svgGeneratedStudio.snapshot());
    for(const field of ["documentId","contentHash","assets","instances"])
      if(afterPersist[field]!==beforePersist[field]) throw new Error(JSON.stringify({field,beforePersist,afterPersist}));
  }
  await click("Verify Noto text");
  await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent?.includes("reopened offline"));
  await click("Run Boolean union");
  await page.waitForFunction(()=>document.querySelector("[role=status]")?.textContent?.includes("committed once"));
  await click("Grid snapping");
  await click("Object");
  await click("Freeform");
  await click("Boundary");
  await click("Migrate legacy content");
  const final=await page.evaluate(()=>window.svgGeneratedStudio.snapshot());
  const descriptorValid=await page.evaluate(()=>window.svgGeneratedStudio.descriptorsValid());
  const rendered=await page.locator("[data-fsgg-document-id]").locator("path,rect,ellipse").count();
  if(conflicted.conflicts!==1||undone.conflicts!==1||final.conflicts!==0||final.assets!==2||final.instances!==2||final.entities!==5||final.schema!=="fsgg.svg-scene/1"||!descriptorValid||rendered<3) throw new Error(JSON.stringify({conflicted,undone,final,descriptorValid,rendered}));
  console.log(JSON.stringify({family,result:"passed",conflicted,undone,final,descriptorValid,rendered}));
} finally { await browser.close(); }
