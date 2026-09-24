import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            user_data_dir="/home/will/.config/google-keep-playwright",
            channel="chrome",
            headless=True
        )
        page = await ctx.new_page()
        await page.goto("https://keep.google.com/#LIST/1jId_5SPcn50D6M295jujXu5ztGWk5ol6vmxeG6pRhjSqC0Q33s4hsqhq8dV5Xnc", wait_until="domcontentloaded")
        await asyncio.sleep(4)
        
        data = await page.evaluate('''() => {
            const cards = Array.from(document.querySelectorAll('div.IZ65Hb-n0tgWb'));
            return cards.map(c => {
                const titleEl = c.querySelector('div.IZ65Ce-haAclf, div[role="textbox"]');
                const title = titleEl ? titleEl.innerText.trim() : '';
                const items = Array.from(c.querySelectorAll('div.bVEB4e-rymPhb-ibnC6b')).map(i => {
                    const cb = i.querySelector('div[role="checkbox"]');
                    const checked = cb ? cb.getAttribute('aria-checked') === 'true' : false;
                    const tb = i.querySelector('div[role="textbox"], div[contenteditable="true"]');
                    const text = tb ? tb.innerText.trim() : i.innerText.trim();
                    return { text, checked };
                });
                return { title, itemCount: items.length, items: items.slice(0, 5) };
            });
        }''')
        
        for idx, c in enumerate(data):
            print(f"Card {idx+1}: '{c['title']}' ({c['itemCount']} items)")
            for it in c['items']:
                chk = "[X]" if it['checked'] else "[ ]"
                print(f"   {chk} {it['text']}")
        
        await ctx.close()

if __name__ == "__main__":
    asyncio.run(main())
