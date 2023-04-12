const puppeteer = require('puppeteer');
const pageScraper = require('./pageScraper');
function sleep(ms) {
	return new Promise(resolve => setTimeout(resolve, ms));
  }

function isSubdomain(domain1, domain2) {
    if (domain2.startsWith("www.")) {
        domain2 = domain2.substring(4);
    }
    return domain1.endsWith(domain2);
}
async function scraper(page, urlOrig){
    var hostDomain = new URL(urlOrig);
    // Get all links
    let urls = await page.$$eval('a', links => {
        links = links.map(el => el.href)
        return links;
    });
    
    var urlTest = new RegExp('^(?:[a-z+]+:)?//', 'i');
    var links = await page.$$('a');
    for (var i = 0; i < 10; i++) {
        console.log("visiting new page");
        if (links.length > 0 ) {
            await sleep(1000);
            var numLinksTried = 0;
            while (numLinksTried < links.length) {
                var random = Math.floor(Math.random() * links.length);
                var url = links[random];
                var href = await url.getProperty('href');
                var href2 = await href.jsonValue();
                if (urlTest.test(href2)) {
                    var domain = new URL(href2);
                    //console.log(domain, hostDomain.hostname);
                    if (domain.hostname === hostDomain.hostname || isSubdomain(domain.hostname, hostDomain.hostname)) {
                        console.log("found hostname that matches");
                        break;
                    }
                } else if (href2.startsWith("/")) {
                    //it's a relative URL
                    break;
                }
                numLinksTried += 1;
            }
            //console.log(numLinksTried, links.length);
            if (numLinksTried === links.length) {
                console.log("broke loop");
                break;
            }
            console.log("clicking " + href2);
            await url.evaluate(l => l.click());
            try {
                //try waiting until it loads, if it doesn't then continue anyways
                await page.waitForNavigation({waitUntil: "networkidle2", timeout: 30000});
            } catch(error) {
                
            }
            console.log("clicked");
            links = await page.$$('a');
        }
    }
    
}

// Pass the browser instance to the scraper controller
async function scrapeAll(url, page){
	let browser;
	try{
        /*
		const browser = await puppeteer.launch({headless: false, args:['--no-sandbox']});
  
        const page = await browser.newPage();
        const session = await page.target().createCDPSession();
        */
		//var url = "https://www.yahoo.com";
		console.log(`Navigating to ${url}...`);
		//await page.goto(url, {waitUntil: "networkidle2"});
		await scraper(page, url);	
		//await browser.close();
	}
	catch(err){
		console.log("Could not resolve the browser instance => ", err);
	}
    
}
module.exports = {scrapeAll};