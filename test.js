const util = require('node:util');
var fs = require('fs');

arr = [{a: 1, b: 2},{a:1, b:3}, {a: 1, b: 2}]


arr = arr.filter((value, index, self) =>
  index === self.findIndex((t) => (
    util.isDeepStrictEqual(value, t)
  ))
)

function test(dict) {
  dict.blah = 5;
}
function isSubdomain(domain1, domain2) {
  if (domain2.startsWith("www.")) {
      domain2 = domain2.substring(4);
  }
  return domain1.endsWith(domain2);
}

console.log(isSubdomain("hr.ikipedia.org", "www.wikipedia.org"));