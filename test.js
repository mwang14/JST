const util = require('node:util');
var fs = require('fs');
var path = require('path')

var arr = {a: 1, b: 2};


function test(dict) {
  dict.blah = 5;
}
function isSubdomain(domain1, domain2) {
  if (domain2.startsWith("www.")) {
      domain2 = domain2.substring(4);
  }
  return domain1.endsWith(domain2);
}

fs.writeFileSync("/tmp/blah", JSON.stringify(arr, null, 2) , 'utf-8');