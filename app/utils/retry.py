import time
import asyncio
import logging
from functools import wraps
from typing import Callable, Any, Tuple, Type

logger = logging.getLogger(__name__)

def retry_async(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    An asynchronous decorator that retries a function with exponential backoff.
    """
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            current_delay = delay
            for attempt in range(retries):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == retries - 1:
                        logger.error(
                            f"Function '{func.__name__}' failed permanently after {retries} attempts. Error: {e}"
                        )
                        raise e
                    logger.warning(
                        f"Attempt {attempt + 1}/{retries} failed for '{func.__name__}': {e}. "
                        f"Retrying in {current_delay:.2f} seconds..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator
