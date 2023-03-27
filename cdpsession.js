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
const util = require('node:util');
count = 0;
var lastScriptLoadedTime = new Date().getTime() / 1000;
var breakpointIDsToLines = {};
var scriptIDsToURLs = {};

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function contains(array, element) {
  for (var i = 0; i < array.length; i++) {
    if (util.isDeepStrictEqual(array[i], element)) {
      return true;
    }
  }
  return false;
}

async function set_breakpoints(session, breakpoints) {
  console.log("setting " + breakpoints.length + " breakpoints.");
  for (var i = 0; i < breakpoints.length; i++) {
    var location = breakpoints[i];
    var scriptId = location.scriptId;
    var lineNumber = location.lineNumber;
    var columnNumber = location.columnNumber;
    try {
      //console.log("setting breakpoint at " + scriptId + " " + lineNumber + " " + columnNumber);
      var breakpoint = await session.send('Debugger.setBreakpoint', {location: {scriptId: scriptId, lineNumber: lineNumber, columnNumber: columnNumber}});
      var breakpointLocation = breakpoint.actualLocation;
      breakpointLocation.script = scriptIDsToURLs[scriptId];
      breakpointIDsToLines[breakpoint.breakpointId] = breakpointLocation
    } catch(err) {
      //console.log(err);
    }
  }
  console.log("Finished setting breakpoints!");
}

(async() => {
  // Use Puppeteer to launch a browser and open a page. For some reason doesn't work in a sandbox
  const browser = await puppeteer.launch({headless: false, args:['--no-sandbox']});
  
  const page = await browser.newPage();
  const session = await page.target().createCDPSession();
  // Get all the breakpoints
  var all_breakpoints = []
  await page.goto('https://alfagroup.csail.mit.edu/');

  async function getAllBreakpoints(x) {
    lastScriptLoadedTime = new Date().getTime() / 1000;
    scriptIDsToURLs[x.scriptId] = x.url;
    const breakpoints = await session.send("Debugger.getPossibleBreakpoints", {start: {scriptId: x.scriptId, lineNumber: 0}});
    all_breakpoints = all_breakpoints.concat(breakpoints.locations);
  }

  async function getHeapObjectId(session, objectId) {

  }
  async function getVars(x) {
    
    if (x.hitBreakpoints !== undefined) {
      breakpoint = x.hitBreakpoints[0];
      console.log(breakpointIDsToLines[breakpoint]);
    }
    //debugger has an array of callframes. hardcoded to get the first one.
    for (var i = 0; i < x.callFrames.length; i++) {
      let callFrame = x.callFrames[i];
      
      // each callframe can have multiple scopes, which are returned as an array. 
      for (var j = 0; j < callFrame.scopeChain.length; j++) {
        let scope = callFrame.scopeChain[j]
        if (scope.type !== 'local') {
          continue;
        }
        //scope.object is the object representing that scope. For local, it contains the variables in that scope. Get the objectId for the scope
        let objId = scope.object.objectId;
        // get the properties from the runtime, which will return the variable values.
        var objects = await session.send("Runtime.getProperties", {objectId: objId});
        for (var i = 0; i < objects.result.length; i++) {
          obj = objects.result[i];
          if (obj.value !== undefined && obj.value.type !== "function") {
            if (obj.value.type === 'object') {
              var heapObjectId = await session.send("HeapProfiler.getHeapObjectId", {objectId: obj.value.objectId});
              console.log(obj.name, heapObjectId);
            }
            //console.log(obj.name, obj.value, scope.type);
          }

        }
      }
    }
    
    
    if (true) {
      await session.send("Debugger.resume");
      count = count+1;
    }
  }
  
  
  
  session.on('Debugger.scriptParsed', getAllBreakpoints);
  session.on('Debugger.paused' , getVars);
  
 
  
  const debugger_enabled = await session.send('Debugger.enable');
  const runtime_enabled = session.send('Runtime.enable'); // not sure if we need to comment this out
  await session.send("HeapProfiler.enable");
  await session.send("HeapProfiler.startTrackingHeapObjects", {trackAllocations: true})
  await sleep(2000);
  while (true) {
    await sleep(2000);
    if (new Date().getTime() / 1000 - lastScriptLoadedTime > 5) {
      break;
    }
    
  }
  /*
  all_breakpoints = all_breakpoints.filter((value, index, self) =>
  index === self.findIndex((t) => (
    value.scriptId === t.scriptId && value.lineNumber === t.lineNumber && value.columnNumber === t.columnNumber
  ))
  )
  console.log(all_breakpoints.length + " after filtering");
  */
  set_breakpoints(session, all_breakpoints);
  //console.log(all_breakpoints[1].locations[0]);
  //const breakpoint = await session.send('Debugger.setBreakpoint', {location: {scriptId: '14', lineNumber: 31}});
  //console.log(breakpoint);
  
  //await browser.close();
})();