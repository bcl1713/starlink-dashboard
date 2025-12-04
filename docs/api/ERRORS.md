# API Error Reference

**Note:** This is a redirect file. The full error documentation has been
preserved.

For the complete error reference (590 lines), see: **[errors.md](./errors.md)**

---

## Quick Error Reference

### Common HTTP Status Codes

| Code | Meaning             | Common Causes                        |
| ---- | ------------------- | ------------------------------------ |
| 400  | Bad Request         | Invalid input, malformed JSON        |
| 404  | Not Found           | Resource doesn't exist               |
| 409  | Conflict            | Resource already exists, state issue |
| 422  | Validation Error    | Failed input validation              |
| 500  | Internal Error      | Server-side error                    |
| 503  | Service Unavailable | Backend not ready                    |

### Quick Troubleshooting

```bash
# Check backend health
curl http://localhost:8000/health

# View backend logs
docker compose logs starlink-location | tail -50

# Check API docs
open http://localhost:8000/docs
```

---

[Full Error Documentation →](./errors.md)

[Back to API Reference](./README.md)
