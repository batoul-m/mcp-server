import os
import json
import requests
import urllib.parse
from pathlib import Path
from dotenv import load_dotenv
from fastmcp import FastMCP
from requests.exceptions import HTTPError

# Bootstrap

load_dotenv()
mcp = FastMCP("harri-mcp")

HARRI_API_BASE = os.getenv("HARRI_API_BASE", "").rstrip("/")
HARRI_BEARER = os.getenv("HARRI_BEARER")

BRAND_CONTEXT = {
    "brand_id": 11312118,
    "brand_type": "enterprise",
    "active_brand_id": 11312118,
    "active_brand_type": "enterprise",
}

# Session Setup (Shared for ALL tools & users)

def load_cookie() -> str:
    path = Path("harri_cookie.txt")
    return path.read_text().strip() if path.exists() else ""

session = requests.Session()

session.cookies.set(
    name="h_userContext",
    value=urllib.parse.quote(json.dumps(BRAND_CONTEXT)),
    domain=".harridev.com",
    path="/",
)

session.headers.update({
    "Authorization": f"Bearer {HARRI_BEARER}",
    "Cookie": load_cookie(),
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json",
    "force-csrf": "true",
    "Origin": "https://dev.harridev.com",
    "Referer": "https://dev.harridev.com/",
})

# Shared Helpers (Reusable / Multi-user Safe)

def fetch_all_users(brand_id: str) -> list:
    url = f"https://gateway.harridev.com/team/api/v3/brands/{brand_id}/users"
    r = session.get(url, params={"view": "ALL"}, timeout=20)
    r.raise_for_status()
    return r.json().get("data", [])


def match_users_by_name(users: list, query: str) -> list:
    q = query.lower()
    return [
        u for u in users
        if q in f"{u.get('first_name','')} {u.get('last_name','')}".lower()
    ]


def format_user(user: dict) -> dict:
    return {
        "id": user["id"],
        "first_name": user.get("first_name"),
        "last_name": user.get("last_name"),
        "email": user.get("email"),
        "positions": [p.get("name") for p in user.get("positions", [])],
    }


def get_primary_position(user: dict) -> str | None:
    return user.get("positions", [{}])[0].get("name")


def fetch_timesheet(brand_id: str, user_id: int, day: str, view: str = "week"):
    url = (
        f"https://lpm-aggregator.harridev.com/api/v1/brands/{brand_id}"
        f"/users/{user_id}/timesheets"
    )
    r = session.get(url, params={"day": day, "type": view}, timeout=20)
    r.raise_for_status()
    return r.json()

# MCP TOOLS

@mcp.tool
def harri_list_employees(brand_id: str):
    users = fetch_all_users(brand_id)
    return {
        "count": len(users),
        "employees": [format_user(u) for u in users]
    }


@mcp.tool
def harri_create_timecard(
    brand_id: str,
    employee_name: str,
    day: str,
    clock_in: str,
    clock_out: str,
):
    users = fetch_all_users(brand_id)
    matches = match_users_by_name(users, employee_name)

    if not matches:
        return {
            "status": "user_not_found",
            "query": employee_name,
        }

    if len(matches) > 1:
        return {
            "status": "multiple_matches",
            "count": len(matches),
            "employees": [format_user(u) for u in matches],
            "note": "Multiple users matched. Please select one by ID."
        }

    user = matches[0]
    user_id = user["id"]

    try:
        timesheet = fetch_timesheet(brand_id, user_id, day)

        return {
            "status": "success",
            "employee": f"{user.get('first_name')} {user.get('last_name')}",
            "user_id": user_id,
            "position": get_primary_position(user),
            "date": day,
            "requested_clock_in": clock_in,
            "requested_clock_out": clock_out,
            "timesheet": timesheet,
            "note": "Manual timecard creation is not supported. Timesheet retrieved."
        }

    except HTTPError as e:
        if e.response.status_code == 403:
            return {
                "status": "forbidden",
                "user_id": user_id,
                "reason": "Insufficient permissions",
            }
        raise


@mcp.tool
def harri_list_timesheets(brand_id: str, from_date: str, to_date: str):
    url = (
        f"{HARRI_API_BASE}/reporting-generator/brands/{brand_id}"
        f"/team_live/timesheet/brand/{brand_id}/report"
    )

    r = session.get(
        url,
        params={
            "from_date": from_date,
            "to_date": to_date,
            "hours_format": "DECIMAL",
            "pay_types": ["SALARIED", "HOURLY"],
        },
        timeout=20,
    )
    r.raise_for_status()
    return r.json()

# Run MCP
if __name__ == "__main__":
    mcp.run(transport="stdio")
