"""

Example Usage:

    import faust

    BLACKLIST = {'KP'}

    class Event(faust.Event):
        account: str
        user: str
        country: str


    class Withdrawal(faust.Event):
        amount: Decimal

    all_events = faust.topic(r'.*', type=Event)
    withdrawals = faust.topic(r'withdrawal\..*', type=Withdrawal)

    @forver.stream(all_events, group_by=Event.user)
    def suspicious_countries(it: StreamT) -> StreamT:
        return (event for event if event.country in BLACKLIST)

    @faust.aggregate_count(withdrawals, timedelta(days=2))
    def user_withdrawals(withdrawal: Withdrawl) -> Tuple[str, Decimal]:
        return withdrawal.user, withdrawal.amount

    @faust.task()
    def suspicious_users() -> StreamT:
        for event in (suspicious_countries.field.user &
                      user_withdrawals.field.user):
            if event.withdrawal.amount > 500:
                yield


    async def main():
        worker = faust.Worker()
        worker.add_task(suspicious_users)
        await worker.start()

        suspicious_events[userid]  # Can use as dictionary
        user_withdrawals[userid]   # Same with tables
"""
import asyncio
from collections import OrderedDict
from typing import MutableMapping, Pattern, Sequence, List
from itertools import count
from . import constants
from .consumer import Consumer
from .stream import Stream
from .types import Serializer, Task
from .utils.service import Service

DEFAULT_SERVER = 'localhost:9092'


# TODO AutoOffsetReset

class Topology(Service):

    _index = count(0)
    _streams: MutableMapping[str, Stream]

    def __init__(self, loop: asyncio.AbstractEventLoop = None) -> None:
        self.loop = loop or asyncio.get_event_loop()
        self._streams = OrderedDict()

    def add_task(self, task: Task) -> None:
        ...

    async def on_start(self) -> None:
        for _stream in self._streams.values():
            await _stream.start()

    async def on_stop(self) -> None:
        for _stream in self._streams.values():
            await _stream.stop()

    def stream(
            self, *topics: str,
            key_serializer: Serializer = None,
            value_serializer: Serializer = None) -> Stream:
        return self._stream(
            topics=topics,
            key_serializer=key_serializer,
            value_serializer=value_serializer,
        )

    def stream_from_pattern(
            self, pattern: Pattern,
            key_serializer: Serializer = None,
            value_serializer: Serializer = None) -> Stream:
        return self._stream(
            pattern=pattern,
            key_serializer=key_serializer,
            value_serializer=value_serializer,
        )

    def _stream(
            self, *,
            topics: Sequence[str] = None,
            pattern: Pattern = None,
            key_serializer: Serializer = None,
            value_serializer: Serializer = None) -> Stream:
        stream = Stream(
            self._new_name(constants.SOURCE_NAME),
            key_serializer=key_serializer,
            value_serializer=value_serializer,
            topics=topics,
            pattern=pattern,
        )
        self.add_source(stream)
        return stream

    def add_source(self, stream):
        assert stream.name
        if not stream.pattern:
            assert stream.topics
        if stream.name in self._streams:
            raise ValueError(
                'Stream with name {0.name!r} already exists.'.format(stream))
        self._streams[stream.name] = stream

    def _new_name(self, prefix: str) -> str:
        return '{0}{1:010d}'.format(prefix, next(self._index))


class Worker(Service):
    """Stream processing worker.

    Keyword Arguments:
        servers: List of server host/port pairs.
            Default is ``["localhost:9092"]``.
        loop: Provide specific asyncio event loop instance.
    """

    def __init__(self,
                 *,
                 servers: Sequence[str] = None,
                 topology: Topology = None,
                 loop: asyncio.AbstractEventLoop = None) -> None:
        super().__init__(loop=loop)
        self.servers = servers or [DEFAULT_SERVER]
        self.topology = topology or Topology(loop=self.loop)

    async def on_start(self) -> None:
        await self.topology.start()

    async def on_stop(self) -> None:
        await self.topology.stop()
