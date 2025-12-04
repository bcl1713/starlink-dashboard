# Error Response Format & HTTP Status Codes

[Back to API Reference](./README.md) | [Back to errors](./errors.md)

---

## Error Response Format

All endpoints return errors in a consistent JSON format:

```json
{
  "detail": "Error description",
  "error_code": "INVALID_REQUEST",
  "timestamp": "2025-10-31T10:30:00.000000"
}
```

**Fields:**

- `detail`: Human-readable error description
- `error_code`: Machine-readable error identifier (when available)
- `timestamp`: When the error occurred (ISO-8601)

---

## HTTP Status Codes

The API uses standard HTTP status codes to indicate success or failure.

### Success Codes (2xx)

| Code  | Name       | Description                              | Use Case                           |
| ----- | ---------- | ---------------------------------------- | ---------------------------------- |
| `200` | OK         | Request successful                       | GET, POST, PUT operations          |
| `201` | Created    | Resource created successfully            | POST operations                    |
| `204` | No Content | Request successful, no content to return | DELETE operations, empty responses |

### Client Error Codes (4xx)

| Code  | Name                 | Description                              | Use Case                                |
| ----- | -------------------- | ---------------------------------------- | --------------------------------------- |
| `400` | Bad Request          | Invalid input data or parameters         | Validation failures, malformed requests |
| `404` | Not Found            | Requested resource doesn't exist         | POI not found, route not found          |
| `409` | Conflict             | Resource conflict (e.g., duplicate name) | POI name already exists                 |
| `422` | Unprocessable Entity | Semantic validation error                | Invalid coordinate ranges, type errors  |

### Server Error Codes (5xx)

| Code  | Name                  | Description             | Use Case                              |
| ----- | --------------------- | ----------------------- | ------------------------------------- |
| `500` | Internal Server Error | Unexpected server error | System failures, unhandled exceptions |

---

[Back to API Reference](./README.md) | [Back to errors](./errors.md)
