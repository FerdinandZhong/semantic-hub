"""Verify page-memory conversation history against a published finance fixture."""

import argparse
from decimal import Decimal
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--base-url", required=True)
parser.add_argument("--chromium")
parser.add_argument("--output", type=Path, default=Path("/tmp/semantic-v2-browser"))
args = parser.parse_args()
base = args.base_url.rstrip("/")
args.output.mkdir(parents=True, exist_ok=True)

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True, executable_path=args.chromium)
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto(base + "/v2?view=chat&workspace=finance", wait_until="networkidle")
    page.locator("#conversation-list").wait_for()
    assert "This page session" in page.locator(".conversation-history").inner_text()

    page.locator("[data-suggest]").first.click()
    page.locator("[data-run]").click()
    page.locator("#chat-thread td").first.wait_for(timeout=30000)
    expected = Decimal(page.locator("#chat-thread td").first.inner_text())
    assert expected == Decimal("686572.96")
    first_id = page.locator("[data-conversation]").first.get_attribute(
        "data-conversation"
    )
    page.locator("#clear-chat").click()
    assert page.locator("#chat-thread td").count() == 0
    page.locator("[data-suggest]").first.click()
    page.locator("[data-run]").wait_for()
    assert page.locator("[data-conversation]").count() == 2
    # Restoring an archived interpretation must not restore its execution action.
    second_id = page.locator("[data-conversation]").first.get_attribute(
        "data-conversation"
    )
    page.locator(f'[data-conversation="{first_id}"]').click()
    assert Decimal(page.locator("#chat-thread td").first.inner_text()) == expected
    assert page.locator("[data-run]").count() == 0
    page.locator(f'[data-conversation="{second_id}"]').click()
    assert page.locator("[data-run]").count() == 0
    assert page.locator("#chat-thread td").count() == 0

    # Switching workspace uses SPA navigation, so the same memory store survives.
    alternatives = page.locator("#workspace option").evaluate_all(
        '(options) => options.map(option => option.value).filter(id => id && id !== "finance")'
    )
    assert alternatives, "Provide another workspace to verify isolation."
    page.locator("#workspace").select_option(alternatives[0])
    page.wait_for_function('!document.querySelector("[data-conversation]")')
    page.locator("#workspace").select_option("finance")
    page.locator("[data-conversation]").first.wait_for()
    assert page.locator("[data-conversation]").count() == 2
    page.locator(f'[data-conversation="{first_id}"]').click()
    assert Decimal(page.locator("#chat-thread td").first.inner_text()) == expected
    assert page.locator("[data-run]").count() == 0

    for width in (1440, 980, 390):
        page.set_viewport_size({"width": width, "height": 1000})
        assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert page.locator("#chat-form").evaluate("""form => {
          const shell = document.querySelector('.chat-shell').getBoundingClientRect();
          const composer = form.getBoundingClientRect();
          return composer.bottom <= shell.bottom && composer.top >= shell.top;
        }""")
        page.screenshot(
            path=str(args.output / f"chat-history-{width}.png"), full_page=True
        )

    # Published version and hash form separate memory scopes.
    assert page.evaluate("""() => {
      const history = window.HubChatHistory;
      const original = history.key('isolated', 'v1', 'hash-one');
      history.save(original, 'Scope test', '<p>In-memory result</p>');
      return history.list(history.key('isolated', 'v2', 'hash-one')).length === 0 &&
        history.list(history.key('isolated', 'v1', 'hash-two')).length === 0;
    }""")
    page.reload(wait_until="networkidle")
    page.locator("#conversation-list").wait_for()
    assert page.locator("[data-conversation]").count() == 0
    assert not errors, errors
    browser.close()
print(
    "Chat history passed: two conversations, restored result, no stale Run, workspace/version/hash isolation, reload clears memory."
)
