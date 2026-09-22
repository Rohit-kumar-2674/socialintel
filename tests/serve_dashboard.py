"""Local-only UI test server with synthetic fixtures; never deploy this entry point."""

import os
import tempfile
from pathlib import Path

import httpx
import uvicorn
from conftest import FixtureNetwork, fixture_response
from socialintel.api import create_app
from socialintel.config import Settings

if __name__ == "__main__":
    settings = Settings(
        data_dir=Path(tempfile.mkdtemp(prefix="socialintel-ui-fixture-")),
        token=os.environ["SOCIALINTEL_TEST_TOKEN"],
        allowed_hosts=("127.0.0.1", "localhost"),
        plugins=(),
    )
    application = create_app(settings, network=FixtureNetwork(httpx.MockTransport(fixture_response)))
    uvicorn.run(application, host="127.0.0.1", port=8124, access_log=False)
