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
from selenium.webdriver.support.ui import Select
from selenium.webdriver.remote.webdriver import WebDriver

logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(name)s:%(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

XPATH_COOKIEBUTTON = """//*[@id="CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"]"""
XPATH_SIGNIN = """/html/body/div[3]/nav/div[9]"""

ID_LOGINPOPUP = 'loginpopup'

CLASS_SIGNIN = "navsignin"
CLASS_LOGININPUTS = "loginInput"
CLASS_FANTASY = "navfantasy"
CLASS_BOOSTERBUTTON = 'assign-booster-button'
CLASS_ROLEBUTTON = "assign-role-button"
CLASS_POWERVIEW = 'toggle-advanced-btn'
CLASS_BOOSTERCONTAINER = 'booster-overview-component'
CLASS_BOOSTER = 'booster-icon-container'
CLASS_BOOSTERNAME = 'booster-description-title'
CLASS_PLAYERCONTAINER = 'booster-compact-mode-component'
CLASS_PLAYER = 'booster-compact-mode-player'
CLASS_LOGINBUTTON = "login-button"
CLASS_CLOSEBUTTON = 'modal-close-button'
CLASS_SETTINGSDROPDOWN = 'dropdown-subtab'
CLASS_PLAYERREMOVE = 'playerButtonRemove'

# patch to make it possible to reattach to running webdriver
# https://stackoverflow.com/a/48194907
# doesnt work once the original script has exited :(
def attach_to_session(executor_url, session_id):
    original_execute = WebDriver.execute
    def new_command_execute(self, command, params=None):
        if command == "newSession":
            # Mock the response
            return {'success': 0, 'value': None, 'sessionId': session_id}
        else:
            return original_execute(self, command, params)
    # Patch the function before creating the driver object
    WebDriver.execute = new_command_execute
    driver = webdriver.Remote(command_executor=executor_url, desired_capabilities={})
    driver.session_id = session_id
    # Replace the patched function with original function
    WebDriver.execute = original_execute
    return driver


class HltvContext():
    
    def __init__(self, args, driver: webdriver.Remote, implicit_wait=5):
        self.args = args

        with open('settings.yml', 'r') as f:
            settings = yaml.safe_load(f)
            
            username = settings['username']
            if username == 'your@ema.il':
                logger.error(f"'username:' not set")
                sys.exit(-1)
            self.username = username
            logger.info(f'{self.username=}')

            password = settings['password']
            if password == 'hunter123':
                logger.error(f"'password:' not set")
                sys.exit(-1)
            self.password = password
            logger.info(f'self.password=*****')

            self.leagueid = settings['leagueid']
            logger.info(f'{self.leagueid=}')

        self.driver = driver

        self.implicit_wait = implicit_wait
        logger.info("initializing driver with 'https://www.hltv.org/'")
        self.driver.get("https://www.hltv.org/")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        logger.debug(f'{args=}')
        if not self.args.keep_open:
            self.driver.close()
        else:
            logger.warning(f'keeping webdriver open, to reconnect use below')
            logger.warning(f'--session-id {driver.session_id} --executor-url {driver.command_executor._url}')

    @property
    def implicit_wait(self):
        return self._implicit_wait

    @implicit_wait.setter
    def implicit_wait(self, implicit_wait):
        logger.info(f'{implicit_wait=}s')
        self._implicit_wait = implicit_wait
        self.driver.implicitly_wait(implicit_wait)

    @implicit_wait.deleter
    def implicit_wait(self):
        print("deleter of implicit_wait called")
        del self._implicit_wait

    ## Generic functions to navigate hltv
    def cookie_pass(self):
        logger.info('waiting for cookie button')
        try:
            elem = self.driver.find_element(By.XPATH, XPATH_COOKIEBUTTON)
            elem.click()
        except NoSuchElementException as e:
            logger.warning(f'{str(e)=}, assuming no cookie popup')

    def login(self):
        # This tends to trigger manual captcha
        self.driver.find_element(By.CLASS_NAME, CLASS_SIGNIN).click()
        elems_login = self.driver.find_element(By.ID, ID_LOGINPOPUP).find_elements(By.CLASS_NAME, CLASS_LOGININPUTS)
        elems_login[0].send_keys(self.username)
        elems_login[1].send_keys(self.password)
        self.driver.find_element(By.CLASS_NAME, CLASS_LOGINBUTTON).click()

    def goto_leaguepage(self):
        leagueurl = f'https://www.hltv.org/fantasy/{self.leagueid}/gameredirect'
        logger.info(f'checking {leagueurl}')
        self.driver.get(leagueurl)

        logger.info(f'waiting a second for redirect')
        time.sleep(1)

        if 'team' in self.driver.current_url:
            logger.info(f'have team in {self.leagueid=}')
        elif 'overview' in self.driver.current_url:
            logger.info(f'do not have team in {self.leagueid=}')
        else:
            logger.warning(f'do not understand redirect for {self.leagueid=} ({self.driver.current_url})')

    def scrape_powerview(self, which):
        button_locator = None

        if which == 'roles':
            button_locator = CLASS_ROLEBUTTON
            elem = self.driver.find_element(By.CLASS_NAME, button_locator)
            if 'not-assigned' not in elem.get_attribute('class'):
                logger.error('cannot open role view, it is not clickable')
                return
            elem.click()

        elif which == 'boosters':
            button_locator = CLASS_BOOSTERBUTTON
            elem = self.driver.find_element(By.CLASS_NAME, button_locator)
            elem.click()
            Select(self.driver.find_element(By.CLASS_NAME, 'modal-title').find_element(By.TAG_NAME, 'select')).select_by_visible_text('Assign booster')
        else:
            raise NotImplementedError(f'can only scrape "roles" or "boosters" (not {which=}')

        self.driver.find_element(By.CLASS_NAME, CLASS_POWERVIEW).click()

        scraped = {}
        elem_boosters = self.driver.find_element(By.CLASS_NAME, CLASS_BOOSTERCONTAINER).find_elements(By.CLASS_NAME, CLASS_BOOSTER)
        for elem_booster in elem_boosters:
            try:
                elem_booster.click()
            except StaleElementReferenceException as e:
                logger.info(f'skipping element: {type(e)}, {str(e)}')
                continue
            booster_name = self.driver.find_element(By.CLASS_NAME, CLASS_BOOSTERNAME).text
            logger.debug(booster_name)
            elems_player = self.driver.find_element(By.CLASS_NAME, CLASS_PLAYERCONTAINER).find_elements(By.CLASS_NAME, CLASS_PLAYER)
            
            booster_data = []
            for elem_player in elems_player:
                data = elem_player.text
                logger.debug(repr(data))
                booster_data.append(repr(data))
            scraped[booster_name] = booster_data
        
        self.driver.find_element(By.CLASS_NAME, CLASS_CLOSEBUTTON).click()

        filename = f'scraped/{self.leagueid}-{which}.yml'
        logger.info(f'dumping scraped data to {filename=}')
        with open(filename, 'w') as outf:
            yaml.dump(scraped, outf)

    def cache_roles(self):
        # # this only gets big average trigger rate
        # self.scrape_powerview('roles')
        elem = self.driver.find_element(By.CLASS_NAME, CLASS_ROLEBUTTON)
        if 'not-assigned' not in elem.get_attribute('class'):
            print('cannot open role view, it is not clickable')
            raise Exception()
        elem.click()

        scraped = {}
        while True:
            elem_nextplayer = self.driver.find_element(By.CLASS_NAME, 'booster-next-player')
            playername = self.driver.find_element(By.CLASS_NAME, 'player-visible').text
            logger.info(f'{playername=}')
            scraped[playername] = {}
            elem_boosters = self.driver.find_element(By.CLASS_NAME, CLASS_BOOSTERCONTAINER).find_elements(By.CLASS_NAME, CLASS_BOOSTER)
            for elem_booster in elem_boosters:
                try:
                    elem_booster.click()
                except StaleElementReferenceException as e:
                    logger.info(f'skipping element {elem_booster.text=}: {type(e)}, {str(e)}')
                    continue
                booster_name = self.driver.find_element(By.CLASS_NAME, CLASS_BOOSTERNAME).text
                logger.debug(f'{booster_name=}')
                booster_data = self.driver.find_element(By.CLASS_NAME, 'booster-trigger-rate').text
                logger.debug(f'{booster_data=}')
                scraped[playername][booster_name] = booster_data
            
            if 'inactive' in elem_nextplayer.get_attribute('class'):
                break
            else:
                elem_nextplayer.click()

        self.driver.find_element(By.CLASS_NAME, CLASS_CLOSEBUTTON).click()

        filename = f'scraped/{self.leagueid}-roles.yml'
        logger.info(f'dumping scraped data to {filename=}')
        with open(filename, 'w') as outf:
            yaml.dump(scraped, outf)
    
    def cache_boosters(self):
        self.scrape_powerview('boosters')

    def cache_players(self):
        CLASS_SETTINGS = 'sub-menu-tab'
        elem = self.driver.find_elements(By.CLASS_NAME, CLASS_SETTINGS)[-1]
        if elem.text != 'Settings':
            logger.warning('cannot cache players, edit lineup not available')
            return
        elem.click()
        self.driver.find_elements(By.CLASS_NAME, CLASS_SETTINGSDROPDOWN)[0].click()

        # they reorder when you dont remove in reverse order, making the references stale
        [elem.click() for elem in self.driver.find_elements(By.CLASS_NAME, CLASS_PLAYERREMOVE)[::-1]]
        
        scraped = {}
        for elem in self.driver.find_elements(By.CLASS_NAME, 'teamCon'):
            teamname = elem.find_element(By.CLASS_NAME, 'teamName').text
            logger.debug(f'{teamname=}')
            teamrank = elem.find_element(By.CLASS_NAME, 'teamRank').text
            logger.debug(f'{teamrank=}')
            for elem2 in elem.find_elements(By.CLASS_NAME, 'teamPlayer'):
                playerprice = elem2.find_element(By.CLASS_NAME, 'playerButtonText').text
                logger.debug(f'{playerprice=}')
                playername = elem2.find_element(By.CLASS_NAME, 'card-player-tag').text
                logger.debug(f'{playername=}')
                stats = []
                for elem3 in elem2.find_elements(By.CLASS_NAME, 'stat-flex'):
                    logger.debug(f'{elem3.text=}')
                    stats.append(repr(elem3.text))

                scraped[playername] = {
                    'playerprice': playerprice,
                    'teamname': teamname,
                    'teamrank': teamrank,
                    'stats': stats
                    }
        
        filename = f'scraped/{self.leagueid}-players.yml'
        logger.info(f'dumping scraped data to {filename=}')
        with open(filename, 'w') as outf:
            yaml.dump(scraped, outf)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HLTV fantasy booster scaper")
    parser.add_argument('-v', '--verbose', action='count')
    parser.add_argument('-k', '--keep-open', 
        action='count',
        help="Keep browser window open after script is done")
    parser.add_argument('--session-id',
        help="session-id of a running webdriver instance (need to be used with --executor-url).")
    parser.add_argument('--executor-url',
        help="executor-url of a running webdriver instance (need to be used with --session-id).")
    args = parser.parse_args()

    if not args.verbose:
        logger.setLevel(logging.WARNING)
    elif args.verbose == 1:
        logger.setLevel(logging.INFO)
    else:
        logger.setLevel(logging.DEBUG)
    
    logger.info("Opening webdriver")
    if args.session_id and args.executor_url:
        driver = attach_to_session(args.executor_url, args.session_id)
    else:
        driver = webdriver.Firefox()

    with HltvContext(args, driver) as ctx:
        ctx.cookie_pass()
        ctx.login()
        input('press enter after finishing captcha\n> ')
        logger.info('speed up implicit wait')
        ctx.implicit_wait = 1
        ctx.goto_leaguepage()

        while True:
            try:
                answer = input('cache what?\n [p]layers\n [r]oles\n [b]oosters\n or [q]uit\n> ')
                if answer in ['q', 'quit']:
                    break
                elif answer in ['p', 'players']:
                    ctx.goto_leaguepage()
                    ctx.cache_players()
                elif answer in ['r', 'roles']:
                    ctx.goto_leaguepage()
                    ctx.cache_roles()
                elif answer in ['b', 'boosters']:
                    ctx.goto_leaguepage()
                    ctx.cache_boosters()
                else:
                    pass
            except KeyboardInterrupt:
                break
