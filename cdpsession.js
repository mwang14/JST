/**
 * Copyright 2017 Google Inc. All rights reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

const puppeteer = require('puppeteer');
function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}


(async() => {
  // Use Puppeteer to launch a browser and open a page. For some reason doesn't work in a sandbox
  const browser = await puppeteer.launch({headless: false, args:['--no-sandbox']});
  
  const page = await browser.newPage();
  const session = await page.target().createCDPSession();
  // Get all the breakpoints
  var all_breakpoints = []
  await page.goto('https://googlechrome.github.io/devtools-samples/debug-js/get-started');
  async function getScriptSource(x) {
    const breakpoints = await session.send("Debugger.getPossibleBreakpoints", {start: {scriptId: x.scriptId, lineNumber: 0}});
    all_breakpoints = all_breakpoints.concat(breakpoints);
  }

  async function getVars(x) {
    let objId = x.callFrames[0].scopeChain[0].object.objectId;
    var objects = await session.send("Runtime.getProperties", {objectId: objId});
    console.log(objects);
  }
  

  session.on('Debugger.scriptParsed', getScriptSource);
  session.on('Debugger.paused' , getVars);
 
  const debugger_enabled = await session.send('Debugger.enable');
  const runtime_enabled = await session.send('Runtime.enable');
  await sleep(1000);
  //console.log(all_breakpoints[1]);
  ;
  const breakpoint = await session.send('Debugger.setBreakpoint', {location: {scriptId: '14', lineNumber: 31}})
  console.log(breakpoint);
  //const source = await session.send("Debugger.getScriptSource", {scriptId: '12'});
  
  // Check it out! Fast animations on the "loading..." screen!
  
  //await browser.close();
})();