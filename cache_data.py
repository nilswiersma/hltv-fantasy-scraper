import gzip
import logging
import time
import re
import argparse
import sys
import itertools

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
            self.settings = yaml.safe_load(f)
            
            username = self.settings['username']
            if username == 'your@ema.il':
                logger.error(f"'username:' not set")
                sys.exit(-1)
            self.username = username
            logger.info(f'{self.username=}')

            password = self.settings['password']
            if password == 'hunter123':
                logger.error(f"'password:' not set")
                sys.exit(-1)
            self.password = password
            logger.info(f'self.password=*****')

            self._leagueids = self.settings['leagueids']
            self._current_leagueid = self.settings['leagueid']
            logger.info(f'{self._leagueids=}')
            logger.info(f'{self._current_leagueid=}')

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
        del self._implicit_wait

    @property
    def current_leagueid(self):
        return self._current_leagueid
    
    @current_leagueid.setter
    def current_leagueid(self, leagueid):
        self._current_leagueid = leagueid
        self.write_settings()

    @property
    def leagueids(self):
        return self._leagueids
    
    @leagueids.setter
    def leagueids(self, leagueids):
        self._leagueids = leagueids
        self.write_settings()

    def write_settings(self):
        self.settings['leagueid'] = self.current_leagueid
        self.settings['leagueids'] = self.leagueids

        with open('settings.yml', 'w') as f:
            yaml.safe_dump(self.settings, f)

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

    def goto_fantasypage(self):
        leagueurl = f'https://www.hltv.org/fantasy'
        self.driver.get(leagueurl)

    def goto_leaguepage(self):
        leagueurl = f'https://www.hltv.org/fantasy/{self.current_leagueid}/gameredirect'
        logger.info(f'checking {leagueurl}')
        self.driver.get(leagueurl)

        logger.info(f'waiting a second for redirect')
        time.sleep(1)

        if 'team' in self.driver.current_url:
            logger.info(f'have team in {self.current_leagueid=}')
            return True
        elif 'overview' in self.driver.current_url:
            logger.warning(f'do not have team in {self.current_leagueid=}')
            return False
        else:
            logger.warning(f'do not understand redirect for {self.current_leagueid=} ({self.driver.current_url})')
            return False
        
    def scrape_games(self, which):
        if which == 'live':
            button_class = 'game-live'
        elif which == 'draft':
            button_class = 'game-draft'
        else:
            raise NotImplementedError(f'can only scrape "live" or "draft" (not {which=}')

        game_elems = self.driver.find_element(By.CLASS_NAME, 'season-games').find_elements(By.CLASS_NAME, button_class)
        ret = []
        if len(game_elems) > 0:
            for elem in game_elems:
                title = elem.find_element(By.XPATH, './ancestor::a').text.split('\n')[0]
                id = int(elem.find_element(By.XPATH, './ancestor::a').get_attribute('href').split('/')[-2])
                ret.append((title, id))
        
        return ret


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

        filename = f'scraped/{self.current_leagueid}-{which}.yml'
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

        filename = f'scraped/{self.current_leagueid}-roles.yml'
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
        
        filename = f'scraped/{self.current_leagueid}-players.yml'
        logger.info(f'dumping scraped data to {filename=}')
        with open(filename, 'w') as outf:
            yaml.dump(scraped, outf)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HLTV fantasy booster scaper")
    parser.add_argument('-v', '--verbose', action='count')
    parser.add_argument('-k', '--keep-open', 
        action='count',
        help="Keep browser window open after script is done")
    parser.add_argument('--skip-login', 
        action='count',
        help="Don't login to account")
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
        if not args.skip_login:
            ctx.login()
            input('press enter after finishing captcha\n> ')
        logger.info('speed up implicit wait')
        ctx.implicit_wait = 1

        while True:
            try:
                answer = input(f'{ctx.current_leagueid=}, do what?\n [s]elect league\n cache [p]layers\n cache [r]oles\n cache [b]oosters\n or [q]uit\n> ')
                if answer in ['q', 'quit']:
                    break

                elif answer in ['s', 'select', 'select league']:
                    ctx.goto_fantasypage()
                    print(' select league')
                    print('  live games:')
                    live_games = ctx.scrape_games('live')
                    idx = 0
                    for idx, (title, leagueid) in enumerate(live_games):
                        print(f'   [{idx:2d}] - {leagueid:4d}: {title} ')
                    if idx != 0:
                        idx += 1
                    print('  draft games:')
                    draft_games = ctx.scrape_games('draft')
                    for idx, (title, leagueid) in enumerate(draft_games, start=idx):
                        print(f'   [{idx:2d}] - {leagueid:4d}: {title} ')
                    # try:
                    ctx.leagueids = list(zip(*(live_games + draft_games)))[1]

                    selected_idx = int(input('> '))
                    if 0 <= selected_idx <= len(ctx.leagueids):
                        ctx.current_leagueid = ctx.leagueids[selected_idx]
                        logger.info(f'{ctx.current_leagueid=}')
                
                elif answer in ['p', 'players', 'cache players']:
                    if ctx.goto_leaguepage():
                        ctx.cache_players()
                elif answer in ['r', 'roles', 'cache roles']:
                    if ctx.goto_leaguepage():
                        ctx.cache_roles()
                elif answer in ['b', 'boosters', 'cache boosters']:
                    if ctx.goto_leaguepage():
                        ctx.cache_boosters()
                    
                else:
                    pass
            except KeyboardInterrupt:
                break
            except EOFError:
                break
