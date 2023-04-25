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
const crawl = require("./crawler/crawl");
var path = require('path');


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


var executed_lines = [];
var variable_values = [];
async function collect(url, outputDirectory) {
  console.log("collecting");
  if (!fs.existsSync(outputDirectory)){
    fs.mkdirSync(outputDirectory);
  }
  count = 0;
  var lastScriptLoadedTime = new Date().getTime() / 1000;
  var breakpointIDsToLines = {};
  var scriptIDsToURLs = {};
  var columns = [];

  
  // Use Puppeteer to launch a browser and open a page. For some reason doesn't work in a sandbox
  const browser = await puppeteer.launch({headless: true, args:['--no-sandbox']});
  
  const page = await browser.newPage();
  const session = await page.target().createCDPSession();
  // Get all the breakpoints
  var all_breakpoints = []
  //await page.goto('https://alfagroup.csail.mit.edu/');
  
  var scriptSources = {};
  var foundVariables = []
 
  async function getVars(x) {
    //console.log("hit breakpoint!");
    if (x.callFrames[0].url === "__puppeteer_evaluation_script__") {
      await session.send("Debugger.stepInto");
      return;
    }
    try {
      var location = x.callFrames[0].location
      //console.log(location)
      var url = x.callFrames[0].url;
      //console.log(x.callFrames[0]);
      var outputScriptPath = path.join(outputDirectory, location.scriptId);
      if (!fs.existsSync(outputScriptPath)) {
        var script = await session.send("Debugger.getScriptSource", {scriptId: location.scriptId});
        scriptSources[location.scriptId] = script.scriptSource;
        //console.log(script.scriptSource.split('\n')[location.lineNumber].length);
        //console.log(x.callFrames.length);
        fs.writeFileSync(outputScriptPath, script.scriptSource);
      }
      var line_called = {"file": url, "scriptId": location.scriptId, "line": location.lineNumber, "column": location.columnNumber};
      var variableBindings = {};
      for (var i = 0; i < x.callFrames.length; i++) {
        let callFrame = x.callFrames[i];
        // each callframe can have multiple scopes, which are returned as an array. 
        for (var j = 0; j < callFrame.scopeChain.length; j++) {
          
          let scope = callFrame.scopeChain[j]
          //if (scope.type !== 'local') {
          //  continue;
          //}
          //console.log("not local " + scope.type);
          //scope.object is the object representing that scope. For local, it contains the variables in that scope. Get the objectId for the scope
          let objId = scope.object.objectId;
          // get the properties from the runtime, which will return the variable values.
          var objects = await session.send("Runtime.getProperties", {objectId: objId});
          
          for (var k = 0; k < objects.result.length; k++) {
            
            obj = objects.result[k];
            if (scope.type === 'global') {
              if (!(foundVariables.includes(obj.name) || scriptSources[location.scriptId].includes(obj.name))) {
                continue;
              }
            }
            foundVariables.push(obj.name);
            if (obj.value !== undefined && obj.value.type !== "function") {
              /*
              if (obj.name === "aPageStart") {
                console.log(obj);
              }
              */
              var objDetails = {};
              if (obj.value.type === 'object' && obj.value.objectId !== undefined) {
                //console.log(obj.value.objectId);
                // TODO: Because we don't crash until this line once the browser closes, we have an extra item in executed_lines since that's already pushed.
                var heapObjectId = await session.send("HeapProfiler.getHeapObjectId", {objectId: obj.value.objectId});
                objDetails["type"] = "object";
                if (obj.value.subtype !== undefined) {
                  objDetails["subtype"] = obj.value.subtype;
                }
                //console.log(obj.value.type + " : " + obj.value.className + " : " + obj.value.description);
                objDetails["className"] = obj.value.className;
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
              //console.log(obj.value.type + " : " + obj.value.objectId);
            }
            
          }
        }
      }
      executed_lines.push(line_called);
      variable_values.push(variableBindings);
      
      if (true) {
        await session.send("Debugger.stepInto");
        count = count+1;
      }
  } catch(error) {
    console.log(error);
  }
  }
  
  var scriptMetadata = {};
  async function scriptParsed(x) {
    //console.log(x.scriptId + " has been parsed, url is " + x.url);
    //console.log(x.startLine + " " + x.startColumn);
    scriptMetadata[x.scriptId] = {};
    scriptMetadata[x.scriptId]["startLine"] = x.startLine;
    scriptMetadata[x.scriptId]["startColumn"] = x.startColumn;
  }
  const debugger_enabled = await session.send('Debugger.enable');
  
  session.on('Debugger.paused' , getVars);
  session.on('Debugger.scriptParsed', scriptParsed);
  
  
  await sleep(2000);
  await session.send("HeapProfiler.enable");
  //console.log("here3");
  await session.send("HeapProfiler.startTrackingHeapObjects", {trackAllocations: true})
  //console.log("here4");
  await sleep(1000);
  
  await session.send("Debugger.pause");
  try {
    await page.goto(url, {timeout: 300000});
  } catch(error){
    console.log("timed out");
  }


  //let buttons = await page.$$('button');
  //buttons[0].click();
  await sleep(5000);
  await browser.close();
  var result = {};
  result["executedLines"] = executed_lines;
  result["variableMappings"] = variable_values;
  /*
  fs.writeFileSync(`${outputDirectory}/linesCalled.jsonl`, JSON.stringify(executed_lines, null, 2) , 'utf-8');
  fs.writeFileSync(`${outputDirectory}/variableMappings.jsonl`, JSON.stringify(variable_values, null, 2) , 'utf-8');
  */
  fs.writeFileSync(`${outputDirectory}/data.json`, JSON.stringify(result, null, 2) , 'utf-8');
  fs.writeFileSync(`${outputDirectory}/scriptMetadata.json`, JSON.stringify(scriptMetadata, null, 2) , 'utf-8');
  console.log(executed_lines.length, variable_values.length);
  
}
async function run(website, path) {
  //await collect("https://alfagroup.csail.mit.edu/", "/tmp/alfa");
  console.log("Running on " + website + " and saving to " + path);
  await collect(website, path);

}
function saveFiles() {
  console.log("saving files");
  fs.writeFileSync('/tmp/linesCalled.jsonl', JSON.stringify(executed_lines, null, 2) , 'utf-8');
  fs.writeFileSync('/tmp/variableMappings.jsonl', JSON.stringify(variable_values, null, 2) , 'utf-8');

  console.log(executed_lines.length, variable_values.length);
}

//process.on('exit', saveFiles.bind(null, {cleanup:true}));
//process.on('uncaughtException', saveFiles.bind(null, {cleanup:true}));
run(process.argv[2], process.argv[3]);

