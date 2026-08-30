import subprocess
import uuid


class PersistentShell:
    """A single long-lived bash process so cd/env/aliases persist between
    lines, just like a normal interactive shell."""

    def __init__(self):
        self.proc = subprocess.Popen(
            ["bash", "--norc", "--noprofile"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

    def run(self, line: str):
        """Execute one line, return (output, exit_code)."""
        marker = f"__MINIAI_DONE_{uuid.uuid4().hex}__"
        self.proc.stdin.write(line + "\n")
        self.proc.stdin.write(f'echo "{marker}$?"\n')
        self.proc.stdin.flush()

        output = []
        exit_code = 0
        while True:
            out_line = self.proc.stdout.readline()
            if out_line == "":
                break
            if out_line.startswith(marker):
                exit_code = int(out_line[len(marker):].strip())
                break
            output.append(out_line)
        return "".join(output), exit_code

    def cwd(self) -> str:
        output, _ = self.run("pwd")
        return output.strip()

    def alive(self) -> bool:
        return self.proc.poll() is None

    def close(self):
        if self.alive():
            try:
                self.proc.stdin.write("exit\n")
                self.proc.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            self.proc.terminate()
