from icalendar import Calendar, Event, vCalAddress, vText
from datetime import datetime
import requests
from utils import get_alarms
from parsers.ieee_cas import main as parse_ieee_cas

# Constants
AI_LINK = "https://aideadlin.es/ai-deadlines.ics"
AI_ICS_FILE = "ai-deadlines.ics"

# Download latest from ai-deadlin.es
try:
    response = requests.get(AI_LINK)
    if response.status_code == 200:
        with open(AI_ICS_FILE, "wb") as file:
            file.write(response.content)
        print("File downloaded successfully.")
    else:
        print(f"Failed to download the file. Status code: {response.status_code}")
        exit()

    with open(AI_ICS_FILE) as f:
        cal = Calendar.from_ical(f.read())
except requests.RequestException as e:
    print(f"Error fetching AI deadlines: {e}")
    exit()
except Exception as e:
    print(f"Error parsing AI deadlines: {e}")
    exit()

# Load deadlines from cse.chalmers.se VLSI group list
# vlsi_1 = parse_chalmers()

# Load deadlines from ieee-cas.org VLSI group list
vlsi_conferences = parse_ieee_cas()

# Create calendar
cal.add("prodid", "-//luarss//ai-vlsi-deadlines//EN")
cal.add("version", "2.0")

for entry in vlsi_conferences:
    event = Event()
    deadline = entry.get("deadline", "")
    name = entry.get("shortform") + " " + entry.get("name", "")
    link = entry.get("link", "")
    region = entry.get("region", "")
    dates = entry.get("dates", "")
    date_start, date_end = (
        dates.split("\u2013") if "\u2013" in dates else (dates, dates)
    )
    date_start = datetime.strptime(date_start.strip(), "%d %b %Y")
    date_end = datetime.strptime(date_end.strip(), "%d %b %Y")
    event.add("dtstart", date_start)
    event.add("dtend", date_end)
    event.add("summary", name)
    event.add(
        "description", f"{name}\n\nRegion: {region}\nLink: {link}\nDeadline: {deadline}"
    )
    event.add("location", region)
    organizer = vCalAddress("MAILTO:jdoe@example.com")
    organizer.params["name"] = vText("luarss")
    event["organizer"] = organizer

    # Add the alarms
    alarms = get_alarms()
    for alarm in alarms:
        event.add_component(alarm)
    cal.add_component(event)

# Write to disk
with open("output.ics", "wb") as f:
    f.write(cal.to_ical())

# Validate ICS file
try:
    with open("output.ics", "r") as f:
        Calendar.from_ical(f.read())
    print("ICS file is valid.")
except Exception as e:
    print(f"ICS file is invalid: {e}")
    exit()

print("Successfully written to output.ics")
