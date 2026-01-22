from datetime import datetime
from croniter import croniter

__all__ = (
    'ScheduleIterator',
)


class ScheduleIterator:
    
    def __init__(self, expression, start_time=None):
        self.expression = expression
        self.start_time = start_time or datetime.now()
        self._cron = croniter(expression, self.start_time)
    
    def __iter__(self):
        return self
    
    def __next__(self):
        return self._cron.get_next(datetime)
    
    def __lt__(self, other):
        if not isinstance(other, ScheduleIterator):
            return NotImplemented
        self_next = self._cron.get_next()
        other_next = other._cron.get_next()
        return self_next < other_next
    
    def __eq__(self, other):
        if not isinstance(other, ScheduleIterator):
            return NotImplemented
        self_next = self._cron.get_next()
        other_next = other._cron.get_next()
        return self_next == other_next
    
    def __le__(self, other):
        return self < other or self == other
    
    def __gt__(self, other):
        return not self <= other
    
    def __ge__(self, other):
        return not self < other
    
    def __ne__(self, other):
        return not self == other
    
    @property
    def current_position(self):
        return self._cron.get_current(datetime)
    
    def advance(self):
        return next(self)
