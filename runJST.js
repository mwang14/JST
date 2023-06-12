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
var fs = require('fs');
const crawl = require("./crawler/crawl");
var path = require('path');
const args = require('yargs').options('data', {type: 'array', desc: 'the data you want to collect: types, heapLoc, or fields'}).argv
const { exec } = require("child_process");

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Executes a shell command and return it as a Promise.
 * @param cmd {string}
 * @return {Promise<string>}
 */
function execShellCommand(cmd) {
  //const exec = require('child_process').exec;
  return new Promise((resolve, reject) => {
   exec(cmd, (error, stdout, stderr) => {
    if (error) {
     console.warn(error);
    }
    resolve(stdout? stdout : stderr);
   });
  });
 }

var executed_lines = [];
var variable_values = [];


async function collect(url, outputDirectory, data) {
  console.log("collecting");
  if (!fs.existsSync(outputDirectory)){
    fs.mkdirSync(outputDirectory);
  }
  count = 0;

  
  // Use Puppeteer to launch a browser and open a page. For some reason doesn't work in a sandbox
  const browser = await puppeteer.launch({headless: true, args:['--no-sandbox']});
  
  const page = await browser.newPage();
  const session = await page.target().createCDPSession();
  
  var scriptSources = {};
  var foundVariables = []
 
  async function getVars(x) {
    if (x.callFrames[0].url === "__puppeteer_evaluation_script__") {
      await session.send("Debugger.stepInto");
      return;
    }
    try {
      var location = x.callFrames[0].location
      var url = x.callFrames[0].url;
      var outputScriptPath = path.join(outputDirectory, location.scriptId);
      if (!fs.existsSync(outputScriptPath)) {
        var script = await session.send("Debugger.getScriptSource", {scriptId: location.scriptId});
        scriptSources[location.scriptId] = script.scriptSource;
        fs.writeFileSync(outputScriptPath, script.scriptSource);
      }
      var line_called = {"file": url, "scriptId": location.scriptId, "line": location.lineNumber, "column": location.columnNumber};
      var variableBindings = {};
      for (var i = 0; i < x.callFrames.length; i++) {
        let callFrame = x.callFrames[i];
        // each callframe can have multiple scopes, which are returned as an array. 
        for (var j = 0; j < callFrame.scopeChain.length; j++) {
          
          let scope = callFrame.scopeChain[j]
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

            if (!(obj.name in variableBindings)) {
              variableBindings[obj.name] = [];
            }

            if (obj.value !== undefined) {
              var objDetails = {};
              //console.log(scope.startLocation, scope.endLocation);
              scopeInfo = {}
              scopeInfo["startLocation"] = scope.startLocation;
              scopeInfo["endLocation"] = scope.endLocation;
              scopeInfo["scope"] = scope.type;
              objDetails["scopeInfo"] = scopeInfo;
              if (obj.value.type === 'object' && obj.value.objectId !== undefined) {
                //console.log(obj.value.objectId);
                var heapObjectId = await session.send("HeapProfiler.getHeapObjectId", {objectId: obj.value.objectId});
                objDetails["type"] = "object";
                if (obj.value.subtype !== undefined) {
                  objDetails["subtype"] = obj.value.subtype;
                }
                objDetails["className"] = obj.value.className;
                objDetails["heapLocation"] = heapObjectId.heapSnapshotObjectId;
                // skip getting the fields for now.
                if (data.includes("fields")) {
                  var properties = await session.send("Runtime.getProperties", {objectId: obj.value.objectId});
                  propertiesResults = {}
                  for (index in properties.result) {
                    var property = properties.result[index];
                    if (property.value && property.value.type !== "function") {
                      propertiesResults[property.name] = property.value.value;
                    }
                  }
                  objDetails["fields"] = propertiesResults;
                }
              } else if(obj.value.type === "undefined") {
                objDetails["type"] = "undefined";
              } else if (scope.type === "local" && obj.value.type === "function") {
                objDetails["type"] = "function";
              } else  {
                objDetails["type"] = obj.value.type;
                objDetails["value"] = obj.value.value;
              }
              if (typeof variableBindings[obj.name] !== "function") { // short hack for now, need to fix this. make variableBindings a map.
                variableBindings[obj.name].push(objDetails);
              }
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
    scriptMetadata[x.scriptId] = {};
    scriptMetadata[x.scriptId]["startLine"] = x.startLine;
    scriptMetadata[x.scriptId]["startColumn"] = x.startColumn;
  }
  const debugger_enabled = await session.send('Debugger.enable');
  
  session.on('Debugger.paused' , getVars);
  session.on('Debugger.scriptParsed', scriptParsed);
  
  
  await sleep(2000);
  await session.send("HeapProfiler.enable");
  await session.send("HeapProfiler.startTrackingHeapObjects", {trackAllocations: true})
  //console.log("here4");
  
  await session.send("Debugger.pause");
  try {
    await page.goto(url, {timeout: 600000});
  } catch(error){
    console.log("timed out");
  }


  await sleep(5000);
  await browser.close();
  var result = {};
  result["executedLines"] = executed_lines;
  result["variableMappings"] = variable_values;
  fs.writeFileSync(`${outputDirectory}/data.json`, JSON.stringify(result, null, 2) , 'utf-8');
  fs.writeFileSync(`${outputDirectory}/scriptMetadata.json`, JSON.stringify(scriptMetadata, null, 2) , 'utf-8');
  console.log(executed_lines.length, variable_values.length);
  console.log(`tar -czf ${path.dirname(outputDirectory)}/${url.substring(8)}.tar.gz -C ${path.dirname(outputDirectory)} ${outputDirectory.replace(/^.*[\\\/]/, '')}`);
  console.log(`rm -r ${outputDirectory}`);
  await execShellCommand(`tar -czf ${path.dirname(outputDirectory)}/${url.substring(8)}.tar.gz -C ${path.dirname(outputDirectory)} ${outputDirectory.replace(/^.*[\\\/]/, '')}`);

  exec(`rm -r ${outputDirectory}`);
  
}
async function run(website, path, data) {
  console.log("Collecting " + data + " on " + website + " and saving to " + path);
  await collect(website, path, data);

}
function saveFiles() {
  console.log("saving files");
  fs.writeFileSync('/tmp/linesCalled.jsonl', JSON.stringify(executed_lines, null, 2) , 'utf-8');
  fs.writeFileSync('/tmp/variableMappings.jsonl', JSON.stringify(variable_values, null, 2) , 'utf-8');

  console.log(executed_lines.length, variable_values.length);
}

run(args.website, args.outDir, args.data);
//console.log(args);

