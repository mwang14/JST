# JST

This repository contains the source code and sample datasetfor the paper __JST: A tool to incorporate dynamic execution information into machine learning models for program analysis__. 

There has been an explosion in using machine learning for programming tasks, ranging from program synthesis to code summarization and similarity at both the source and binary level. Typically, the training data for these models consists only of the static code. Recent work has shown that incorporating runtime execution information into training can greatly improve performance for code models trained on assembly. However, the use of execution information has not been seen for models trained on source code, likely due to the lack of a suitable dataset. JST can generate this dataset by automatically collecting runtime information.  This dataset can be used for many other program analysis tasks, such as alias analysis, escape analysis, and shape analysis -- all of which, to the best of our knowledge, have not yet had any machine learning based solutions. JST automatically instruments client-side Javascript while running a webcrawler to collect runtime information. 

JST works by automatically instrumenting client-side Javascript using Google Chrome's Developer Tools alongside running a webcrawler. JST collects runtime information at each statement that is executed. Similar to prior data curation efforts such as ImageNet, we collect this data by crawling popular websites. We present a dataset of Javascript code from crawling the top 1,000 most popular websites with line-by-line annotations for the runtime information. 

---
`runJST.js` is the script that crawls a website and collects the runtime information. It takes three arguments: 
- __website__: The URL to crawl.
- __outDir__: the directory in which to save the data. 
- __data__: An array of what type of data to collect. Valid options are:
  -  `heapLoc`: Pass this to collect where pointers are pointing to in the heap. 
  - `types`: Pass this to collect the types of arguments.
  - `fields`: Pass this to collect the fields for objects.
  
For example, in order to crawl `https://www.reddit.com` and collect types and heap locations, and then save the results to `/tmp/reddit`, the command would be:

```
node --max-old-space-size=2048 runJST.js --data types heapLoc --website https://www.reddit.com --outDir /tmp/reddit
```
Inside of the output directory (`/tmp/reddit` in this case), `runJST.js` will create several files:
- __data.json__: This is the collected execution information. There are two keys:
  - `executedLines`: A list, where each element is the statement that is executed in order. So the first element is the first statement that is executed, the second element is the second statement, etc.
  Each element is another dictionary with the script, line, and column that is run.
  - `variableMappings`: Another list, which contains the collected information after each line. This includes all the information that is passed as the `data` argument to `runJST.js`.
- __js_files/__: A directory containing all the Javascript files that ran on the website.
- __scriptMetadata.json__: When the script is ran inside of `<script>` tags, the start and end line numbers need an offset. This file contains the offsets for each script. See https://chromedevtools.github.io/devtools-protocol/tot/Debugger/#event-scriptParsed. 

---
Inside of `dataset_generation`, we provide scripts for parsing the collected data.