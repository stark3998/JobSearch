import time
import logging

logger = logging.getLogger(__name__)


def retry_with_backoff(func, max_retries=3, base_delay=5, **kwargs):
    for attempt in range(max_retries):
        try:
            return func(**kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"All {max_retries} attempts failed: {e}")
                return None
            delay = base_delay * (2 ** attempt)
            logger.warning(
                f"Attempt {attempt + 1}/{max_retries} failed: {e}. "
                f"Retrying in {delay}s..."
            )
            time.sleep(delay)
    return None
