import os
import logging
from dotenv import load_dotenv
from playwright.async_api import async_playwright
from mcp.server.fastmcp import FastMCP


load_dotenv()
logging.basicConfig(level=logging.INFO)

mcp = FastMCP("harri-web-mcp")

EMAIL = os.getenv("HARRI_EMAIL")
PASSWORD = os.getenv("HARRI_PASSWORD")

if not EMAIL or not PASSWORD:
    raise RuntimeError("Missing HARRI_EMAIL or HARRI_PASSWORD in .env")


async def login(page):
    """Login to Harri and launch the first available location."""

    logging.info("Logging into Harri...")

    await page.goto(
        "https://dev.harridev.com/user/login",
        wait_until="domcontentloaded",
        timeout=60000,
    )

    await page.wait_for_selector(
        'input[placeholder="Email address or phone number"]',
        timeout=60000,
    )
    await page.fill(
        'input[placeholder="Email address or phone number"]',
        EMAIL,
    )
    await page.fill(
        'input[placeholder="Password"]',
        PASSWORD,
    )
    await page.click('button:has-text("Log in")')

    await page.wait_for_selector("text=My locations", timeout=60000)
    logging.info("Selecting location...")

    context = page.context
    pages_before = context.pages

    await page.click('button:has-text("Launch")')


    for _ in range(30):
        await page.wait_for_timeout(500)

        pages_after = context.pages
        if len(pages_after) > len(pages_before):
            new_page = pages_after[-1]
            await new_page.wait_for_load_state("domcontentloaded")
            logging.info("Location opened in new tab")
            return new_page

        if "access-portal" not in page.url:
            await page.wait_for_load_state("domcontentloaded")
            logging.info("Location opened in same tab")
            return page

    raise RuntimeError("Failed to launch location")


@mcp.tool()
async def create_timecard(
    employee_name: str,
    start_time: str,
    end_time: str,
) -> str:
    """
    Create a timecard for an employee in Harri.

    Args:
        employee_name: Full employee name as shown in Harri.
        start_time: Shift start time (e.g. 09:00 am).
        end_time: Shift end time (e.g. 05:00 pm).
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        page = await login(page)

        await page.goto(
            "https://dev.harridev.com/clock-time/timesheet?tab=ALL",
            timeout=60000,
        )
        await page.wait_for_selector("text=Timesheet", timeout=60000)

        await page.wait_for_selector(
            'text=/Add (a new )?time card/i',
            timeout=60000,
        )
        await page.click('text=/Add (a new )?time card/i')

        await page.wait_for_selector(
            ".manage-shift-form-loading",
            state="hidden",
            timeout=60000,
        )

        employee_field = page.locator(
            '[automation="timesheetAddShiftModal"] .field:has-text("Employee")'
        ).first

        await employee_field.wait_for(state="visible", timeout=60000)
        await employee_field.click()
        await page.keyboard.type(employee_name)
        await page.wait_for_timeout(800)
        await page.keyboard.press("Enter")

        position_field = page.locator(
            '[automation="timesheetAddShiftModal"] .field:has-text("Position")'
        ).first

        await position_field.wait_for(state="visible", timeout=60000)
        await position_field.click()
        await page.keyboard.press("ArrowDown")
        await page.keyboard.press("Enter")

        time_inputs = await page.query_selector_all(
            'input[placeholder="hh:mm a"]'
        )

        await time_inputs[0].click()
        await page.keyboard.type(start_time)
        await page.keyboard.press("Enter")

        await time_inputs[1].click()
        await page.keyboard.type(end_time)
        await page.keyboard.press("Enter")

        await page.wait_for_selector("text=Allowed breaks", timeout=60000)

        yes_buttons = page.locator(
            '[automation="timesheetAddShiftModal"] '
            'button:has-text("Yes"), '
            '[automation="timesheetAddShiftModal"] a:has-text("Yes")'
        )

        count = await yes_buttons.count()
        for i in range(count):
            await yes_buttons.nth(i).click()
            await page.wait_for_timeout(300)

        reason_field = page.locator(
            '[automation="timesheetAddShiftModal"] .field:has-text("Choose reason")'
        ).first

        await reason_field.click()
        await page.keyboard.press("ArrowDown")
        await page.keyboard.press("Enter")

        await page.fill(
            'textarea[placeholder="Start typing your message here..."]',
            "Added via MCP automation",
        )

        await page.click('button:has-text("Create")')
        await page.wait_for_timeout(3000)

        await browser.close()

    return f"Timecard created for {employee_name} ({start_time} → {end_time})"


@mcp.tool()
async def list_timesheet_reports() -> str:
    """List timesheet records from Harri Reports page."""

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()

        page = await login(page)

        await page.goto(
            "https://dev.harridev.com/reporting/time-sheet-report",
            timeout=60000,
        )
        await page.wait_for_selector("text=Enterprise reports", timeout=60000)

        apply_button = page.locator('button:has-text("Apply")')
        if await apply_button.is_visible():
            await apply_button.click()

        await page.wait_for_selector(
            'text=There are no records to display|table',
            timeout=60000,
        )

        if await page.locator(
            'text=There are no records to display'
        ).is_visible():
            await browser.close()
            return "No timesheet records found."

        rows = page.locator("table tbody tr")
        count = await rows.count()

        results = []

        for i in range(count):
            row = rows.nth(i)
            cells = row.locator("td")

            employee = await cells.nth(3).inner_text()
            position = await cells.nth(2).inner_text()
            pay_type = await cells.nth(4).inner_text()
            status = await cells.nth(5).inner_text()
            total_hours = await cells.nth(6).inner_text()

            results.append(
                f"- {employee.strip()} | {position.strip()} | "
                f"{pay_type.strip()} | {status.strip()} | {total_hours.strip()}h"
            )

        await browser.close()
        return "\n".join(results)


def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()