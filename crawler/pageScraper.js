function sleep(ms) {
	return new Promise(resolve => setTimeout(resolve, ms));
  }

const scraperObject = {
	async scraper(page, url){
		/*
		let page = await browser.newPage();
		var hostDomain = new URL(this.url);
		console.log(`Navigating to ${this.url}...`);
		await page.goto(this.url, {waitUntil: "networkidle2"});
		*/
		var hostDomain = new URL(url);
		// Get all links
		let urls = await page.$$eval('a', links => {
			links = links.map(el => el.href)
			return links;
		});
		//console.log(urls);
        //let buttons = await page.$$('button');
        
        //buttons = buttons.map(el => el.innerText);
		//for (var i = 0; i < buttons.length; i++) {
		//	await buttons[i].evaluate(b => b.click());
		//}
		
        //buttons[0].click();
		var urlTest = new RegExp('^(?:[a-z+]+:)?//', 'i');
		var links = await page.$$('a');
		for (var i = 0; i < 5; i++) {
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
						console.log(domain.hostname, hostDomain.hostname);
						if (domain.hostname === hostDomain.hostname || domain.hostname.endsWith(hostDomain.hostname)) {
							console.log("found hostname that matches");
							break;
						}
					} else if (href2.startsWith("/")) {
						//it's a relative URL
						break;
					}
					numLinksTried += 1;
				}
				console.log(numLinksTried, links.length);
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
}

module.exports = scraperObject;