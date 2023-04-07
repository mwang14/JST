const scraperObject = {
	url: 'http://books.toscrape.com',
	async scraper(browser){
		let page = await browser.newPage();
		console.log(`Navigating to ${this.url}...`);
		await page.goto(this.url, {waitUntil: "networkidle2"});
		// Get all links
		let urls = await page.$$eval('a', links => {
			links = links.map(el => el.href)
			return links;
		});
		console.log(urls);
        let buttons = await page.$$('button');
        let links = await page.$$('a');
        //buttons = buttons.map(el => el.innerText);
        //buttons[0].click();
        //console.log(links[0]);
	}
}

module.exports = scraperObject;