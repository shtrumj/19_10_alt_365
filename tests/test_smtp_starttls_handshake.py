import asyncio
import os
import smtplib
import ssl
import sys

import pytest

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from app.smtp_server import EmailHandler, create_ssl_context


@pytest.mark.asyncio
async def test_smtp_starttls_handshake():
    """Ensure SMTP handler upgrades an SMTP connection via STARTTLS."""
    ssl_context = create_ssl_context()
    assert ssl_context is not None

    handler = EmailHandler(ssl_context=ssl_context)
    server = await asyncio.start_server(
        handler.handle_client, host="127.0.0.1", port=0
    )

    try:
        sockets = server.sockets or []
        assert sockets, "SMTP server did not expose any listening sockets"
        port = sockets[0].getsockname()[1]

        def _exercise_client():
            client_ssl = ssl.create_default_context()
            client_ssl.check_hostname = False
            client_ssl.verify_mode = ssl.CERT_NONE

            with smtplib.SMTP("127.0.0.1", port, timeout=5) as client:
                code, _ = client.ehlo()
                assert code == 250
                assert "starttls" in client.esmtp_features

                code, _ = client.starttls(context=client_ssl)
                assert 200 <= code < 300

                code, _ = client.ehlo()
                assert code == 250
                assert "starttls" not in client.esmtp_features

                client.noop()

        await asyncio.to_thread(_exercise_client)
    finally:
        server.close()
        await server.wait_closed()
