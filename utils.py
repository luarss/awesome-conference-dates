from icalendar import Alarm
from datetime import timedelta


def get_alarms():
    alarms = []
    for hour in [1, 24, 72, 168]:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", "Meeting Reminder")
        alarm.add("trigger", timedelta(hours=-hour))
        alarms.append(alarm)
    return alarms
