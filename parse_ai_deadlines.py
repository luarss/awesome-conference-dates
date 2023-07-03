import yaml
from icalendar import Calendar, Event, vCalAddress, vText, Alarm
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

## Load deadlines from ai-deadlin.es
with open("conferences.yml", "r") as stream:
    try:
        ai_conferences = (yaml.safe_load(stream))
    except yaml.YAMLError as exc:
        print(exc)

## Load deadlines from cse.chalmers.se VLSI group list
output = requests.get('https://www.cse.chalmers.se/research/group/vlsi/conference/')
soup = BeautifulSoup(output.text, 'html.parser')
dates = [val.text for val in soup.find_all('center')[3::4]]
conferences = [x.text for x in soup.find_all('center')[::8]]  
vlsi_conferences = [x for  x in  zip(dates, conferences)]
 
# init the calendar
cal = Calendar()

cal.add('prodid', '-//luarss//ai-vlsi-deadlines//EN')
cal.add('version', '2.0')


for entry in ai_conferences:
    # Add subcomponents
    event = Event()
    try:
        title = f"{entry['title']} {entry['year']}"
        event.add('summary', title)
        event.add('description', entry['title'])
        event.add('dtstart', entry['start'])
        event.add('dtend', entry['end'])

        # Add the organizer
        organizer = vCalAddress('MAILTO:jdoe@example.com')
        organizer.params['name'] = vText('luarss')
        event['organizer'] = organizer
        event['location'] = vText('Earth')

        event['uid'] = title

        # Add the event to the calendar
        cal.add_component(event)
    except Exception as e:
        print(e); print(title)

for entry in vlsi_conferences:
    event = Event()
    date, title = entry[0], entry[1]
    date = datetime.strptime(date, '%Y-%m-%d')
    event.add('dtstart', date)
    event.add('dtend', date)
    event.add('summary', title)

    alarm = Alarm()
    alarm.add('action', 'DISPLAY')
    alarm.add('description', 'Meeting Reminder')
    alarm.add('trigger', timedelta(days =-7))
    alarm.add('trigger', timedelta(days =-3))
    alarm.add('trigger', timedelta(days =-1))
    alarm.add('trigger', timedelta(hours = -1))
    event.add_component(alarm)
    cal.add_component(event)

# Write to disk 
with open('output.ics', 'wb') as f:
    f.write(cal.to_ical())

print('Successfully written to output.ics')

