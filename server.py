"""
AI Workshop — WebSocket multi-terminal server.

Channels: hermes (bash), cc (claude), codex (codex)
Each channel gets a real PTY. Background task continuously reads PTY output
and broadcasts to all subscribed WebSocket clients.
"""
import os, pty, select, signal, struct, fcntl, termios, asyncio, json, logging

try:
    import websockets
except ImportError:
    raise SystemExit("pip install websockets")

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(message)s")
log = logging.getLogger("workshop")

CHANNELS = {
    "hermes": {"cmd": "/bin/bash", "cwd": "/home/morganbest"},
    "cc":     {"cmd": "claude",    "cwd": "/mnt/e/hermes-work/github-mcp-server"},
    "codex":  {"cmd": "codex",     "cwd": "/mnt/e/hermes-work/github-mcp-server"},
}

# {channel: {"pid": int, "master_fd": int}}
procs = {}
# {channel: set(websocket)} — subscribers per channel
subscribers = {ch: set() for ch in CHANNELS}
subscribers["activity"] = set()  # receives ALL channel output


def set_winsize(fd, cols, rows):
    packed = struct.pack("HHHH", rows, cols, 0, 0)
    fcntl.ioctl(fd, termios.TIOCSWINSZ, packed)


def spawn(channel):
    """Fork a PTY subprocess for channel. Returns {pid, master_fd}."""
    if channel in procs:
        _cleanup(channel)

    info = CHANNELS[channel]
    master, slave = pty.openpty()
    pid = os.fork()

    if pid == 0:
        os.close(master)
        os.setsid()
        for fd in (0, 1, 2):
            os.dup2(slave, fd)
        if slave > 2:
            os.close(slave)
        os.chdir(info["cwd"])
        cmd = info["cmd"]
        os.execvpe(cmd, [cmd], os.environ)

    os.close(slave)
    set_winsize(master, 120, 40)
    procs[channel] = {"pid": pid, "master_fd": master}
    log.info(f"spawned {channel} pid={pid} cmd={info['cmd']}")
    return procs[channel]


def _cleanup(channel):
    proc = procs.pop(channel, None)
    if not proc:
        return
    try:
        os.kill(proc["pid"], signal.SIGTERM)
        os.waitpid(proc["pid"], 0)
    except (OSError, ChildProcessError):
        pass
    try:
        os.close(proc["master_fd"])
    except OSError:
        pass
    log.info(f"cleaned {channel}")


def cleanup_all():
    for ch in list(procs.keys()):
        _cleanup(ch)


async def broadcast(channel, data):
    """Send data to all subscribers of a channel. Also sends to activity subscribers."""
    if not data:
        return
    text = data.decode("utf-8", errors="replace")

    # Send to channel subscribers
    dead = set()
    for ws in subscribers.get(channel, set()):
        try:
            await ws.send(json.dumps({"channel": channel, "output": text}))
        except websockets.exceptions.ConnectionClosed:
            dead.add(ws)
    subscribers[channel] -= dead

    # Also send to activity subscribers
    if "activity" in subscribers and subscribers["activity"]:
        prefix = {"hermes": "⎔", "cc": "○", "codex": "◇"}.get(channel, "▸")
        dead_act = set()
        for ws in subscribers["activity"]:
            try:
                await ws.send(json.dumps({"channel": "activity", "output": f"{prefix} {text}"}))
            except websockets.exceptions.ConnectionClosed:
                dead_act.add(ws)
        subscribers["activity"] -= dead_act


async def pty_reader():
    """Background: read all PTY outputs and broadcast every 50ms."""
    while True:
        for channel, proc in list(procs.items()):
            if not proc:
                continue
            fd = proc["master_fd"]
            try:
                if select.select([fd], [], [], 0)[0]:
                    data = os.read(fd, 65536)
                    if data:
                        await broadcast(channel, data)
            except (OSError, ValueError):
                _cleanup(channel)
        await asyncio.sleep(0.05)


async def handler(ws):
    """WebSocket connection handler."""
    channel = None

    try:
        async for message in ws:
            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                continue

            # Subscribe
            if "channel" in data:
                ch = data["channel"]
                if ch not in CHANNELS and ch != "activity":
                    await ws.send(json.dumps({"error": f"unknown channel: {ch}"}))
                    continue
                # Spawn PTY only for non-activity channels
                if ch != "activity" and ch not in procs:
                    try:
                        spawn(ch)
                    except Exception as e:
                        await ws.send(json.dumps({"error": f"spawn {ch} failed: {e}"}))
                        continue
                channel = ch
                subscribers[channel].add(ws)
                await ws.send(json.dumps({"ok": f"subscribed to {channel}"}))
                log.info(f"client subscribed to {channel}")

            # Resize
            elif "resize" in data and channel:
                r = data["resize"]
                proc = procs.get(channel)
                if proc:
                    set_winsize(proc["master_fd"], r.get("cols", 120), r.get("rows", 40))

            # Input to PTY
            elif "input" in data and channel:
                proc = procs.get(channel)
                if proc:
                    try:
                        os.write(proc["master_fd"], data["input"].encode())
                    except OSError:
                        _cleanup(channel)

    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        if channel:
            subscribers[channel].discard(ws)
            log.info(f"client left {channel}")


async def main():
    signal.signal(signal.SIGCHLD, lambda *_: None)
    signal.signal(signal.SIGINT, lambda *_: cleanup_all())

    log.info("starting on 0.0.0.0:8765")
    async with websockets.serve(handler, "0.0.0.0", 8765):
        await asyncio.gather(
            pty_reader(),
            asyncio.Future(),  # run forever
        )


if __name__ == "__main__":
    asyncio.run(main())
