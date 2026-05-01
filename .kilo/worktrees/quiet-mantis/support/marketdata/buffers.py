from collections import deque
from typing import Any, Dict, Iterable, List


class RollingBuffer:
	"""A small rolling buffer wrapper around collections.deque.

	API:
	- append(item)
	- extend(iterable)
	- all() -> list of items
	- last(n) -> list of last n items
	- clear()
	- __len__(), __iter__()
	"""

	def __init__(self, maxlen: int):
		self._dq = deque(maxlen=maxlen)

	def append(self, item: Any) -> None:
		self._dq.append(item)

	def extend(self, items: Iterable[Any]) -> None:
		self._dq.extend(items)

	def all(self) -> List[Any]:
		return list(self._dq)

	def last(self, n: int = 1) -> List[Any]:
		if n <= 0:
			return []
		data = list(self._dq)
		return data[-n:]

	def clear(self) -> None:
		self._dq.clear()

	def __len__(self) -> int:
		return len(self._dq)

	def __iter__(self):
		return iter(self._dq)

	def to_deque(self) -> deque:
		return self._dq


def create_ohlc_buffers_from_config() -> Dict[str, RollingBuffer]:
	"""Create RollingBuffer instances for M5, M15, H1 timeframes.

	Returns a dictionary of pre-initialized RollingBuffer objects.
	"""
	buffers: Dict[str, RollingBuffer] = {}
	for tf in ["M5", "M15", "H1"]:
		buffers[tf] = RollingBuffer(maxlen=50)
	return buffers


def sync_buffers_to_config(buffers: Dict[str, RollingBuffer]) -> None:
	"""No-op placeholder for compatibility.

	In the current architecture, buffers are standalone and don't
	need synchronization with external configs.
	"""
	pass

 