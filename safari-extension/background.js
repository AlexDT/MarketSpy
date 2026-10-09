// Vangt de klik op de toolbar-knop en laat het content-script de pagina extraheren.
chrome.action.onClicked.addListener(async (tab) => {
  if (!tab.id) return;
  const [result] = await chrome.scripting.executeScript({
    target: { tabId: tab.id },
    func: extractAndSend,
  });
  if (result && result.result) {
    console.log("MarketSpy-helper: verzonden", result.result.status);
  }
});

async function extractAndSend() {
  const url = location.href;
  const isFunda = /funda\.nl\/koop\//.test(url);
  const isAd =
    /marktplaats\.nl\/v\//.test(url) || /2dehands\.be\/v\//.test(url);
  const isProfile =
    /marktplaats\.nl\/(l|u)\//.test(url) || /2dehands\.be\/(l|u)\//.test(url);
  if (!isAd && !isProfile && !isFunda) {
    return { status: "geen advertentie-, profiel- of funda-pagina" };
  }

  const text = (sel) =>
    document.querySelector(sel)?.innerText?.trim() || null;

  if (isFunda) {
    const body = document.body.innerText;
    const prijs = body.match(/€\s?([\d\.]+)\s?(k\.k\.|v\.o\.n\.)?/);
    const data = {
      captured_at: new Date().toISOString(),
      url,
      page_type: "funda",
      title: text("h1") || document.title,
      price: prijs ? `€ ${prijs[1]} ${prijs[2] || ""}`.trim() : null,
      address: text("[data-object-address]") || text("h1"),
      place: (location.pathname.match(/koop\/([^\/]+)/) || [])[1] || null,
      realtor: text("[data-test-id='makelaar-name']") ||
        (body.match(/(?:Makelaar|makelaardij):?\s*([^\n]{3,40})/)||[])[1] || null,
      photos: Array.from(document.querySelectorAll("img[src*='funda'], img[src*='media.funda']"))
        .map((i) => i.src).slice(0, 10),
      raw_text: body.slice(0, 6000),
    };
    const resp = await fetch("http://127.0.0.1:5001/inbox", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    return { status: resp.ok ? "ok" : "server niet bereikbaar" };
  }

  const data = {
    captured_at: new Date().toISOString(),
    url,
    page_type: isAd ? "advertentie" : "profiel_of_lijst",
    title: isAd
      ? text("h1") || document.title
      : document.title,
    price:
      text("[data-testid='listing-price']") ||
      text(".hz-Listing-price") ||
      null,
    condition:
      text("[data-testid='listing-condition']") ||
      text(".hz-Listing-condition") ||
      null,
    description:
      text("[data-testid='listing-description']") ||
      text(".hz-Listing-description") ||
      null,
    place:
      text("[data-testid='listing-location']") ||
      text(".hz-Listing-location") ||
      null,
    ad_number: (url.match(/m(\d{8,})/) || [])[1] || null,
    views: document.body.innerText.match(/(\d+)x\s*bekeken/)?.[1] || null,
    saved: document.body.innerText.match(/(\d+)x\s*bewaard/)?.[1] || null,
    seller: {
      name:
        text("[data-testid='seller-name']") ||
        text(".hz-Seller-name") ||
        text(".seller-name") ||
        null,
      member_since:
        document.body.innerText.match(/sinds\s+(.{3,20})/i)?.[1] || null,
      reviews:
        text("[data-testid='seller-reviews']") ||
        document.body.innerText.match(/(\d+)\s*(reviews?|beoordelingen?)/i)?.[0] ||
        null,
    },
    photos: Array.from(document.querySelectorAll(
      "img[src*='marktplaats'], img[src*='cdn.2dehands'], img[src*='image']"
    ))
      .map((i) => i.src)
      .filter((s) => /cdn|image|marktplaats|2dehands/.test(s))
      .slice(0, 10),
    raw_text: document.body.innerText.slice(0, 6000),
  };

  const resp = await fetch("http://127.0.0.1:5001/inbox", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
  return { status: resp.ok ? "ok" : "server niet bereikbaar" };
}
