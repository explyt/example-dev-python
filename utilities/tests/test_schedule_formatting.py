from datetime import datetime
from django.test import TestCase
from utilities.scheduling import ScheduleIterator

class ScheduleIteratorTestCase(TestCase):

    def test_basic_iteration(self):
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        schedule = ScheduleIterator('0 * * * *', base_time)
        
        first = next(schedule)
        second = next(schedule)
        
        self.assertEqual(first.hour, 13)
        self.assertEqual(second.hour, 14)

    def test_current_position_property(self):
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        schedule = ScheduleIterator('0 * * * *', base_time)
        
        position = schedule.current_position
        self.assertEqual(position.hour, 12)

    def test_advance_method(self):
        base_time = datetime(2024, 1, 1, 12, 0, 0)
        schedule = ScheduleIterator('0 * * * *', base_time)
        
        next_time = schedule.advance()
        self.assertEqual(next_time.hour, 13)

    def test_schedule_comparison(self):
        base_time = datetime(2024, 1, 1, 12, 0, 0)

        hourly = ScheduleIterator('0 * * * *', base_time)
        daily = ScheduleIterator('0 0 * * *', base_time)

        self.assertEqual(hourly.current_position.hour, 12)
        self.assertEqual(daily.current_position.hour, 12)

        is_hourly_sooner = hourly < daily

        self.assertTrue(is_hourly_sooner)

        self.assertEqual(hourly.current_position.hour, 12)
