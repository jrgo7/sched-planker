import logging
import time
import urllib.parse
from typing import Any

import coloredlogs
import playaudio
from gtts import gTTS
from selenium_driverless.types.by import By
from seleniumbase import SB, BaseCase
from seleniumbase.undetected.webelement import WebElement

from config import CONFIG

coloredlogs.DEFAULT_LOG_FORMAT = "%(asctime)s %(levelname)s | %(message)s"
coloredlogs.install()


def main():
    with SB(uc=True, test=True) as sb:
        logging.info("# AnimoStalker")
        while True:
            logging.info("")
            logging.info("## Scanning...")
            for target in CONFIG["targets"]:
                logging.info(f"### {target['course']}")
                listings = scrape_course(sb, target["course"])
                alert_available_slots(listings, target["sections"])
            logging.info("> Scanning again after 60 seconds.")
            time.sleep(60)


def scrape_course(
    sb: BaseCase,
    course: str,
    id_number: str = CONFIG["id_number"],
) -> list[dict]:
    table_xpath = "/html/body/table[4]/tbody/tr/td/table/tbody/tr[3]/td/table/tbody/tr/td[2]/form/table"
    url = course_url(course, id_number)
    sb.uc_open_with_reconnect(url)
    sb.uc_gui_click_captcha()
    table = sb.find_element(By.XPATH, table_xpath, timeout=10)
    assert table, "Table not found!"
    content = get_content(table)
    listings = process_listings(content)
    return listings


def get_content(table: WebElement) -> list[str]:
    content = []
    rows = table.find_elements(By.TAG_NAME, "tr")
    for row in rows:
        cells = row.find_elements(By.TAG_NAME, "td")
        for cell in cells:
            content.append(cell.text)
    return list(map(lambda line: line.strip(), filter(lambda line: line, content)))[9:]


def process_listings(content: list[str]) -> list[dict[str, str | list[str]]]:
    initial_keys = [
        "class_number",
        "course_code",
        "section",
        "day",
        "time",
        "room",
        "cap",
        "enrolled",
        "modality",
        "instructor",
    ]
    additional_keys = [
        "",
        "",
        "day",
        "time",
        "room",
        "",
        "",
        "",
        "instructor",
    ]
    listings = []
    listing = {}

    def add_fields_to_listing(keys: list[str]):
        for key in keys:
            if not content:  # hack for blank instructor in last listing
                break

            value = content.pop(0)

            if key == "instructor" and (
                value == "" or is_castable_to_int(value)
            ):  # hack for blank instructor
                content.insert(0, value)
                continue

            if not key:  # exclude blank keys
                continue

            if key in listing.keys():
                if isinstance(listing[key], list):
                    listing[key].append(value)
                else:
                    listing[key] = [listing[key], value]
            else:
                listing[key] = value

    while content:
        add_fields_to_listing(initial_keys)
        is_new_listing = False
        while content and not is_new_listing:
            value = content.pop(0)
            if is_castable_to_int(value):  # course number of a new listing
                content.insert(0, value)
                is_new_listing = True
            elif content:  # addt'l date, time, room
                add_fields_to_listing(additional_keys)
        listings.append(listing)
        listing = {}

    return listings


def is_castable_to_int(x: Any) -> bool:
    try:
        int(x)
        return True
    except (ValueError, TypeError):
        return False


def course_url(
    course: str,
    id_number: str = CONFIG["id_number"],
    option: str = "all",
) -> str:
    url = "https://enroll.dlsu.edu.ph/dlsu/view_course_offerings/?"
    params = {
        "p_id_no": id_number,
        "p_course_code": course,
        "p_option": option,
        "p_button": "Search",
    }
    return url + urllib.parse.urlencode(params)


def alert_available_slots(
    listings: list[dict[str, str | list[str]]], sections: list[str]
) -> None:
    listings = list(filter(lambda listing: listing["section"] in sections, listings))
    for listing in listings:
        logging.info(
            f"- {listing['section']}\t{listing['enrolled']} / {listing['cap']}"
        )
        assert isinstance(listing["enrolled"], str)
        assert isinstance(listing["cap"], str)
        if int(listing["enrolled"]) < int(listing["cap"]):
            text = f"Available slots for {listing['course_code']} section {listing['section']}!"
            gTTS(
                text=text,
                lang="en",
            ).save("alert.mp3")
            playaudio.playaudio("alert.mp3")


if __name__ == "__main__":
    main()
