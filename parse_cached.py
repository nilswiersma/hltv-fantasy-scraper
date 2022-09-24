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

def parse_players(scraped) -> pd.DataFrame:
    data = []
    for player, info in scraped.items():
        print(player)
        row = {'player': player}
        for key, value in info.items():
            if key == 'playerprice':
                row['price'] = int(value.replace('$', '').replace(',', ''))
            elif key == 'teamname':
                row['team'] = value
            elif key == 'teamrank':
                row['rank'] = value.split(' ')[0].replace('#', '')
            elif key == 'stats':
                for stat in value:
                    stat = eval(stat)
                    name, val = stat.split('\n')
                    # clean floats
                    if name in ['Rating', 'CT rating', 'T rating', 'AWP', 'Deaths per round']:
                        row[name] = float(val)
                    # % floats
                    elif name in ['HS %', 'Entry rounds', 'Clutch rounds', 'Support rounds', 'Multi kill rounds']:
                        row[name] = float(val.replace('%', ''))
                    else:
                        raise NotImplementedError(f'dont know {name=}')
            else:
                raise NotImplementedError(f'dont know {key=}')
        logger.debug(f'{row=}')
        data.append(row)
    logger.debug(f'{data=}')
    return pd.DataFrame(data)

def parse_boosters(scraped) -> pd.DataFrame:
    data = []
    for booster, players in scraped.items():
        logger.info(f'{booster=}')
        for playerstr in players:
            logger.debug(f'{playerstr=}')
            playerstr = eval(playerstr)
            name, game, percentage = playerstr.split('\n')[:3]
            percentage = percentage.replace('%', '')
            logger.info(f'{name=} {percentage=}')
            data.append({'booster': booster, 'name': name, 'percentage': int(percentage)})
    return pd.DataFrame(data)

def parse_roles(scraped) -> pd.DataFrame:
    data = []
    for role, players in scraped.items():
        logger.info(f'{role=}')
        for playerstr in players:
            logger.debug(f'{playerstr=}')
            playerstr = eval(playerstr)
            name, game, percentage = playerstr.split('\n')[:3]
            percentage = percentage.replace('%', '')
            logger.info(f'{name=} {percentage=}')
            data.append({'role': role, 'name': name, 'percentage': int(percentage)})
    return pd.DataFrame(data)

with open('settings.yml', 'r') as f:
    settings = yaml.safe_load(f)
    leagueid = settings['leagueid']

pages = ['players', 'boosters', 'roles']
parsers = parse_players, parse_boosters, parse_roles

for page, parser in zip(pages, parsers):
    try:
        fname = f'scraped/{leagueid}-{page}.yml'
        with open(fname, 'r') as inf:
            scraped = yaml.safe_load(inf)
    except FileNotFoundError:
        logger.error(f'cannot find {fname}, skipping')
        continue
    
    df = parser(scraped)

    df.to_pickle(f'pickles/{leagueid}-{page}.pkl')

    with pd.ExcelWriter(f'spreadsheets/{leagueid}-{page}.xlsx') as writer:
        # df.pivot(index='name', columns='booster').to_excel(writer)
        df.to_excel(writer)

    break

    # data = []
    # for booster, players in scraped.items():
    #     print(booster)
    #     for playerstr in players:
    #         name, game, percentage = parse_it(playerstr)
    #         print(name, percentage)
    #         data.append({'booster': booster, 'name': name, 'percentage': int(percentage)})


# for portion in ['boosters', 'roles']:
#     try:
#         fname = f'.scraped-{portion}-{leagueid}.yml'
#         with open(fname, 'r') as inf:
#             scraped = yaml.safe_load(inf)
#     except FileNotFoundError:
#         logger.error(f'cannot find {fname}, skipping')
#         continue

#     data = []
#     for booster, players in scraped.items():
#         print(booster)
#         for playerstr in players:
#             name, game, percentage = parse_it(playerstr)
#             print(name, percentage)
#             data.append({'booster': booster, 'name': name, 'percentage': int(percentage)})

#     df = pd.DataFrame(data)
#     df.to_pickle(f'pickles/{leagueid}-{portion}.pkl')
#     with pd.ExcelWriter(f'spreadsheets/{leagueid}-{portion}.xlsx') as writer:
#         df.pivot(index='name', columns='booster').to_excel(writer)
