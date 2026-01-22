from datetime import datetime
from django.test import TestCase
from croniter import croniter
import pytz

class CronSchedulingTestCase(TestCase):

    def test_basic_cron_next_execution(self):
        base_time = datetime(2024, 1, 1, 0, 0, 0)
        cron = croniter('0 0 * * *', base_time)
        next_run = cron.get_next(datetime)
        
        self.assertEqual(next_run.day, 2)
        self.assertEqual(next_run.hour, 0)
        self.assertEqual(next_run.minute, 0)

    def test_cron_with_hash_distribution(self):
        base_time = datetime(2024, 1, 1, 0, 0, 0)

        job_id_1 = 'job-12345'
        job_id_2 = 'job-67890'

        cron1 = croniter('H H * * *', base_time, hash_id=job_id_1)
        cron2 = croniter('H H * * *', base_time, hash_id=job_id_2)
        
        next1 = cron1.get_next(datetime)
        next2 = cron2.get_next(datetime)

        self.assertNotEqual((next1.hour, next1.minute), (next2.hour, next2.minute))

    def test_cron_expand_from_start_time(self):
        start_time = datetime(2024, 1, 1, 12, 37, 0)
        cron = croniter('*/10 * * * *', start_time)
        
        next_run = cron.get_next(datetime)
        expected_minute = 47
        actual_minute = next_run.minute
        
        self.assertEqual(actual_minute, expected_minute)

    def test_cron_hourly_schedule(self):
        base_time = datetime(2024, 1, 1, 12, 30, 0)
        cron = croniter('0 * * * *', base_time)
        
        next_run = cron.get_next(datetime)
        self.assertEqual(next_run.hour, 13)
        self.assertEqual(next_run.minute, 0)

    def test_cron_weekly_schedule(self):
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        cron = croniter('0 9 * * 1', base_time)
        
        next_run = cron.get_next(datetime)
        self.assertEqual(next_run.weekday(), 0)
        self.assertEqual(next_run.hour, 9)
