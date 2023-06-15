import yaml
from icalendar import Calendar, Event, vCalAddress, vText
from datetime import datetime

with open("conferences.yml", "r") as stream:
    try:
        x = (yaml.safe_load(stream))
    except yaml.YAMLError as exc:
        print(exc)
 
# init the calendar
cal = Calendar()

cal.add('prodid', '-//aideadlin.es//ai-deadlines//EN')
cal.add('version', '2.0')


for entry in x:
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

# Write to disk 
with open('output.ics', 'wb') as f:
    f.write(cal.to_ical())

print('Successfully written to output.ics')

