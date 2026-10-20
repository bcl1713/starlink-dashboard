"""Run independent diagnostics completely while preserving a failing overall gate."""

import json


def check_all(root, browser, pdfs):
    report = {"checksPassed": False, "browser": None, "pdfs": {}, "errors": {}}

    def persist():
        (root / "qualification-results.json").write_text(json.dumps(report, indent=2))

    def check(name, operation):
        try:
            return operation()
        except InterruptedError:
            raise
        # Diagnostic boundary: persist every failure, then raise at the gate.
        except Exception as error:  # noqa: BLE001
            report["errors"][name] = str(error)
            (root / (name + "-failure.json")).write_text(
                json.dumps(
                    {
                        "check": name,
                        "errorType": type(error).__name__,
                        "error": str(error),
                    },
                    indent=2,
                )
            )
        finally:
            persist()

    persist()
    report["browser"] = check("browser", browser)
    for name, operation in pdfs.items():
        report["pdfs"][name] = check(name, operation)
    report["checksPassed"] = not report["errors"]
    persist()
    if report["errors"]:
        raise RuntimeError(
            "Production qualification failed: " + ", ".join(report["errors"])
        )
    return report
