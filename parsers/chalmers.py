import requests
from bs4 import BeautifulSoup

LINK = "https://www.cse.chalmers.se/research/group/vlsi/conference"

def main():
    try:
        output = requests.get(LINK, timeout=10)
        soup = BeautifulSoup(output.text, 'html.parser')
        dates = [val.text for val in soup.find_all('center')[3::4]]
        conferences = [x.text for x in soup.find_all('center')[::8]]  
        vlsi_conferences = [x for x in  zip(dates, conferences)]
    except requests.RequestException as e:
        print(f"Error fetching VLSI conferences: {e}")
        vlsi_conferences = []
    except Exception as e:
        print(f"Error parsing VLSI conferences: {e}")
        vlsi_conferences = []
    return vlsi_conferences

if __name__ == "__main__":
    data = main()
    for date, title in data:
        print(f"{date}: {title}")