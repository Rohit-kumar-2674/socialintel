"""Authenticated container readiness check; never prints credentials or case data."""

import os
import sys
from urllib.request import Request, urlopen

try:
    request = Request("http://127.0.0.1:8000/api/settings", headers={
        "Authorization": "Bearer " + os.environ["SOCIALINTEL_API_TOKEN"],
    })
    with urlopen(request, timeout=4) as response:
        sys.exit(0 if response.status == 200 else 1)
except Exception:
    sys.exit(1)
