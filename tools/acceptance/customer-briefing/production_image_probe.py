"""Run as the application user in the actual production backend image."""

import json
import os
import subprocess
from hashlib import sha256
from pathlib import Path

from app.mission.exporter.customer_runtime import ASSET_ROOT, NODE, RENDERER_ENTRY

assert os.getuid() == 1000, "production entrypoint did not select appuser"
assert subprocess.check_output([NODE, "--version"], text=True).strip() == "v22.22.2"
assert Path(RENDERER_ENTRY).is_file() and not RENDERER_ENTRY.startswith("/app/")
assert Path(ASSET_ROOT, "mission-export.html").is_file()
paths = [
    RENDERER_ENTRY,
    str(Path(ASSET_ROOT, "mission-export.html")),
    os.environ["BRIEFING_APO_PATH"],
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]
result = {
    "uid": os.getuid(),
    "node": "v22.22.2",
    "installedHashes": {
        path: sha256(Path(path).read_bytes()).hexdigest() for path in paths
    },
}
for program in ("pdfinfo", "pdffonts", "pdftotext", "pdftoppm"):
    completed = subprocess.run(
        [program, "-v"], capture_output=True, text=True, check=True, timeout=5
    )
    result[program] = completed.stderr.splitlines()[0]
result["browser"] = json.loads(
    subprocess.check_output(
        [
            NODE,
            "--input-type=commonjs",
            "-e",
            """
const {chromium}=require('/opt/customer-briefing/node_modules/playwright');
(async()=>{let browser;try{
 browser=await chromium.launch({headless:true,args:['--no-sandbox']});
 const context=await browser.newContext(); const page=await context.newPage();
 await page.setContent('<h1>Production browser ready</h1>');
 if(await page.textContent('h1')!=='Production browser ready') throw Error('browser content');
 await context.close(); console.log(JSON.stringify({version:browser.version(),ready:true}));
}finally{if(browser)await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
""",
        ],
        text=True,
        timeout=20,
    )
)
print(json.dumps(result))
