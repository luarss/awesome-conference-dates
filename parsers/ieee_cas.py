import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from bs4 import BeautifulSoup
import urllib.parse

LINK = "https://ieee-cas.org/conference-events/full-conference-list"
CLICK_LIMIT = 30


def get_full_page_source_selenium(url):
    """
    Automates clicking the 'Load More' button until it disappears,
    then returns the full page's HTML source.
    """
    # Use the Selenium WebDriver for Chrome
    chrome_options = webdriver.ChromeOptions()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-infobars")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)

    print("Page loaded. Handling cookie banner...")

    # --- Handle cookie consent banner ---
    try:
        # Wait a moment for the banner to appear
        time.sleep(2)

        # find and dismiss the cookie banner
        cookie_buttons = [
            "button[class*='osano']",
            "button[class*='cookie']",
            "button[class*='accept']",
            "button[class*='consent']",
            ".osano-cm-accept",
            ".osano-cm-close",
            ".osano-cm-dismiss",
        ]

        for selector in cookie_buttons:
            try:
                cookie_button = driver.find_element(By.CSS_SELECTOR, selector)
                cookie_button.click()
                print("Cookie banner dismissed.")
                time.sleep(1)
                break
            except NoSuchElementException:
                continue

    except Exception as e:
        print(f"Could not handle cookie banner: {e}")

    # --- Click the "Load More" button until it disappears ---
    print("Starting to click 'Load More'...")
    curr_count = 0
    while True:
        if curr_count > CLICK_LIMIT:
            print(f"Reached click limit of {CLICK_LIMIT}. Stopping.")
            break
        try:
            curr_count += 1
            # Find the "Load More" button by its unique attributes
            # A CSS selector is great for this.
            load_more_button = driver.find_element(
                By.CSS_SELECTOR, "a[title='Load more items']"
            )

            # Scroll the button into view to ensure it's clickable
            driver.execute_script(
                "arguments[0].scrollIntoView({block: 'center'});", load_more_button
            )
            time.sleep(1)  # Slightly longer pause to ensure scrolling is complete

            # Ensure the button is interactable before clicking
            if load_more_button.is_displayed() and load_more_button.is_enabled():
                load_more_button.click()
            else:
                print("Load More button not interactable.")
                break

            print("Clicked 'Load More'. Waiting for new content...")

            # Wait for the new content to load. 2 seconds is a simple but
            # potentially fragile wait. For production, use WebDriverWait.
            time.sleep(2)
        except NoSuchElementException:
            # This exception means the button was not found, so we're done.
            print("All content has been loaded.")
            break  # Exit the loop
        except Exception as e:
            print(f"An error occurred while clicking 'Load More': {e}")
            raise e

    # --- Get the full page source after all content is loaded ---
    full_html = driver.page_source
    driver.quit()
    return full_html


def extract_conference_details(article, base_url):
    """
    Extracts details for a single conference from its <article> tag.
    Returns a dictionary containing the conference information.
    """
    details = {}

    # Extract Shortform
    shortform_tag = article.find("div", class_="field--node--field-acronym")
    details["shortform"] = shortform_tag.text.strip() if shortform_tag else None

    # Extract Conference Name and Link
    name_link_tag = article.find("h3", class_="field--node--field-display-title").find(
        "a"
    )
    if name_link_tag:
        details["name"] = name_link_tag.text.strip()
        relative_link = name_link_tag.get("href", "")
        details["link"] = urllib.parse.urljoin(base_url, relative_link)
    else:
        details["name"] = None
        details["link"] = None

    # Extract Deadline (Optional)
    deadline_tag = article.find("div", class_="field--node--field-deadline")
    if deadline_tag and deadline_tag.find("time"):
        details["deadline"] = deadline_tag.find("time").text.strip()

    # Extract Dates
    dates_tag = article.find("div", class_="field--node--field-date-range")
    if dates_tag and len(dates_tag.find_all("span")) > 1:
        details["dates"] = dates_tag.find_all("span")[1].get_text(
            strip=True, separator=" "
        )
    else:
        details["dates"] = None

    # Extract Region
    region_tag = article.find("div", class_="field--node--field-location-text")
    if region_tag and len(region_tag.find_all("span")) > 1:
        details["region"] = region_tag.find_all("span")[1].text.strip()
    else:
        details["region"] = None

    return details


def main():
    """
    Main function to execute the Selenium automation and print the results.
    """
    # The URL of the page with the "Load More" button
    target_url = LINK

    # Get the fully-loaded HTML after clicking through all pages
    final_html = get_full_page_source_selenium(target_url)

    # Now, you can use BeautifulSoup on the complete HTML
    base_url = "https://ieee-cas.org"

    # Find all conference article containers
    soup = BeautifulSoup(final_html, "html.parser")
    all_conference_articles = soup.find_all("article", class_="simple--event")

    # Create a list to hold all the extracted data
    all_conferences_data = []

    # Loop through each article and extract its details
    for article in all_conference_articles:
        conference_info = extract_conference_details(article, base_url)
        if conference_info.get(
            "shortform"
        ):  # Only add if it's a valid entry with a shortform
            all_conferences_data.append(conference_info)
    return all_conferences_data


if __name__ == "__main__":
    all_data = main()
    for conf in all_data:
        print(
            f"Shortform: {conf.get('shortform')}, Name: {conf.get('name')}, Link: {conf.get('link')}, "
            f"Deadline: {conf.get('deadline')}, Dates: {conf.get('dates')}, Region: {conf.get('region')}"
        )
