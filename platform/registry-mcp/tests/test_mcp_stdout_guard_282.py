"""#282: a stdio MCP server's stdout carries JSON-RPC only, but a hosted source (e.g. a
user source calling an LLM via LiteLLM) wrote log lines to stdout and corrupted the
stream. registry-mcp now reserves the real stdout for the protocol and routes everything
else to stderr, at the fd level, so even a logging handler that captured the original
stdout stream can't reach it.
"""
import logging
import os
import sys

from registry_mcp.server import (
    IsolatedStdoutFastMCP,
    _quiet_litellm,
    _reserve_stdout_for_protocol,
    mcp,
)


def test_server_uses_the_isolated_transport():
    # The guard is only effective if the live server object actually uses it.
    assert isinstance(mcp, IsolatedStdoutFastMCP)


def test_quiet_litellm_raises_litellm_log_level():
    logging.getLogger("LiteLLM").setLevel(logging.INFO)
    _quiet_litellm()
    assert logging.getLogger("LiteLLM").level >= logging.WARNING


def test_reserve_stdout_keeps_stray_writes_off_the_protocol(capfd):
    """Raw-stdout test: within the guard, only writes to the yielded protocol stream reach
    the real stdout; stray fd-1 writes, prints, and the original stdout object go to
    stderr."""
    with capfd.disabled():  # we drive the fds ourselves
        out_r, out_w = os.pipe()
        err_r, err_w = os.pipe()
        saved1, saved2 = os.dup(1), os.dup(2)
        original_stdout = sys.stdout
        try:
            os.dup2(out_w, 1)
            os.dup2(err_w, 2)
            with _reserve_stdout_for_protocol() as protocol:
                protocol.write("JSONRPC\n")
                protocol.flush()
                os.write(1, b"STRAY_FD1\n")          # raw fd-1 write
                print("STRAY_PRINT", flush=True)      # via sys.stdout
                original_stdout.write("STRAY_ORIG\n")  # a handler holding the old stream
                original_stdout.flush()
        finally:
            os.dup2(saved1, 1)
            os.dup2(saved2, 2)
            os.close(saved1)
            os.close(saved2)
        os.close(out_w)
        os.close(err_w)
        out = os.read(out_r, 8192).decode()
        err = os.read(err_r, 8192).decode()
        os.close(out_r)
        os.close(err_r)

    assert "JSONRPC" in out
    assert "STRAY" not in out                       # nothing stray reached the protocol
    assert "STRAY_FD1" in err and "STRAY_PRINT" in err and "STRAY_ORIG" in err


def test_reserve_stdout_restores_fd_on_exit(capfd):
    with capfd.disabled():
        before = os.fstat(1).st_ino
        with _reserve_stdout_for_protocol():
            pass
        after = os.fstat(1).st_ino
    assert before == after  # fd 1 points back at the original stdout
