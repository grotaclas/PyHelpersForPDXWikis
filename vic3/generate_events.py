import re
import os
from typing import Any

import sys
# add the parent folder to the path so that imports work even if this file gets executed directly
sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))

from vic3.vic3_file_generator import Vic3FileGenerator


class EventGenerator(Vic3FileGenerator):
    """Generator for Victoria 3 events wiki documentation"""

    def generate_events(self, args: list[str]):
        """Generate wiki documentation for one or more events in a namespace.

        Usage: python generate_events.py events <namespace> [event_id1 event_id2 ...]

        If no event_ids are given, all events in the namespace are generated.
        Event IDs can be the numeric part only (e.g. '1') or full keys (e.g. 'my_ns.1').
        """
        if len(args) < 1:
            print('Usage: python generate_events.py events <namespace> [event_id1 event_id2 ...]')
            return ''

        namespace = args[0]
        requested_ids = set()

        for arg in args[1:]:
            # Support both '1' and 'namespace.1' formats
            if arg.startswith(namespace + '.'):
                requested_ids.add(arg[len(namespace) + 1:])
            else:
                requested_ids.add(arg)

        # Find all events in this namespace
        events = self.parser.events(namespace)

        if not events:
            print(f'No events found for namespace "{namespace}"')
            return ''

        # Filter to requested IDs if specified
        if requested_ids:
            events = {k: v for k, v in events.items() if k in requested_ids}
            if not events:
                all_ids = list(self.parser.events(namespace).keys())
                print(f'No matching events found. Available events in namespace "{namespace}": {all_ids}')
                return ''

        # Format each event
        formatter = self.parser.formatter
        output_parts = []

        for event_id in sorted(events.keys(), key=self._sort_key):
            event = events[event_id]
            event.version = self.game.major_version
            event.collapse = 'yes'  # Default to collapsed for country pages
            output_parts.append(formatter.format_event(event))

        return '\n\n'.join(output_parts)

    @staticmethod
    def _sort_key(event_id: str) -> tuple:
        """Sort key that handles numeric event IDs properly."""
        try:
            return (0, int(event_id))
        except ValueError:
            return (1, event_id)


if __name__ == '__main__':
    EventGenerator().run_specific(sys.argv)
