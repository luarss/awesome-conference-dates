from icalendar import Calendar, Event, vCalAddress, vText, Alarm
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup
from utils import get_alarms

# Download latest from ai-deadlin.es
ai_link = "https://aideadlin.es/ai-deadlines.ics"
response = requests.get(ai_link)
if response.status_code == 200:
    with open("ai-deadlines.ics", "wb") as file:
        file.write(response.content)
    print("File downloaded successfully.")
else:
    print(f"Failed to download the file. Status code: {response.status_code}")
    exit()

with open("ai-deadlines.ics") as f:
    try:
        cal = Calendar.from_ical(f.read())
    except Exception as e:
        print(e)
        exit()

# Load deadlines from cse.chalmers.se VLSI group list
output = requests.get('https://www.cse.chalmers.se/research/group/vlsi/conference/')
soup = BeautifulSoup(output.text, 'html.parser')
dates = [val.text for val in soup.find_all('center')[3::4]]
conferences = [x.text for x in soup.find_all('center')[::8]]  
vlsi_conferences = [x for  x in  zip(dates, conferences)]
 
cal.add('prodid', '-//luarss//ai-vlsi-deadlines//EN')
cal.add('version', '2.0')

for entry in vlsi_conferences:
    event = Event()
    date, title = entry[0], entry[1]
    date = datetime.strptime(date, '%Y-%m-%d')
    event.add('dtstart', date)
    event.add('dtend', date)
    event.add('summary', title)
    event.add('description', title)
    organizer = vCalAddress('MAILTO:jdoe@example.com')
    organizer.params['name'] = vText('luarss')
    event['organizer'] = organizer
    event['location'] = vText('Earth')
    event['uid'] = title

    # Add the alarms
    alarms = get_alarms()
    for alarm in alarms:
       event.add_component(alarm)
    cal.add_component(event)

# Write to disk 
with open('output.ics', 'wb') as f:
    f.write(cal.to_ical())

print('Successfully written to output.ics')

