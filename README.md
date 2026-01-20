# Harri MCP Server

This project implements a Model Context Protocol (MCP) server that integrates with Harri APIs to manage employees and timecards.  
It was built as a backend integration exercise to understand Harri’s API structure, authentication layers, and security constraints.


## Features

### Employee Listing (Working)

- Successfully retrieves employees for a given brand
- Uses the TEAM API, which is designed for HR-related data
- Fully functional and verified

**Endpoint used:**
```http
GET https://gateway.harridev.com/team/api/v3/brands/{brand_id}/users?view=ALL
```
### Timecard Creation 

The correct timecard API endpoint was identified directly from the Harri UI using browser inspection

The endpoint matches exactly what the web application uses

Endpoint used by UI:
```http
POST https://gateway.harridev.com/lpm-aggregator/api/v1/brands/{brand_id}/users/{user_id}/clocks?day=YYYY-MM-DD&type=day
```

The endpoint was tested:

1) Programmatically via MCP

2) Using curl

3) With headers and cookies copied from the browser session

## Authentication Notes

- Employee listing works correctly with the current credentials
- Timecard creation appears to require:
  - A service-to-service token
  - Explicit labor/payroll permissions
- This behavior is expected for payroll systems, which restrict write operations for security reasons


## MCP Tools
harri_list_employees

Lists all employees for a specific brand.

Input:
```bash
{
  "brand_id": ""
}
```
harri_toggle_timecard

Attempts to create (clock in / clock out) a timecard for a specific employee.
```bash
Input:

{
  "brand_id": "",
  "user_id": "",
  "day": "2026-01-06"
}
```
