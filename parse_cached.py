import yaml
import pandas as pd
import logging
import argparse

logger = logging.getLogger(__name__)
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(levelname)s:%(asctime)s:%(name)s:%(message)s')
ch.setFormatter(formatter)
logger.addHandler(ch)

parser = argparse.ArgumentParser(description="HLTV fantasy booster scaper")
parser.add_argument('-v', '--verbose', action='count')
parser.add_argument('-k', '--keep-open', 
    action='count',
    help="Keep browser window open after script is done")
args = parser.parse_args()

if not args.verbose:
    logger.setLevel(logging.WARNING)
elif args.verbose == 1:
    logger.setLevel(logging.INFO)
else:
    logger.setLevel(logging.DEBUG)

def parse_it(line):
    line = eval(line)
    line = line.split('\n')
    name = line[0]
    game = line[1]
    percentage = line[2].replace('%', '')
    return name, game, percentage

with open('settings.yml', 'r') as f:
    settings = yaml.safe_load(f)
    leagueid = settings['leagueid']

for portion in ['boosters', 'roles']:
    try:
        fname = f'.scraped-{portion}-{leagueid}.yml'
        with open(fname, 'r') as inf:
            scraped = yaml.safe_load(inf)
    except FileNotFoundError:
        logger.error(f'cannot find {fname}, skipping')
        continue

    data = []
    for booster, players in scraped.items():
        print(booster)
        for playerstr in players:
            name, game, percentage = parse_it(playerstr)
            print(name, percentage)
            data.append({'booster': booster, 'name': name, 'percentage': int(percentage)})

    df = pd.DataFrame(data)
    df.to_pickle(f'pickles/{leagueid}-{portion}.pkl')
    with pd.ExcelWriter(f'spreadsheets/{leagueid}-{portion}.xlsx') as writer:
        df.pivot(index='name', columns='booster').to_excel(writer)
