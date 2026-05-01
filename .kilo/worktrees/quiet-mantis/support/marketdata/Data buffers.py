import json
import pickle
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import sys

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from support.marketdata.buffers import RollingBuffer


class SerializedRollingBuffers:
    """Manages persistent rolling buffers for M5, M15, H1 timeframes.

    Provides:
    - In-memory RollingBuffer instances for fast access
    - Serialization to JSON (human-readable) or pickle (binary)
    - Loading from disk on startup
    - Automatic persistence hooks
    """

    def __init__(
        self,
        buffer_size: int = 50,
        data_dir: Path = None,
        auto_save: bool = True,
        serialize_format: str = "json"  # "json" or "pickle"
    ):
        """Initialize serialized rolling buffers.

        Args:
            buffer_size: Max candles per buffer (default 50)
            data_dir: Directory to store serialized buffers (default "./data/buffers/")
            auto_save: Automatically save on append (default True)
            serialize_format: "json" for human-readable, "pickle" for compact
        """
        self.buffer_size = buffer_size
        self.data_dir = Path(data_dir) if data_dir else Path("./data/buffers/")
        self.auto_save = auto_save
        self.serialize_format = serialize_format
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Initialize RollingBuffer instances for each timeframe
        self.buffers: Dict[str, RollingBuffer] = {
            "M5": RollingBuffer(maxlen=buffer_size),
            "M15": RollingBuffer(maxlen=buffer_size),
            "H1": RollingBuffer(maxlen=buffer_size),
        }

        # File paths for persistence
        self.filepath_json = self.data_dir / "buffers.json"
        self.filepath_pickle = self.data_dir / "buffers.pkl"

    def append_candle(
        self,
        timeframe: str,
        open_price: float,
        high_price: float,
        low_price: float,
        close_price: float,
        time: str = None,
        volume: int = None,
    ) -> None:
        """Append a candle to the specified timeframe buffer.

        Args:
            timeframe: "M5", "M15", or "H1"
            open_price, high_price, low_price, close_price: OHLC prices
            time: ISO 8601 timestamp (default: current UTC time)
            volume: Trading volume (optional)
        """
        if timeframe not in self.buffers:
            raise KeyError(f"Unknown timeframe: {timeframe}")

        if time is None:
            time = datetime.utcnow().isoformat() + "Z"

        candle = {
            "open": open_price,
            "high": high_price,
            "low": low_price,
            "close": close_price,
            "time": time,
        }
        if volume is not None:
            candle["volume"] = volume

        self.buffers[timeframe].append(candle)

        if self.auto_save:
            self.save()

    def append_dict(self, timeframe: str, candle: Dict[str, Any]) -> None:
        """Append a candle dict to the specified timeframe buffer.

        Args:
            timeframe: "M5", "M15", or "H1"
            candle: Dict with keys: open, high, low, close, time (and optional volume)
        """
        if timeframe not in self.buffers:
            raise KeyError(f"Unknown timeframe: {timeframe}")

        self.buffers[timeframe].append(candle)

        if self.auto_save:
            self.save()

    def get_buffer(self, timeframe: str) -> RollingBuffer:
        """Get the RollingBuffer for a timeframe.

        Args:
            timeframe: "M5", "M15", or "H1"

        Returns:
            RollingBuffer instance
        """
        if timeframe not in self.buffers:
            raise KeyError(f"Unknown timeframe: {timeframe}")
        return self.buffers[timeframe]

    def get_all(self, timeframe: str) -> List[Dict[str, Any]]:
        """Get all candles from a timeframe buffer.

        Args:
            timeframe: "M5", "M15", or "H1"

        Returns:
            List of candle dicts
        """
        return self.buffers[timeframe].all()

    def get_last(self, timeframe: str, n: int = 1) -> List[Dict[str, Any]]:
        """Get the last n candles from a timeframe buffer.

        Args:
            timeframe: "M5", "M15", or "H1"
            n: Number of candles to retrieve

        Returns:
            List of last n candle dicts
        """
        return self.buffers[timeframe].last(n)

    def clear(self, timeframe: Optional[str] = None) -> None:
        """Clear buffers (all or specific timeframe).

        Args:
            timeframe: Specific timeframe to clear, or None to clear all
        """
        if timeframe is None:
            for buf in self.buffers.values():
                buf.clear()
        else:
            if timeframe not in self.buffers:
                raise KeyError(f"Unknown timeframe: {timeframe}")
            self.buffers[timeframe].clear()

        if self.auto_save:
            self.save()

    def save(self) -> None:
        """Serialize and save buffers to disk (JSON or pickle)."""
        data = {
            tf: self.buffers[tf].all() for tf in self.buffers
        }

        if self.serialize_format == "json":
            with open(self.filepath_json, "w") as f:
                json.dump(data, f, indent=2)
        elif self.serialize_format == "pickle":
            with open(self.filepath_pickle, "wb") as f:
                pickle.dump(data, f)
        else:
            raise ValueError(f"Unknown format: {self.serialize_format}")

    def load(self) -> bool:
        """Load serialized buffers from disk.

        Returns:
            True if loaded successfully, False if files don't exist
        """
        filepath = (
            self.filepath_json
            if self.serialize_format == "json"
            else self.filepath_pickle
        )

        if not filepath.exists():
            return False

        try:
            if self.serialize_format == "json":
                with open(filepath, "r") as f:
                    data = json.load(f)
            else:
                with open(filepath, "rb") as f:
                    data = pickle.load(f)

            for timeframe in self.buffers:
                if timeframe in data:
                    self.buffers[timeframe].clear()
                    self.buffers[timeframe].extend(data[timeframe])

            return True
        except Exception as e:
            print(f"Error loading buffers: {e}")
            return False

    def export_to_csv(self, timeframe: str, filepath: Path = None) -> None:
        """Export a timeframe buffer to CSV (open, high, low, close, time).

        Args:
            timeframe: "M5", "M15", or "H1"
            filepath: Output CSV file path (default: data/buffers/{timeframe}.csv)
        """
        if timeframe not in self.buffers:
            raise KeyError(f"Unknown timeframe: {timeframe}")

        if filepath is None:
            filepath = self.data_dir / f"{timeframe}.csv"

        candles = self.buffers[timeframe].all()

        import csv
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(
                f, fieldnames=["time", "open", "high", "low", "close", "volume"]
            )
            writer.writeheader()
            for candle in candles:
                row = {
                    "time": candle.get("time", ""),
                    "open": candle.get("open", ""),
                    "high": candle.get("high", ""),
                    "low": candle.get("low", ""),
                    "close": candle.get("close", ""),
                    "volume": candle.get("volume", ""),
                }
                writer.writerow(row)

    def stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all buffers.

        Returns:
            Dict with timeframe stats (count, oldest_time, newest_time)
        """
        stats = {}
        for tf in self.buffers:
            candles = self.buffers[tf].all()
            stats[tf] = {
                "candle_count": len(candles),
                "oldest_time": candles[0].get("time") if candles else None,
                "newest_time": candles[-1].get("time") if candles else None,
                "buffer_size": self.buffer_size,
            }
        return stats

    def __repr__(self) -> str:
        stats = self.stats()
        lines = ["SerializedRollingBuffers:"]
        for tf, st in stats.items():
            lines.append(
                f"  {tf}: {st['candle_count']} candles "
                f"({st['oldest_time']} - {st['newest_time']})"
            )
        return "\n".join(lines)
