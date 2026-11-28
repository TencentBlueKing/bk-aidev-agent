import asyncio
import json
import ssl
import subprocess

from aidev_agent_adapter import runner as runner_module
from aidev_agent_adapter.runner import send_frame, serve_runner
from websockets.asyncio.server import serve


async def test_runner_opens_session_and_resumes_on_separate_socket(adapter, tmp_path, monkeypatch):
    cert = tmp_path / "localhost.pem"
    key = tmp_path / "localhost.key"
    subprocess.run(
        [
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    monkeypatch.setenv("SSL_CERT_FILE", str(cert))
    monkeypatch.setenv("no_proxy", "localhost,127.0.0.1")
    tls = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    tls.load_cert_chain(cert, key)
    ticket = tmp_path / "ticket"
    ticket.write_text("runner-test")
    connections = asyncio.Queue()

    async def accept(ws):
        await connections.put(ws)
        await ws.wait_closed()

    async with serve(accept, "127.0.0.1", 0, ssl=tls) as server:
        base = f"wss://localhost:{server.sockets[0].getsockname()[1]}"
        runner = asyncio.create_task(serve_runner(adapter, base + "/runner", ticket, "instance"))
        try:
            async with asyncio.timeout(12):
                control = await connections.get()
                assert json.loads(await control.recv()) == {
                    "type": "runner.register",
                    "sandbox_id": "instance",
                    "ticket": "runner-test",
                }
                await send_frame(control, "runner.ready", epoch=1)

                async def open_session(session_code):
                    await send_frame(
                        control,
                        "session.open",
                        epoch=1,
                        session_code=session_code,
                        ticket="session-test",
                        url=base + "/session",
                    )
                    session = await connections.get()
                    assert json.loads(await session.recv()) == {
                        "type": "session.register",
                        "epoch": 1,
                        "session_code": session_code,
                        "ticket": "session-test",
                    }
                    await send_frame(session, "session.ready", epoch=1)
                    return session

                first = await open_session("thread")
                await send_frame(first, "chat.submit", run_id="run", text="hello")
                started = json.loads(await first.recv())
                assert started["event"]["type"] == "RUN_STARTED"
                await first.close()
                other = await open_session("another")
                await send_frame(other, "chat.resume", run_id="run", after=1)
                assert json.loads(await other.recv())["type"] == "session.unknown"
                resumed = await open_session("thread")
                await send_frame(resumed, "chat.resume", run_id="run", after=started["sequence"])
                sequence = started["sequence"]
                while True:
                    frame = json.loads(await resumed.recv())
                    sequence += 1
                    assert frame["sequence"] == sequence
                    assert frame["eventId"] == f"run:{sequence}"
                    if frame["event"]["type"] == "RUN_FINISHED":
                        break
        finally:
            runner.cancel()
            await asyncio.gather(runner, return_exceptions=True)


async def test_busy_control_connection_still_sends_heartbeats(tmp_path, monkeypatch):
    interval = 0.05
    messages = asyncio.Queue()

    class BusyControl:
        registered = False

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def send(self, raw):
            await messages.put(json.loads(raw))

        async def recv(self):
            if not self.registered:
                self.registered = True
                return json.dumps({"type": "runner.ready", "epoch": 3})
            await asyncio.sleep(interval / 10)
            return json.dumps({"type": "session.open", "epoch": 2})

    monkeypatch.setattr(runner_module, "HEARTBEAT_INTERVAL", interval)
    monkeypatch.setattr(runner_module, "DirectConnection", lambda *args, **kwargs: BusyControl())
    ticket = tmp_path / "ticket"
    ticket.write_text("test-ticket")
    task = asyncio.create_task(serve_runner(None, "wss://channel.example/runner", ticket, "instance"))
    try:
        assert (await asyncio.wait_for(messages.get(), 1))["type"] == "runner.register"
        for _ in range(2):
            assert await asyncio.wait_for(messages.get(), 1) == {"type": "runner.heartbeat", "epoch": 3}
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
