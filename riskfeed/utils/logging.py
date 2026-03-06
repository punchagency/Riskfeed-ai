import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger("riskfeed")
logger.setLevel(logging.INFO)

_handler = logging.StreamHandler()
_handler.setLevel(logging.INFO)
logger.addHandler(_handler)


def log_event(event: str, payload: Dict[str, Any]) -> None:
    """Structured log line as JSON for easy parsing"""
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **payload,
    }
    logger.info(json.dumps(record, default=str))