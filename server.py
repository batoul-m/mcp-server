import os
import logging
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


load_dotenv()
logging.basicConfig(level=logging.INFO)

mcp = FastMCP("harri-web-mcp")

HARRI_API_BASE = os.getenv("HARRI_API_BASE", "https://dev.harridev.com/")
HARRI_API_TOKEN = os.getenv("HARRI_API_TOKEN")

if not HARRI_API_TOKEN:
    raise RuntimeError("Missing HARRI_API_TOKEN in .env")


def get_api_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=HARRI_API_BASE,
        headers={
            "Authorization": f"Bearer {HARRI_API_TOKEN}",
            "Content-Type": "application/json",
        },
        timeout=30.0,
    )


@mcp.tool()
async def create_timecard(
    employee_id: str,
    start_time: str,
    end_time: str,
) -> str:

    logging.info("Creating timecard via API")

    payload = {
        "employeeId": employee_id,
        "clockIn": start_time,
        "clockOut": end_time,
        "breaks": {
            "missed": True
        },
        "reason": "Added via AI agent",
    }

    async with get_api_client() as client:
        response = await client.post(
            "/timecards", 
            json=payload,
        )
        response.raise_for_status()
        data = response.json()

    timecard_id = data.get("id", "unknown")

    return f"Timecard created successfully (id={timecard_id})"


@mcp.tool()
async def list_timesheet_reports() -> str:

    logging.info("Fetching timesheet reports via API")

    async with get_api_client() as client:
        response = await client.get(
            "/reports/timesheets",  
            params={"range": "today"},
        )
        response.raise_for_status()
        records = response.json().get("records", [])

    if not records:
        return "No timesheet records found."

    results = []

    for record in records:
        results.append(
            f"- {record.get('employeeName')} | "
            f"{record.get('position')} | "
            f"{record.get('payType')} | "
            f"{record.get('status')} | "
            f"{record.get('totalHours')}h"
        )

    return "\n".join(results)


def main():
    mcp.run(transport="stdio")

if __name__ == "__main__":
    main()