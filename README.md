# Harri Web MCP Server

A Model Context Protocol (MCP) server implementation providing programmatic access to Harri's workforce management APIs. This server exposes Harri's employee management, timecard, and timesheet functionality as standardized MCP tools that can be consumed by AI agents and automation frameworks.

## Architecture Overview

### Model Context Protocol (MCP)

This project implements an MCP server using the [FastMCP](https://github.com/jlowin/fastmcp) framework. MCP is a protocol that enables AI applications to securely access external data sources and tools through a standardized interface. The server runs as a stdio-based transport service, communicating via JSON-RPC messages.

### System Architecture

```
┌─────────────────┐
│  MCP Client     │  (AI Agent / Application)
│  (Cursor/Claude)│
└────────┬────────┘
         │ JSON-RPC (stdio)
         │
┌────────▼────────┐
│  MCP Server     │  (server.py)
│  FastMCP        │
└────────┬────────┘
         │
┌────────▼────────┐
│  HTTP Session   │  (requests.Session)
│  Auth Headers   │
│  Cookie Mgmt    │
└────────┬────────┘
         │
┌────────▼────────┐
│  Harri APIs     │
│  - Gateway API  │
│  - LPM API      │
│  - Reporting    │
└─────────────────┘
```

## Technology Stack

### Core Dependencies

- **Python 3.12+**: Required runtime
- **fastmcp**: MCP server framework for rapid tool registration
- **requests**: HTTP client with session management
- **python-dotenv**: Environment variable management
- **mcp[cli]**: MCP protocol implementation and CLI utilities

### Package Management

The project uses [uv](https://github.com/astral-sh/uv) for dependency management. Dependencies are defined in `pyproject.toml` and locked in `uv.lock`.

## Configuration

### Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Harri API Configuration
HARRI_API_BASE=https://gateway.harridev.com  # Base URL for Harri API gateway
HARRI_BEARER=your_bearer_token_here          # OAuth2 Bearer token for API authentication
```

### Authentication Mechanism

The server implements a multi-layered authentication strategy:

1. **Bearer Token Authentication**: Provided via `HARRI_BEARER` environment variable, set in the `Authorization` header
2. **Cookie-based Session**: Loaded from `harri_cookie.txt` file, includes session cookies and CSRF tokens
3. **Brand Context Cookie**: Dynamically set `h_userContext` cookie containing JSON-encoded brand information

#### Brand Context

The server maintains a hardcoded brand context for all requests:

```python
BRAND_CONTEXT = {
    "brand_id": 11312118,
    "brand_type": "enterprise",
    "active_brand_id": 11312118,
    "active_brand_type": "enterprise",
}
```

This context is URL-encoded and set as a cookie for `.harridev.com` domain to maintain session state.

### Cookie File Format

The `harri_cookie.txt` file should contain the raw cookie string as copied from browser developer tools:

```
h_storage-policy-banner=true; __q_state_...; JSESSIONID=node01...
```

## API Integration

### Harri API Endpoints

The server integrates with multiple Harri API services:

#### 1. Team API (Gateway)
- **Base URL**: `https://gateway.harridev.com/team/api/v3`
- **Endpoint**: `/brands/{brand_id}/users`
- **Purpose**: Employee/user data retrieval
- **Authentication**: Bearer token + cookies

#### 2. Labor Productivity Management (LPM) API
- **Base URL**: `https://lpm-aggregator.harridev.com/api/v1`
- **Endpoint**: `/brands/{brand_id}/users/{user_id}/timesheets`
- **Purpose**: Individual timesheet data
- **Query Parameters**: `day` (ISO date), `type` (view: "week", "day", etc.)

#### 3. Reporting Generator API
- **Base URL**: Configured via `HARRI_API_BASE`
- **Endpoint**: `/reporting-generator/brands/{brand_id}/team_live/timesheet/brand/{brand_id}/report`
- **Purpose**: Aggregate timesheet reports
- **Query Parameters**:
  - `from_date`: ISO date string
  - `to_date`: ISO date string
  - `hours_format`: "DECIMAL" or "HH:MM"
  - `pay_types`: Array of ["SALARIED", "HOURLY"]

## MCP Tools

### 1. `harri_list_employees`

Lists all employees for a given brand.

**Parameters:**
- `brand_id` (string): Brand identifier

**Returns:**
```json
{
  "count": 42,
  "employees": [
    {
      "id": 12345,
      "first_name": "John",
      "last_name": "Doe",
      "email": "john.doe@example.com",
      "positions": ["Server", "Bartender"]
    }
  ]
}
```

**Implementation Details:**
- Fetches all users with `view=ALL` parameter
- Transforms raw API response using `format_user()` helper
- Returns structured employee data with position information

### 2. `harri_create_timecard`

Attempts to create/retrieve a timecard for an employee by name.

**Parameters:**
- `brand_id` (string): Brand identifier
- `employee_name` (string): Full or partial employee name
- `day` (string): ISO date string (YYYY-MM-DD)
- `clock_in` (string): Clock-in time (not currently implemented)
- `clock_out` (string): Clock-out time (not currently implemented)

**Returns:**
```json
{
  "status": "success",
  "employee": "John Doe",
  "user_id": 12345,
  "position": "Server",
  "date": "2026-01-11",
  "requested_clock_in": "09:00",
  "requested_clock_out": "17:00",
  "timesheet": { /* raw timesheet data */ },
  "note": "Manual timecard creation is not supported. Timesheet retrieved."
}
```

**Error Responses:**
- `user_not_found`: No employees matched the query
- `multiple_matches`: Multiple employees matched (disambiguation required)
- `forbidden`: Insufficient permissions (403 error)

**Implementation Details:**
- Uses fuzzy name matching via `match_users_by_name()` helper
- Case-insensitive substring matching on `first_name` + `last_name`
- Currently read-only: retrieves existing timesheet data only
- Manual timecard creation is not implemented in the API

### 3. `harri_list_timesheets`

Retrieves aggregated timesheet reports for a date range.

**Parameters:**
- `brand_id` (string): Brand identifier
- `from_date` (string): Start date in ISO format (YYYY-MM-DD)
- `to_date` (string): End date in ISO format (YYYY-MM-DD)

**Returns:**
Raw JSON response from Harri reporting API (structure varies by API version)

**Implementation Details:**
- Uses configured `HARRI_API_BASE` for endpoint construction
- Automatically sets `hours_format` to "DECIMAL"
- Filters by both "SALARIED" and "HOURLY" pay types
- 20-second timeout on requests

## Session Management

### Shared Session Architecture

The server uses a **single, shared `requests.Session()` instance** for all requests. This design:

- Maintains persistent connections for performance
- Preserves cookies across multiple requests
- Allows centralized header management
- Is **multi-user safe** (session state is brand-scoped, not user-scoped)

### Request Headers

All requests include standardized headers:

```python
{
    "Authorization": f"Bearer {HARRI_BEARER}",
    "Cookie": load_cookie(),
    "Content-Type": "application/json;charset=UTF-8",
    "Accept": "application/json",
    "force-csrf": "true",
    "Origin": "https://dev.harridev.com",
    "Referer": "https://dev.harridev.com/",
}
```

The `force-csrf` header indicates CSRF protection bypass for API access.

## Helper Functions

### User Management Helpers

- **`fetch_all_users(brand_id: str) -> list`**: Fetches complete user list from Team API
- **`match_users_by_name(users: list, query: str) -> list`**: Performs fuzzy name matching
- **`format_user(user: dict) -> dict`**: Transforms API response to standardized format
- **`get_primary_position(user: dict) -> str | None`**: Extracts primary position name

### Timesheet Helpers

- **`fetch_timesheet(brand_id: str, user_id: int, day: str, view: str = "week")`**: Retrieves individual timesheet data
- **`load_cookie() -> str`**: Reads cookie file from filesystem

## Installation & Setup

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager

### Installation Steps

1. **Clone the repository:**
   ```bash
   cd harri_web_mcp
   ```

2. **Install dependencies using uv:**
   ```bash
   uv sync
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env  # If exists, or create manually
   # Edit .env with your Harri API credentials
   ```

4. **Obtain authentication cookie:**
   - Log into Harri dev environment
   - Extract cookies from browser developer tools
   - Save to `harri_cookie.txt`

5. **Verify installation:**
   ```bash
   uv run python server.py
   ```

## Running the MCP Server

### Direct Execution

```bash
uv run python server.py
```

The server runs in stdio mode, expecting JSON-RPC messages on stdin and writing responses to stdout.

### Node.js Wrapper

A Node.js wrapper script (`wrapper.js`) is provided for environments requiring process spawning:

```bash
node wrapper.js
```

The wrapper spawns the Python process with proper stdio pipes and environment inheritance.

### Integration with MCP Clients

Configure your MCP client (e.g., Cursor, Claude Desktop) to execute:

```json
{
  "command": "python",
  "args": ["/path/to/server.py"],
  "cwd": "/path/to/harri_web_mcp"
}
```

Or use the Node.js wrapper:

```json
{
  "command": "node",
  "args": ["/path/to/wrapper.js"]
}
```

## Error Handling

### HTTP Error Responses

The server implements structured error handling:

- **403 Forbidden**: Returned when user lacks permissions
- **401 Unauthorized**: Authentication failure (check `HARRI_BEARER` and cookies)
- **HTTPError**: Other HTTP errors are re-raised for MCP client handling

### User Matching Errors

- **No matches**: Returns `status: "user_not_found"`
- **Multiple matches**: Returns `status: "multiple_matches"` with candidate list for disambiguation

## Development

### Project Structure

```
harri_web_mcp/
├── server.py              # Main MCP server implementation
├── main.py                # Entry point (placeholder)
├── wrapper.js             # Node.js process wrapper
├── pyproject.toml         # Python project configuration
├── uv.lock                # Dependency lock file
├── .env                   # Environment variables (not in git)
├── harri_cookie.txt       # Session cookies (not in git)
└── README.md              # This file
```

### Adding New Tools

To add a new MCP tool:

1. Define the tool function with type hints:
   ```python
   @mcp.tool
   def harri_new_tool(param1: str, param2: int):
       # Implementation
       return result
   ```

2. FastMCP automatically exposes the function via the `@mcp.tool` decorator
3. Function signatures are introspected for parameter validation

### Testing

Test individual components:

```python
# Test user fetching
from server import fetch_all_users
users = fetch_all_users("11312118")

# Test name matching
from server import match_users_by_name
matches = match_users_by_name(users, "John")
```

## Security Considerations

1. **Credentials**: Never commit `.env` or `harri_cookie.txt` to version control
2. **Session Cookies**: Cookies expire and may need periodic refresh
3. **Brand Context**: Hardcoded brand ID limits server to single brand (consider parameterization)
4. **Multi-tenancy**: Current implementation uses shared session (safe for single-brand use)

## Limitations

- **Timecard Creation**: Not implemented; tool only retrieves existing timesheets
- **Single Brand**: Brand ID is hardcoded in `BRAND_CONTEXT`
- **Cookie Dependency**: Requires manual cookie extraction from browser
- **Error Recovery**: Limited retry logic for transient failures

