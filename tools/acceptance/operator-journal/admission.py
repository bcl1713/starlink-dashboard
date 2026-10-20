"""Reserve a local Linux acceptance project before granting cleanup authority."""

import errno
import hashlib
import socket


class Admission:
    def admit(self):
        # Linux abstract sockets are atomic cross-process reservations, released
        # by the kernel on exit; no unlink race or stale lock file is possible.
        name = (
            "operator-acceptance-" + hashlib.sha256(self.project.encode()).hexdigest()
        )
        reservation = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            reservation.bind("\0" + name)
        except OSError as error:
            reservation.close()
            if error.errno == errno.EADDRINUSE:
                raise RuntimeError("Acceptance project is already reserved") from error
            raise
        self.reservation = reservation
        self.ownership["reservation"] = {"kind": "linux-abstract-socket", "name": name}
        self.persist()
        label = f"label=com.docker.compose.project={self.project}"
        for kind in ("container", "network", "volume"):
            command = ["docker", kind, "ls", "-q"]
            if kind == "container":
                command.append("-a")
            for selector in (label, f"name=^{self.project}[-_]"):
                if self.execute([*command, "--filter", selector], timeout=30).strip():
                    raise RuntimeError(f"Acceptance project is occupied: {kind}")
        for service in ("backend", "frontend"):
            if self.execute(
                [
                    "docker",
                    "image",
                    "ls",
                    "-q",
                    "--filter",
                    f"reference={self.project}-{service}:*",
                ],
                timeout=30,
            ).strip():
                raise RuntimeError("Acceptance project is occupied: image tag")
        self.admitted = True
        self.ownership["admitted"] = True
        self.persist()

    def release(self):
        if self.reservation is not None:
            self.reservation.close()
            self.reservation = None
            self.ownership["reservation"]["released"] = True
            self.persist()
