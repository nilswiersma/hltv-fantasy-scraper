import gzip
import logging
import time
import re
import argparse
import sys

import yaml
# from seleniumwire import webdriver
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, ElementClickInterceptedException, NoSuchElementException

logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(name)s:%(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

parser = argparse.ArgumentParser(description="HLTV fantasy booster scaper")
parser.add_argument('-v', '--verbose', action='count')
args = parser.parse_args()

if not args.verbose:
    logger.setLevel(logging.WARNING)
elif args.verbose == 1:
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.DEBUG)

implicit_wait = 5

xpath_cookiebutton = """//*[@id="CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"]"""
xpath_signin = """/html/body/div[3]/nav/div[9]"""

id_loginpopup = 'loginpopup'

class_signin = "navsignin"
class_logininputs = "loginInput"
class_fantasy = "navfantasy"
class_boosterbutton = 'assign-booster-button'
class_powerview = 'toggle-advanced-btn'
class_boostercontainer = 'booster-overview-component'
class_booster = 'booster-icon-container'
class_boostername = 'booster-description-title'
class_playercontainer = 'booster-compact-mode-component'
class_player = 'booster-compact-mode-player'

with open('settings.yml', 'r') as f:
    settings = yaml.safe_load(f)
    
    username = settings['username']
    if username == 'your@ema.il':
        logger.error(f"'username:' not set")
        sys.exit(-1)
    logger.info(f'username = {username}')

    password = settings['password']
    if password == 'hunter123':
        logger.error(f"'password:' not set")
        sys.exit(-1)
    logger.info(f'password = *****')

    leagueid = settings['leagueid']

logger.info("Opening webdriver")
driver = webdriver.Firefox()

try:
    driver.get("https://www.hltv.org/")
    logger.info(f'implicit_wait = {implicit_wait}s')
    driver.implicitly_wait(implicit_wait)

    elem = driver.find_element(By.XPATH, xpath_cookiebutton)
    logger.info(f'{elem}')
    elem.click()

    driver.find_element(By.CLASS_NAME, class_signin).click()

    elems_login = driver.find_element(By.ID, id_loginpopup).find_elements(By.CLASS_NAME, class_logininputs)
    elems_login[0].send_keys(username)
    elems_login[1].send_keys(password)
    driver.find_element(By.CLASS_NAME, "login-button").click()

    input('press enter after finishing captcha\n> ')

    leagueurl = f'https://www.hltv.org/fantasy/{leagueid}/gameredirect'
    driver.get(leagueurl)
    logger.info(f'checking {leagueurl}')
    
    driver.find_element(By.CLASS_NAME, class_boosterbutton).click()

    driver.find_element(By.CLASS_NAME, class_powerview).click()

    scraped = {}
    elems_booster = driver.find_element(By.CLASS_NAME, class_boostercontainer).find_elements(By.CLASS_NAME, class_booster)
    for elem_booster in elems_booster:
        try:
            elem_booster.click()
        except StaleElementReferenceException as e:
            print(f'skipping element: {type(e)}, {str(e)}')
            continue
        booster_name = driver.find_element(By.CLASS_NAME, class_boostername).text
        logger.info(booster_name)
        elems_player = driver.find_element(By.CLASS_NAME, class_playercontainer).find_elements(By.CLASS_NAME, class_player)
        
        booster_data = []
        for elem_player in elems_player:
            data = elem_player.text
            logger.info(repr(data))
            booster_data.append(repr(data))
        scraped[booster_name] = booster_data

    with open(f'.scraped-{leagueid}.yml', 'w') as outf:
        yaml.dump(scraped, outf)         

finally:
    pass
    input("exit?")
    driver.close()
