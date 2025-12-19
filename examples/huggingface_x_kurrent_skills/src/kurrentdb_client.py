"""
KurrentDB Client Wrapper for Financial Event Sourcing
Handles connection, event appending, and reading from KurrentDB
"""

from kurrentdbclient import KurrentDBClient, NewEvent, StreamState
from typing import List, Generator, Optional, Type, TypeVar
import json
import uuid
from datetime import datetime

from events.financial_events import FinancialEvent


T = TypeVar('T', bound=FinancialEvent)


class FinancialEventStore:
    """
    KurrentDB client wrapper for financial events.
    Provides event sourcing patterns for financial risk calculations.
    """

    def __init__(self, connection_string: str = "kurrentdb://localhost:2113?tls=false"):
        """
        Initialize connection to KurrentDB.

        Args:
            connection_string: KurrentDB connection string
        """
        self.client = KurrentDBClient(uri=connection_string)
        self._stream_prefix_map = {
            'portfolio': 'portfolio',
            'risk': 'risk',
            'bond': 'fixedincome',
            'option': 'derivatives',
            'futures': 'derivatives',
            'calculation': 'tvm',  # time value of money
            'scenario': 'scenario',
            'market': 'marketdata',
        }

    def _get_stream_name(self, event: FinancialEvent) -> str:
        """
        Derive stream name from event type following event sourcing patterns.
        Pattern: {category}-{aggregate_id}
        """
        event_type = type(event).__name__

        # Portfolio events
        if hasattr(event, 'portfolio_id') and event.portfolio_id:
            if 'Portfolio' in event_type:
                return f"portfolio-{event.portfolio_id}"
            elif 'Position' in event_type or 'Dividend' in event_type:
                return f"portfolio-{event.portfolio_id}"

        # Risk calculation events
        if any(x in event_type for x in ['VaR', 'Greeks', 'Sharpe', 'Drawdown', 'Beta']):
            if hasattr(event, 'portfolio_id') and event.portfolio_id:
                return f"risk-{event.portfolio_id}"

        # Fixed income events
        if any(x in event_type for x in ['Bond', 'Duration', 'Convexity', 'Yield', 'Coupon']):
            if hasattr(event, 'bond_id') and event.bond_id:
                return f"fixedincome-{event.bond_id}"
            return f"fixedincome-curve-{datetime.utcnow().strftime('%Y%m%d')}"

        # Derivatives events
        if any(x in event_type for x in ['Option', 'ImpliedVol', 'Delta', 'Futures']):
            if hasattr(event, 'option_id') and event.option_id:
                return f"derivatives-{event.option_id}"
            if hasattr(event, 'futures_id') and event.futures_id:
                return f"derivatives-{event.futures_id}"

        # Time value calculations
        if any(x in event_type for x in ['PresentValue', 'FutureValue', 'NPV', 'IRR', 'Amortization']):
            if hasattr(event, 'calculation_id') and event.calculation_id:
                return f"tvm-{event.calculation_id}"
            if hasattr(event, 'loan_id') and event.loan_id:
                return f"tvm-loan-{event.loan_id}"

        # Scenario analysis
        if any(x in event_type for x in ['Stress', 'MonteCarlo', 'Sensitivity']):
            if hasattr(event, 'simulation_id') and event.simulation_id:
                return f"scenario-{event.simulation_id}"
            if hasattr(event, 'portfolio_id') and event.portfolio_id:
                return f"scenario-{event.portfolio_id}"

        # Market data
        if any(x in event_type for x in ['Market', 'Interest', 'Exchange', 'Volatility']):
            if hasattr(event, 'symbol') and event.symbol:
                return f"marketdata-{event.symbol}"
            if hasattr(event, 'rate_type') and event.rate_type:
                return f"marketdata-rates-{event.rate_type}"
            if hasattr(event, 'currency_pair') and event.currency_pair:
                return f"marketdata-fx-{event.currency_pair.replace('/', '')}"

        # Fallback
        return f"financial-{event.event_id}"

    def append_event(
        self,
        event: FinancialEvent,
        stream_name: Optional[str] = None,
        expected_version: StreamState = StreamState.ANY
    ) -> int:
        """
        Append a single event to KurrentDB.

        Args:
            event: The financial event to append
            stream_name: Optional stream name override
            expected_version: Optimistic concurrency control

        Returns:
            The commit position of the appended event
        """
        if stream_name is None:
            stream_name = self._get_stream_name(event)

        new_event = NewEvent(
            type=event.event_type(),
            data=event.to_json(),
            content_type="application/json",
            id=uuid.UUID(event.event_id)
        )

        commit_position = self.client.append_to_stream(
            stream_name=stream_name,
            current_version=expected_version,
            events=[new_event]
        )

        return commit_position

    def append_events(
        self,
        events: List[FinancialEvent],
        stream_name: str,
        expected_version: StreamState = StreamState.ANY
    ) -> int:
        """
        Append multiple events to a single stream atomically.

        Args:
            events: List of financial events to append
            stream_name: The target stream name
            expected_version: Optimistic concurrency control

        Returns:
            The commit position of the last appended event
        """
        new_events = [
            NewEvent(
                type=event.event_type(),
                data=event.to_json(),
                content_type="application/json",
                id=uuid.UUID(event.event_id)
            )
            for event in events
        ]

        commit_position = self.client.append_to_stream(
            stream_name=stream_name,
            current_version=expected_version,
            events=new_events
        )

        return commit_position

    def read_stream(
        self,
        stream_name: str,
        start_position: int = 0,
        limit: Optional[int] = None,
        backwards: bool = False
    ) -> Generator[dict, None, None]:
        """
        Read events from a stream.

        Args:
            stream_name: The stream to read from
            start_position: Starting position in the stream
            limit: Maximum number of events to read
            backwards: Read in reverse order

        Yields:
            Event dictionaries with type and data
        """
        kwargs = {
            'stream_name': stream_name,
            'stream_position': start_position,
            'backwards': backwards
        }
        if limit:
            kwargs['limit'] = limit

        events = self.client.get_stream(**kwargs)

        for event in events:
            yield {
                'type': event.type,
                'data': json.loads(event.data.decode('utf-8')),
                'stream_position': event.stream_position,
                'created': event.created
            }

    def read_stream_typed(
        self,
        stream_name: str,
        event_class: Type[T],
        start_position: int = 0,
        limit: Optional[int] = None
    ) -> Generator[T, None, None]:
        """
        Read events from a stream and deserialize to typed events.

        Args:
            stream_name: The stream to read from
            event_class: The event class to deserialize to
            start_position: Starting position
            limit: Maximum events to read

        Yields:
            Typed event instances
        """
        for event_dict in self.read_stream(stream_name, start_position, limit):
            if event_dict['type'] == event_class.event_type():
                yield event_class.from_json(json.dumps(event_dict['data']).encode('utf-8'))

    def subscribe_to_stream(
        self,
        stream_name: str,
        from_position: Optional[int] = None,
        from_end: bool = False
    ) -> Generator[dict, None, None]:
        """
        Subscribe to a stream for real-time events.

        Args:
            stream_name: The stream to subscribe to
            from_position: Start position (None = start)
            from_end: Start from end (live events only)

        Yields:
            Event dictionaries as they arrive
        """
        kwargs = {'stream_name': stream_name}
        if from_position is not None:
            kwargs['stream_position'] = from_position
        if from_end:
            kwargs['from_end'] = True

        subscription = self.client.subscribe_to_stream(**kwargs)

        for event in subscription:
            yield {
                'type': event.type,
                'data': json.loads(event.data.decode('utf-8')),
                'stream_position': event.stream_position,
                'created': event.created
            }

    def subscribe_to_all(
        self,
        filter_include: Optional[List[str]] = None,
        filter_exclude: Optional[List[str]] = None
    ) -> Generator[dict, None, None]:
        """
        Subscribe to all events with optional filtering.

        Args:
            filter_include: Regex patterns for streams to include
            filter_exclude: Regex patterns for streams to exclude

        Yields:
            Event dictionaries from all matching streams
        """
        kwargs = {}
        if filter_include:
            kwargs['filter_include'] = filter_include
        if filter_exclude:
            kwargs['filter_exclude'] = filter_exclude

        subscription = self.client.subscribe_to_all(**kwargs)

        for event in subscription:
            yield {
                'type': event.type,
                'stream_name': event.stream_name,
                'data': json.loads(event.data.decode('utf-8')),
                'commit_position': event.commit_position,
                'created': event.created
            }

    def get_all_portfolio_events(self, portfolio_id: str) -> List[dict]:
        """
        Get all events for a portfolio (for building aggregate state).

        Args:
            portfolio_id: The portfolio identifier

        Returns:
            List of all events for the portfolio
        """
        events = []
        for event in self.read_stream(f"portfolio-{portfolio_id}"):
            events.append(event)
        return events

    def get_calculation_history(
        self,
        category: str,
        entity_id: str
    ) -> List[dict]:
        """
        Get calculation history for an entity.

        Args:
            category: Event category (risk, fixedincome, derivatives, tvm)
            entity_id: Entity identifier

        Returns:
            List of calculation events
        """
        stream_name = f"{category}-{entity_id}"
        return list(self.read_stream(stream_name))


# Convenience function for quick setup
def create_event_store(insecure: bool = True, host: str = "localhost", port: int = 2113) -> FinancialEventStore:
    """
    Create a FinancialEventStore with common configuration.

    Args:
        insecure: Use insecure connection (no TLS)
        host: KurrentDB host
        port: KurrentDB port

    Returns:
        Configured FinancialEventStore instance
    """
    tls_param = "false" if insecure else "true"
    connection_string = f"kurrentdb://{host}:{port}?tls={tls_param}"
    return FinancialEventStore(connection_string)
