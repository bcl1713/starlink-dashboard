# API Error Handling

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)

---

## Overview

Complete guide to error handling in the Starlink Dashboard API. This
documentation has been split into focused sections for easier navigation.

---

## Error Documentation Sections

### [Error Response Format & Status Codes](./errors-format.md)

Standard error response format and HTTP status codes.

**Contents:**

- Error response structure
- Success codes (2xx)
- Client error codes (4xx)
- Server error codes (5xx)

**When to use:** Understanding error structure and HTTP status meanings.

---

### [Common Error Scenarios](./errors-scenarios.md)

Real-world error examples with requests, responses, and solutions.

**Contents:**

- Invalid coordinates
- POI not found
- Duplicate POI name
- Configuration validation errors
- Route errors
- Missing parameters
- Service unavailable

**When to use:** Debugging specific error responses.

---

### [Error Codes Reference](./errors-reference.md)

Complete list of all error codes organized by category.

**Contents:**

- Coordinate errors
- POI errors
- Route errors
- Configuration errors
- Request errors
- Service errors

**When to use:** Looking up specific error codes.

---

### [Error Handling Best Practices](./errors-handling.md)

Client-side error handling patterns and best practices.

**Contents:**

- Python error handling examples
- JavaScript error handling examples
- Retry logic with exponential backoff
- Client-side validation

**When to use:** Implementing robust error handling in your code.

---

### [Troubleshooting Guide](./errors-troubleshooting.md)

Diagnostic steps and solutions for persistent errors.

**Contents:**

- Service health checks
- Debug logging
- Common solutions
- Getting help

**When to use:** Persistent or unexplained errors.

---

## Quick Reference

### Error Response Format

All endpoints return errors in consistent JSON format:

```json
{
  "detail": "Error description",
  "error_code": "INVALID_REQUEST",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

### Common HTTP Status Codes

- `200 OK` - Success
- `400 Bad Request` - Invalid input
- `404 Not Found` - Resource not found
- `409 Conflict` - Duplicate resource
- `422 Unprocessable Entity` - Validation error
- `500 Internal Server Error` - Server error

### Quick Diagnostics

```bash
# Check service health
curl http://localhost:8000/health

# Enable debug logging
LOG_LEVEL=DEBUG docker compose restart starlink-location

# View logs
docker compose logs -f starlink-location
```

---

## Navigation

- [Error Format & Status Codes](./errors-format.md)
- [Common Scenarios](./errors-scenarios.md)
- [Error Codes Reference](./errors-reference.md)
- [Best Practices](./errors-handling.md)
- [Troubleshooting](./errors-troubleshooting.md)
- [Back to API Reference](./README.md)

---

[Back to API Reference](./README.md) | [Back to main docs](../INDEX.md)
