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
var fs = require('fs');


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



async function collect(url) {
  count = 0;
  var lastScriptLoadedTime = new Date().getTime() / 1000;
  var breakpointIDsToLines = {};
  var scriptIDsToURLs = {};
  var columns = [];

  var executed_lines = [];
  var variable_values = [];
  // Use Puppeteer to launch a browser and open a page. For some reason doesn't work in a sandbox
  const browser = await puppeteer.launch({headless: false, args:['--no-sandbox']});
  
  const page = await browser.newPage();
  const session = await page.target().createCDPSession();
  // Get all the breakpoints
  var all_breakpoints = []
  //await page.goto('https://alfagroup.csail.mit.edu/');
  await page.goto(url);
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
        breakpointLocation.scriptId = scriptId;
        breakpointIDsToLines[breakpoint.breakpointId] = breakpointLocation
        //console.log(scriptIDsToURLs[scriptId]);
        //if (scriptIDsToURLs[scriptId] === "http://localhost:1234/test.js" ) {
          columns.push(lineNumber + " " + columnNumber);
        //}
      } catch(err) {
        //console.log(err);
      }
    }
    console.log("Finished setting breakpoints!");
  }

  async function getAllBreakpoints(x) {
    lastScriptLoadedTime = new Date().getTime() / 1000;
    scriptIDsToURLs[x.scriptId] = x.url;
    var script = await session.send("Debugger.getScriptSource", {scriptId: x.scriptId});
    fs.writeFileSync(`/tmp/scripts/${x.scriptId}`, script.scriptSource);
    const breakpoints = await session.send("Debugger.getPossibleBreakpoints", {start: {scriptId: x.scriptId, lineNumber: 0}});
    all_breakpoints = all_breakpoints.concat(breakpoints.locations);
  }

  async function getVars(x) {
    if (x.hitBreakpoints === undefined) {
      await session.send("Debugger.resume");
      return;
    }

    //debugger has an array of callframes. hardcoded to get the first one.
    var breakpoint = breakpointIDsToLines[x.hitBreakpoints[0]];
    var line_called = {"file": breakpoint.script, "scriptId": breakpoint.scriptId, "line": breakpoint.lineNumber, "column": breakpoint.columnNumber};
    executed_lines.push(line_called);
    var variableBindings = {};
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
        
        for (var k = 0; k < objects.result.length; k++) {
          
          obj = objects.result[k];
          if (obj.value !== undefined && obj.value.type !== "function") {
            var objDetails = {};
            if (obj.value.type === 'object') {
              var heapObjectId = await session.send("HeapProfiler.getHeapObjectId", {objectId: obj.value.objectId});
              objDetails["type"] = "object";
              objDetails["heapLocation"] = heapObjectId.heapSnapshotObjectId;
              var properties = await session.send("Runtime.getProperties", {objectId: obj.value.objectId});
              propertiesResults = {}
              for (index in properties.result) {
                var property = properties.result[index];
                if (property.value && property.value.type !== "function") {
                  propertiesResults[property.name] = property.value.value;
                }
              }
              objDetails["fields"] = propertiesResults;
              //console.log(obj.name, heapObjectId.heapSnapshotObjectId, breakpoint.script, breakpoint.lineNumber, breakpoint.columnNumber, x.hitBreakpoints[0]);
            } else if(obj.value.type === "undefined") {
              objDetails["type"] = "undefined";
              //console.log(obj.name, 'undefined');
            } else  {
              objDetails["type"] = obj.value.type;
              objDetails["value"] = obj.value.value;
              //console.log(obj.name, obj.value.value);
            }
            variableBindings[obj.name] = objDetails;
          }
          
        }
      }
    }
    variable_values.push(variableBindings);
    if (true) {
      await session.send("Debugger.resume");
      count = count+1;
    }
  }
  
  session.on('Debugger.scriptParsed', getAllBreakpoints);
  session.on('Debugger.paused' , getVars);
  
  const debugger_enabled = await session.send('Debugger.enable');
  const runtime_enabled = await session.send('Runtime.enable'); // not sure if we need to comment this out
  await session.send("HeapProfiler.enable");
  await session.send("HeapProfiler.startTrackingHeapObjects", {trackAllocations: true})
  await sleep(2000);
  while (true) {
    await sleep(2000);
    if (new Date().getTime() / 1000 - lastScriptLoadedTime > 5) {
      break;
    }
    
  }
  
  await set_breakpoints(session, all_breakpoints);
  await sleep(1000);
  
  let buttons = await page.$$('button');
  buttons[0].click();
  await sleep(2000);
  await browser.close();
  fs.writeFileSync('/tmp/linesCalled.jsonl', JSON.stringify(executed_lines, null, 2) , 'utf-8');
  fs.writeFileSync('/tmp/variableMappings.jsonl', JSON.stringify(variable_values, null, 2) , 'utf-8');
  
}

collect("http://localhost:1234");
function saveFiles() {
  fs.writeFileSync('/tmp/linesCalled.jsonl', JSON.stringify(executed_lines, null, 2) , 'utf-8');
  fs.writeFileSync('/tmp/variableMappings.jsonl', JSON.stringify(variable_values, null, 2) , 'utf-8');

  console.log(executed_lines.length, variable_values.length);
}

//process.on('exit', saveFiles.bind(null, {cleanup:true}));